# EEQS 后端（Django + DRF）

额尔齐斯河流域上游水资源预报管理系统后端。对外提供 RESTful API，覆盖站点/气象观测数据查询、水文日均流量预报、人工数据补录、MODIS 积雪栅格瓦片服务等能力。

## 技术栈

| 组件 | 说明 |
|------|------|
| Django 5.1 + DRF | Web 框架与 REST API |
| PostgreSQL + TimescaleDB | 数据库（含时序连续聚合视图），本地 Docker 端口 15432 |
| Celery + Redis | 异步任务队列与定时调度（APScheduler 为过渡方案） |
| drf-spectacular | OpenAPI 3.0 文档自动生成 |
| earthaccess / rioxarray / rasterio | MODIS 数据下载与栅格处理 |

## 快速开始

### 1. 准备环境

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate    # Linux/macOS

pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，至少填入：

- `DJANGO_SECRET_KEY` — 生成方式：
  `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
- `POSTGRES_PASSWORD` — 本地 Docker 数据库密码

### 3. 启动数据库（Docker）

使用 TimescaleDB 镜像，映射端口 **15432**，库名 `eeqsDB`：

```bash
docker run -d --name django-timescale \
  -e POSTGRES_DB=eeqsDB \
  -e POSTGRES_USER=<你的用户名> \
  -e POSTGRES_PASSWORD=<你的密码> \
  -p 15432:5432 \
  timescale/timescaledb:latest-pg16
```

> `.env` 中的 `POSTGRES_*` 必须与这里一致。

### 4. 初始化数据库

```bash
python manage.py migrate
python manage.py createsuperuser
```

> 注意：`WeatherDailyAgg` / `WeatherHourlyAgg` 是 TimescaleDB 连续聚合视图（`managed=False`），
> 需要先在数据库中手动创建对应物化视图，相关 API 才能工作。

### 5. 启动服务

```bash
# Django 开发服务器
python manage.py runserver

# Redis（另开终端，见 REDIS_SETUP_GUIDE.md）
redis\redis-server.exe

# Celery Worker（另开终端，Windows 推荐 solo 模式）
celery -A mysite worker -l info -P solo

# Celery Beat 定时调度（可选，另开终端）
celery -A mysite beat -l info
```

### 6. 验证

| 地址 | 说明 |
|------|------|
| `http://127.0.0.1:8000/api/schema/swagger-ui/` | Swagger API 文档 |
| `http://127.0.0.1:8000/admin/` | Django 管理后台 |

## 目录结构

```
backend/
├── manage.py
├── requirements.txt
├── .env.example              # 环境变量模板（复制为 .env 使用）
├── mysite/                   # 项目配置
│   ├── settings.py           # 敏感配置从环境变量读取
│   ├── urls.py               # 根路由（/api/、/admin/、/api/schema/）
│   └── celery.py             # Celery 应用
├── data/                     # 主应用
│   ├── models.py             # Station / WeatherData / 水文预报 / 栅格任务等
│   ├── views.py              # DRF ViewSets
│   ├── serializers.py
│   ├── filters.py            # 时间/日期范围过滤
│   ├── tasks.py              # Celery 异步任务 + APScheduler 兼容任务
│   ├── hydrology_service.py  # 水文预报编排（加载模型脚本、重试、落库）
│   ├── scheduler_setup.py    # APScheduler 启动（过渡方案）
│   ├── tile_service.py / tile_views.py  # XYZ 瓦片服务（ETag/304）
│   ├── management/commands/  # import_data / run_hydrology_forecast / sync_raster
│   ├── migrations/
│   └── raster_pipeline/      # MODIS 下载 -> 渲染 -> 切瓦片流水线
├── sync_one.py               # 单日期栅格任务补跑脚本
├── schema.yml / schema.json  # 已生成的 OpenAPI 契约
└── 技术对接文档.md            # 前后端/第三方对接说明
```

## 定时任务

| 任务 | 频率 | 说明 |
|------|------|------|
| `import-weather-data` | 每 30 分钟 | 解析 LoggerNet TOA5 数据文件，增量入库 |
| `daily-hydrology-forecast` | 每日 01:00 | 运行水文模型，产出次日日均流量预报 |
| `daily-raster-sync` | 每日 02:20 | 同步最近 16 天 MODIS 积雪数据并渲染瓦片 |

## 可选配置

- **MODIS 下载**：需要 NASA Earthdata 账号，在项目根目录创建 `.env.earthdata`：
  ```
  EARTHDATA_USERNAME=xxx
  EARTHDATA_PASSWORD=xxx
  ```
- **水文模型脚本**：通过 `HYDROLOGY_MODEL_SCRIPT_PATH` 指向本机模型脚本，
  脚本需提供 `run_forecast` 入口函数。

## 认证

当前为 Session + Basic Auth 双模式，全局默认要求登录（`IsAuthenticated`）。
第三方对接使用 `Authorization: Basic <base64(user:pass)>`。
JWT 升级规划中，详见 `技术对接文档.md`。

## 运行测试

```bash
python manage.py test
python test_raster_api.py        # 栅格 API 冒烟测试（不启动 runserver）
```
