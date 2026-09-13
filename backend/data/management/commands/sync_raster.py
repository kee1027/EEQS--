"""同步执行 MODIS 栅格 pipeline（不依赖 Celery，便于手动/调试运行）。

用法：
    python manage.py sync_raster                     # dataset_id=1, days_back=16
    python manage.py sync_raster --days-back 16
    python manage.py sync_raster --dataset-id 1 --days-back 16

首次运行会自动创建默认的 MOD10A1 阿勒泰数据集记录（幂等）。
"""

from django.core.management.base import BaseCommand, CommandError

from data.models import RasterDataset
from data.raster_pipeline.jobs import sync_latest

DEFAULT_DATASET = {
    "name": "MODIS 积雪（阿勒泰）",
    "product": "MOD10A1",
    "concept_id": "C2565093311-NSIDC_CPRD",
    "min_lon": 85.5,
    "max_lon": 91.1,
    "min_lat": 45.0,
    "max_lat": 49.2,
    "tile_dataset_name": "modis-snow",
    "is_active": True,
}


class Command(BaseCommand):
    help = "同步执行 MODIS 栅格 pipeline：下载 -> 渲染瓦片 -> 台账入库"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dataset-id",
            type=int,
            default=None,
            help="RasterDataset 主键（缺省时自动确保默认数据集存在并使用它）",
        )
        parser.add_argument(
            "--days-back",
            type=int,
            default=16,
            help="以今天为锚回溯天数（默认 16）",
        )

    def handle(self, *args, **options):
        dataset_id = options["dataset_id"]
        days_back = options["days_back"]

        if dataset_id is None:
            dataset, created = RasterDataset.objects.get_or_create(
                name=DEFAULT_DATASET["name"],
                product=DEFAULT_DATASET["product"],
                defaults=DEFAULT_DATASET,
            )
            dataset_id = dataset.pk
            verb = "创建" if created else "复用"
            self.stdout.write(f"{verb}数据集: id={dataset_id} {dataset}")
        elif not RasterDataset.objects.filter(pk=dataset_id).exists():
            raise CommandError(f"RasterDataset id={dataset_id} 不存在")

        self.stdout.write(
            self.style.NOTICE(
                f"开始同步: dataset_id={dataset_id}, days_back={days_back}"
            )
        )
        summary = sync_latest(
            dataset_id=dataset_id,
            days_back=days_back,
            triggered_by="manual",
        )

        for r in summary["results"]:
            line = f"  {r['date']}: {r['status']}"
            if r.get("tile_count"):
                line += f" (tiles={r['tile_count']})"
            if r.get("error"):
                line += f" ERROR: {r['error']}"
            if r.get("reason"):
                line += f" ({r['reason']})"
            self.stdout.write(line)

        self.stdout.write(
            self.style.SUCCESS(
                f"完成: 下载/渲染 {len(summary['downloaded'])} 期, "
                f"跳过 {len(summary['skipped'])} 期, "
                f"待数据 {len(summary['pending'])} 期, "
                f"失败 {len(summary['failed'])} 期"
            )
        )
