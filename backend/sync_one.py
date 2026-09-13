"""处理窗口内最早一个未完成日期的栅格任务（供短超时多次调用，幂等续跑）。

用法: venv/Scripts/python.exe sync_one.py [days_back]
每次调用：确保数据集存在 -> 整窗搜索 -> 找到最早一个非 SUCCESS 且有数据的日期
-> 创建/复用 RasterJob -> 执行 run_raster_job -> 打印结果。
全部完成时打印 ALL_DONE。
"""
import os
import sys
from datetime import timedelta

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

from django.utils import timezone

from data.models import RasterDataset, RasterJob
from data.management.commands.sync_raster import DEFAULT_DATASET
from data.raster_pipeline.downloader import parse_data_date, search_modis
from data.raster_pipeline.jobs import run_raster_job

days_back = int(sys.argv[1]) if len(sys.argv) > 1 else 16

dataset, _ = RasterDataset.objects.get_or_create(
    name=DEFAULT_DATASET["name"],
    product=DEFAULT_DATASET["product"],
    defaults=DEFAULT_DATASET,
)

today = timezone.localdate()
window_start = today - timedelta(days=days_back - 1)

granules = search_modis(window_start, today, dataset.bbox, dataset.concept_id)
by_date = {}
for g in granules:
    try:
        d = parse_data_date(g["meta"]["native-id"])
    except ValueError:
        continue
    by_date.setdefault(d, []).append(g)

for i in range(days_back - 1, -1, -1):  # 从最早日期开始
    d = today - timedelta(days=i)
    existing = RasterJob.objects.filter(dataset=dataset, date=d).first()
    if existing and existing.status == RasterJob.Status.SUCCESS:
        continue
    day_granules = by_date.get(d, [])
    if not day_granules:
        if existing is None:
            RasterJob.objects.create(
                dataset=dataset, date=d,
                status=RasterJob.Status.PENDING, triggered_by="manual",
            )
        print(f"{d}: PENDING (no granule)")
        continue
    if existing is None:
        existing = RasterJob.objects.create(
            dataset=dataset, date=d,
            status=RasterJob.Status.PENDING, triggered_by="manual",
        )
    result = run_raster_job(existing.pk, granules=day_granules)
    print("RESULT:", result)
    sys.exit(0 if result["status"] == "SUCCESS" else 2)

print("ALL_DONE")
