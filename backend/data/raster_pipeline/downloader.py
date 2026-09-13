"""MODIS 数据下载器。

基于 earthaccess（NASA Earthdata Login）实现 MOD10A1 的检索与下载。
落盘结构约定：data/raster_data/raw/<产品>/<YYYY-MM-DD>/<文件名>.hdf

凭据：从项目根目录 .env.earthdata 读取（EARTHDATA_USERNAME / EARTHDATA_PASSWORD），
设置到环境变量后用 earthaccess.login(strategy="environment") 登录。
凭据不得硬编码在任何 .py 源码中。
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path

# 项目根目录（本文件位于 <root>/data/raster_pipeline/downloader.py）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env.earthdata"

DEFAULT_CONCEPT_ID = "C2565093311-NSIDC_CPRD"  # MOD10A1 V061
RAW_ROOT = PROJECT_ROOT / "data" / "raster_data" / "raw"


def load_earthdata_credentials(env_file: str | Path = ENV_FILE) -> None:
    """从 .env.earthdata 读取凭据并写入 os.environ（不覆盖已有环境变量）。"""
    env_path = Path(env_file)
    if not env_path.exists():
        raise FileNotFoundError(f"Earthdata 凭据文件不存在: {env_path}")

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key:
            os.environ.setdefault(key, value)

    if not os.environ.get("EARTHDATA_USERNAME") or not os.environ.get("EARTHDATA_PASSWORD"):
        raise ValueError(f"{env_path} 中缺少 EARTHDATA_USERNAME 或 EARTHDATA_PASSWORD")


def _login():
    """加载凭据并登录 Earthdata，返回 earthaccess 模块（已认证）。"""
    import earthaccess

    load_earthdata_credentials()
    auth = earthaccess.login(strategy="environment")
    if not auth.authenticated:
        raise RuntimeError("Earthdata 登录失败：请检查 .env.earthdata 凭据")
    return earthaccess


def parse_data_date(file_name: str) -> date:
    """从 MODIS 文件名解析数据日期。

    例如 MOD10A1.A2026005.h23v04.061.2026008011240.hdf
    -> A2026005 表示 2026 年第 005 天 -> 2026-01-05
    """
    match = re.search(r"\.A(\d{4})(\d{3})\.", str(file_name))
    if not match:
        raise ValueError(f"无法从文件名解析数据日期: {file_name}")
    year, doy = int(match.group(1)), int(match.group(2))
    return date(year, 1, 1) + timedelta(days=doy - 1)


def search_modis(
    date_start: str | date,
    date_end: str | date,
    bbox: tuple[float, float, float, float],
    concept_id: str = DEFAULT_CONCEPT_ID,
):
    """按时间窗口 + 空间范围搜索 MODIS granule。

    Parameters
    ----------
    date_start, date_end : str | date
        观测日期范围（闭区间），"YYYY-MM-DD"。
    bbox : tuple
        (min_lon, min_lat, max_lon, max_lat)。
    concept_id : str
        CMR concept id，默认 MOD10A1 V061。

    Returns
    -------
    list
        earthaccess granule 结果列表。
    """
    earthaccess = _login()

    if isinstance(date_start, date):
        date_start = date_start.isoformat()
    if isinstance(date_end, date):
        date_end = date_end.isoformat()

    return earthaccess.search_data(
        concept_id=concept_id,
        temporal=(date_start, date_end),
        bounding_box=bbox,
    )


def download_modis(results, out_dir: str | Path) -> list[Path]:
    """下载搜索结果到指定目录，返回落盘文件路径列表。

    已存在且大小一致的文件由 earthaccess 自动跳过（断点续传）。
    """
    earthaccess = _login()

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not results:
        return []

    files = earthaccess.download(results, local_path=str(out_dir))
    return [Path(f) for f in files]
