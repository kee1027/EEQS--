"""栅格任务编排：「自动下载 -> 渲染瓦片 -> 台账入库」状态机。

状态机：PENDING -> DOWNLOADING -> RENDERING -> SUCCESS / FAILED
幂等约定：同一 (dataset, date) 已有 SUCCESS 的 RasterJob 时跳过。

瓦片输出策略（本期）：渲染某日期成功后，清空瓦片根目录下旧瓦片再写入新瓦片
（"最新一期覆盖"设计；多日期历史切换是已知后续扩展点）。
"""

from __future__ import annotations

import shutil
from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .downloader import (
    DEFAULT_CONCEPT_ID,
    RAW_ROOT,
    download_modis,
    parse_data_date,
    search_modis,
)
from .readers import read_modis_hdf_to_xarray
from .render import render_to_geotiff, tile_geotiff

# 本文件位于 data/raster_pipeline/jobs.py；data 包根为 parents[1]
TMP_ROOT = Path(__file__).resolve().parents[1] / "raster_data" / "tmp"

MIN_ZOOM = 6
MAX_ZOOM = 11


def _get_model(name):
    """延迟加载 ORM 模型（避免在 Django 未就绪时导入失败）。"""
    from data import models

    return getattr(models, name)


def _tile_root(dataset) -> Path:
    root = settings.TILE_DATASETS.get(dataset.tile_dataset_name)
    if root is None:
        raise ValueError(
            f"TILE_DATASETS 中未注册瓦片数据集: {dataset.tile_dataset_name}"
        )
    return Path(root)


def _clear_tiles(tile_root: Path) -> None:
    """清空瓦片根目录（保留目录本身）。"""
    if tile_root.exists():
        shutil.rmtree(tile_root)
    tile_root.mkdir(parents=True, exist_ok=True)


def run_raster_job(job_id: int, granules=None) -> dict:
    """执行一个栅格处理任务，返回最终状态摘要。

    Parameters
    ----------
    job_id : int
        RasterJob 主键。
    granules : list | None
        预先搜索好的 earthaccess granule 列表（sync_latest 整窗搜索后按天传入）。
        None 则按 job.date 单独搜索。
    """
    RasterJob = _get_model("RasterJob")

    job = RasterJob.objects.select_related("dataset").get(pk=job_id)
    dataset = job.dataset

    try:
        # ------------------------------------------------------------------
        # 1. DOWNLOADING：下载该数据日期的 HDF 到 raw/<product>/<date>/
        # ------------------------------------------------------------------
        job.status = RasterJob.Status.DOWNLOADING
        job.error_message = ""
        job.save(update_fields=["status", "error_message"])

        date_str = job.date.isoformat()
        out_dir = RAW_ROOT / dataset.product / date_str

        if granules is None:
            granules = search_modis(
                date_start=job.date,
                date_end=job.date,
                bbox=dataset.bbox,
                concept_id=dataset.concept_id or DEFAULT_CONCEPT_ID,
            )

        downloaded = download_modis(granules, out_dir)
        source_files = sorted(p.name for p in downloaded)

        # 兜底：earthaccess 跳过已存在文件时返回列表仍包含路径；
        # 若下载结果为空但目录已有文件，直接采用目录内容（幂等重跑）。
        if not source_files and out_dir.exists():
            source_files = sorted(p.name for p in out_dir.glob("*.hdf"))

        if not source_files:
            raise RuntimeError(f"{dataset.product} {date_str} 无可用数据文件")

        # ------------------------------------------------------------------
        # 2. RENDERING：读取该日期目录全部 HDF -> GeoTIFF -> XYZ 瓦片
        # ------------------------------------------------------------------
        job.status = RasterJob.Status.RENDERING
        job.source_files = source_files
        job.save(update_fields=["status", "source_files"])

        hdf_files = sorted(out_dir.glob("*.hdf"))
        if not hdf_files:
            raise RuntimeError(f"目录 {out_dir} 下没有 HDF 文件")

        arrays = [read_modis_hdf_to_xarray(str(p)) for p in hdf_files]

        TMP_ROOT.mkdir(parents=True, exist_ok=True)
        tif_path = TMP_ROOT / f"{dataset.product}_{date_str}.tif"
        render_to_geotiff(
            arrays,
            tif_path,
            clip_bounds_lonlat=dataset.bbox,
        )

        tile_root = _tile_root(dataset)
        _clear_tiles(tile_root)
        written = tile_geotiff(tif_path, tile_root, min_zoom=MIN_ZOOM, max_zoom=MAX_ZOOM)

        # ------------------------------------------------------------------
        # 3. SUCCESS：台账落库
        # ------------------------------------------------------------------
        with transaction.atomic():
            job = RasterJob.objects.select_for_update().get(pk=job_id)
            job.status = RasterJob.Status.SUCCESS
            job.tile_count = len(written)
            job.error_message = ""
            job.finished_at = timezone.now()
            job.save(
                update_fields=[
                    "status",
                    "tile_count",
                    "error_message",
                    "finished_at",
                ]
            )

        return {
            "job_id": job_id,
            "date": date_str,
            "status": job.status,
            "source_files": source_files,
            "tile_count": len(written),
        }

    except Exception as exc:
        with transaction.atomic():
            job = RasterJob.objects.select_for_update().get(pk=job_id)
            job.status = RasterJob.Status.FAILED
            job.error_message = str(exc)[:2000]
            job.finished_at = timezone.now()
            job.save(update_fields=["status", "error_message", "finished_at"])
        return {
            "job_id": job_id,
            "date": date_str,
            "status": RasterJob.Status.FAILED,
            "error": str(exc)[:2000],
        }


def sync_latest(dataset_id: int, days_back: int = 16, triggered_by: str = "schedule") -> dict:
    """核心定时入口：以今天为锚回溯 days_back 天，逐日补齐缺失数据。

    - earthaccess 搜索整个窗口一次，按数据日期分组
    - 每一天：已有 SUCCESS 的 RasterJob 则跳过（幂等）；否则创建/复用并执行
    - 卫星数据有几天延迟，窗口内无数据的日期记为 PENDING 台账（等待次日再试）

    Returns
    -------
    dict: {dataset_id, window, downloaded, skipped, failed, pending, results}
    """
    RasterDataset = _get_model("RasterDataset")
    RasterJob = _get_model("RasterJob")

    dataset = RasterDataset.objects.get(pk=dataset_id)
    today = timezone.localdate()
    window_start = today - timedelta(days=days_back - 1)

    # 整窗搜索一次
    granules = search_modis(
        date_start=window_start,
        date_end=today,
        bbox=dataset.bbox,
        concept_id=dataset.concept_id or DEFAULT_CONCEPT_ID,
    )

    # 按数据日期分组（从 granule 文件名解析年积日）
    by_date: dict[date, list] = {}
    for g in granules:
        file_name = g["meta"]["native-id"] if isinstance(g, dict) else g.get("meta", {}).get("native-id", "")
        # earthaccess DataGranule 支持 dict 风格访问；取不到时退回 granule 标题
        if not file_name:
            file_name = str(g)
        try:
            d = parse_data_date(file_name)
        except ValueError:
            continue
        by_date.setdefault(d, []).append(g)

    results = []
    downloaded, skipped, failed, pending = [], [], [], []

    all_dates = [today - timedelta(days=i) for i in range(days_back)]

    for d in sorted(all_dates):
        date_str = d.isoformat()

        existing = RasterJob.objects.filter(dataset=dataset, date=d).first()
        if existing and existing.status == RasterJob.Status.SUCCESS:
            skipped.append(date_str)
            results.append({"date": date_str, "status": "SKIPPED", "job_id": existing.pk})
            continue

        day_granules = by_date.get(d, [])
        if not day_granules:
            # 卫星数据延迟：本期无数据，留 PENDING 台账等下轮
            if existing is None:
                existing = RasterJob.objects.create(
                    dataset=dataset,
                    date=d,
                    status=RasterJob.Status.PENDING,
                    triggered_by=triggered_by,
                )
            pending.append(date_str)
            results.append(
                {"date": date_str, "status": "PENDING", "job_id": existing.pk,
                 "reason": "no granule in window"}
            )
            continue

        if existing is None:
            existing = RasterJob.objects.create(
                dataset=dataset,
                date=d,
                status=RasterJob.Status.PENDING,
                triggered_by=triggered_by,
            )

        result = run_raster_job(existing.pk, granules=day_granules)
        results.append(result)
        if result["status"] == RasterJob.Status.SUCCESS:
            downloaded.append(date_str)
        else:
            failed.append(date_str)

    return {
        "dataset_id": dataset_id,
        "window": [window_start.isoformat(), today.isoformat()],
        "downloaded": downloaded,
        "skipped": skipped,
        "failed": failed,
        "pending": pending,
        "results": results,
    }
