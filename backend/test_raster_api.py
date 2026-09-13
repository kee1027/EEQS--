"""用 Django test client 验证 raster pipeline API（不启动 runserver）。"""
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from data.models import RasterJob

User = get_user_model()
user = User.objects.filter(is_superuser=True).first() or User.objects.first()
if user is None:
    user = User.objects.create_superuser("apitest", "apitest@example.com", "apitest-pass")
    print("created temp superuser: apitest")

client = Client()
client.force_login(user)
print("auth as:", user.username)

checks = []

r = client.get("/api/raster-datasets/")
checks.append(("GET /api/raster-datasets/", r.status_code))
print("datasets:", r.json() if r.status_code == 200 else r.content[:200])

r = client.get("/api/raster-datasets/1/dates/")
checks.append(("GET /api/raster-datasets/1/dates/", r.status_code))
payload = r.json() if r.status_code == 200 else r.content[:200]
print(f"dates: {len(payload.get('dates', []))} 个 ->", payload)

r = client.get("/api/raster-jobs/")
checks.append(("GET /api/raster-jobs/", r.status_code))
data = r.json()
rows = data.get("results", data) if isinstance(data, dict) else data
print(f"jobs: {len(rows)} 条")

r = client.get("/api/raster-jobs/?dataset=1&date=2026-08-23")
checks.append(("GET /api/raster-jobs/?dataset=1&date=2026-08-23", r.status_code))
print("filtered:", r.json())

# 取一张真实存在的新瓦片
job = RasterJob.objects.filter(status="SUCCESS").order_by("-date").first()
print("latest SUCCESS:", job.date if job else None)
r = client.get("/api/tiles/modis-snow/8/190/89.png")
checks.append(("GET /api/tiles/modis-snow/8/190/89.png", r.status_code))
body = b"".join(r.streaming_content) if hasattr(r, "streaming_content") else r.content
print("tile content-type:", r.headers.get("Content-Type"), "bytes:", len(body))

print("\n==== 汇总 ====")
ok = True
for name, code in checks:
    flag = "PASS" if code == 200 else "FAIL"
    if code != 200:
        ok = False
    print(f"[{flag}] {name} -> {code}")
print("ALL PASS" if ok else "SOME FAILED")
