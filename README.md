# EEQS 可视化平台

额尔齐斯河流域上游水资源预报管理系统 —— 前后端分离的可视化平台。

核心能力：多站点气象-水文观测数据接入与展示、水文模型日均流量预报、人工数据补录与审核、MODIS 积雪栅格地图可视化。

## 技术架构

| 层级 | 技术栈 |
|------|--------|
| 前端 | Vue + Element UI + ECharts + Leaflet |
| 后端 | Django 5.1 + Django REST Framework |
| 数据库 | PostgreSQL + TimescaleDB（端口 15432） |
| 异步任务 | Celery + Redis |
| API 文档 | drf-spectacular（OpenAPI 3.0，Swagger UI） |

## 目录结构

- `frontend/` — 前端项目（Vue + Leaflet 地图可视化）
- `backend/` — 后端服务（Django + DRF，RESTful API）

## 快速开始

### 前端

```bash
cd frontend
npm install
npm run serve
```

### 后端

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows（Linux/macOS: source venv/bin/activate）
pip install -r requirements.txt
cp .env.example .env           # 填入 DJANGO_SECRET_KEY 和 POSTGRES_PASSWORD
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

> 数据库（TimescaleDB Docker）与 Redis 的启动方式、Celery 配置等细节见
> [backend/README.md](backend/README.md)。

## 对接与文档

- API 基地址：`http://127.0.0.1:8000/api/`
- Swagger 文档：`http://127.0.0.1:8000/api/schema/swagger-ui/`
- 已生成的 OpenAPI 契约：`backend/schema.yml`
- 前后端/第三方对接说明：[backend/技术对接文档.md](backend/技术对接文档.md)

## 协作约定

- 敏感配置一律走环境变量：复制 `backend/.env.example` 为 `backend/.env`（已 gitignore），不要提交真实凭据。
- API 变更遵循向后兼容；新增接口请同步更新 `技术对接文档.md`。
- 提交前运行 `python manage.py check` 与 `python manage.py test`。
