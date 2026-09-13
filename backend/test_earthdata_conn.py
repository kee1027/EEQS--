"""earthaccess 连通性测试：登录 + 搜索最近 16 天 MOD10A1，不下载。"""
import collections
from datetime import date, timedelta

from data.raster_pipeline.downloader import parse_data_date, search_modis

today = date.today()
start = today - timedelta(days=15)
print("searching", start, "->", today)
results = search_modis(start, today, (85.5, 45.0, 91.1, 49.2))
print("granules:", len(results))
counter = collections.Counter()
for g in results:
    nid = g["meta"]["native-id"]
    counter[parse_data_date(nid).isoformat()] += 1
for d in sorted(counter):
    print(d, counter[d])
