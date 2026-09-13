# Django 水文气象平台 — 系统功能实施方案

> **版本**：v1.0  
> **编制日期**：2026-07-22  
> **适用范围**：权限控制体系、Celery 异步任务调度、APScheduler 平滑迁移  
> **约束**：本方案为**纯设计文档**，不涉及代码修改，仅用于指导后续开发。

---

## 目录

1. [项目现状概述](#1-项目现状概述)
2. [目标架构蓝图](#2-目标架构蓝图)
3. [Phase 1：Celery 基础设施稳定化](#3-phase-1celery-基础设施稳定化)
4. [Phase 2：权限控制体系（RBAC）](#4-phase-2权限控制体系rbac)
5. [Phase 3：异步任务全面切换与双轨运行](#5-phase-3异步任务全面切换与双轨运行)
6. [Phase 4：APScheduler 退役与清理](#6-phase-4apscheduler-退役与清理)
7. [Phase 5：运维监控与告警](#7-phase-5运维监控与告警)
8. [附录 A：环境搭建参考](#附录-a环境搭建参考)
9. [附录 B：常见问题排查](#附录-b常见问题排查)
10. [附录 C：API 权限矩阵](#附录-capi-权限矩阵)

---

## 1. 项目现状概述

### 1.1 技术栈

| 层级 | 组件 | 版本/说明 |
|------|------|----------|
| Web 框架 | Django | 5.1.15 |
| API 框架 | Django REST Framework | 3.15+ |
| 数据库 | PostgreSQL + TimescaleDB | 端口 15432 |
| 任务队列 | Celery + Redis | Celery 5.3+，Redis 本地服务 |
| 定时调度 | APScheduler (legacy) | 内嵌于 Django，计划迁移至 Celery Beat |
| 文档 | drf-spectacular | Swagger / ReDoc |
| 跨域 | django-cors-headers | 开发环境 `CORS_ALLOW_ALL_ORIGINS = True` |

### 1.2 已有模型

| 模型 | 说明 | 当前权限 |
|------|------|----------|
| `Station` | 站点基础信息 | 匿名可读 |
| `WeatherData` | 原始气象数据 | 匿名可读（默认7天过滤） |
| `ManualDataRecord` | 人工录入数据 | 仅认证用户可创建；创建者/管理员可作废 |
| `HydrologyForecastRun` | 水文预测运行记录 | 仅管理员可手动触发；所有人可查看 |
| `HydrologyForecastDaily` | 水文日预测结果 | 匿名可读 |
| `WeatherDailyAgg` / `WeatherHourlyAgg` | TimescaleDB 连续聚合 | 匿名可读（managed=False） |

### 1.3 已有 Celery 基础设施

- `mysite/celery.py`：Celery App 配置，自动发现任务 ✅
- `mysite/__init__.py`：确保 Django 启动时加载 Celery ✅
- `settings.py`：完整 Celery 配置（Broker/Result Backend/Beat Schedule）✅
- `data/tasks.py`：`import_data_task`、`hydrology_forecast_task` 两个 `@shared_task` ✅
- `data/views.py`：`HydrologyForecastRunViewSet.create` 支持 `HYDROLOGY_ASYNC_MODE` 双模式切换 ✅
- `data/urls.py`：`/api/tasks/<task_id>/` 状态查询路由 ✅
- `requirements.txt`：已包含 `celery`、`redis`、`django-celery-results` ✅

### 1.4 当前已知问题

| 问题 | 影响 | 建议处理方式 |
|------|------|-------------|
| Docker 无法拉取 Redis 镜像（网络超时） | 开发环境 Redis 需本地独立安装 | 使用 Windows 版 Redis 或 WSL2 内 Redis |
| `requirements.txt` 存在重复依赖行 | 无功能影响，但冗余 | 去重整理 |
| PostgreSQL 连接偶发 `Connection refused` | 调度器启动失败 | 检查 Docker 容器健康状态 |
| Windows 下 Celery 需 `-P solo` 或 `eventlet` | Worker 默认 prefork 在 Windows 不可用 | 启动命令显式指定 `-P solo` |
| 权限控制仅依赖 `IsAuthenticated` + `is_staff` 硬编码 | 无法支撑多角色细粒度控制 | Phase 2 实施 RBAC |

---

## 2. 目标架构蓝图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              客户端 (Browser / curl / 前端)                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Django + DRF (Web 层)                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  RBAC 中间件  │  │ 视图权限控制  │  │ 双模式分发器  │  │ API 文档     │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                  ▼
           ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
           │ 同步模式     │    │ 异步模式     │    │ Celery Beat │
           │ (默认 fallback)│   │ (Celery Task)│   │ (定时调度)   │
           └─────────────┘    └─────────────┘    └─────────────┘
                    │                  │                  │
                    └──────────────────┼──────────────────┘
                                       ▼
                          ┌─────────────────────────┐
                          │      Redis Broker        │
                          │    (db0: task queue)     │
                          └─────────────────────────┘
                                       │
                                       ▼
                          ┌─────────────────────────┐
                          │    Celery Worker(s)      │
                          │  - import_data_task      │
                          │  - hydrology_forecast_task│
                          └─────────────────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    ▼                                     ▼
           ┌─────────────┐                        ┌─────────────┐
           │ PostgreSQL  │                        │ django-celery│
           │ (业务数据)   │                        │ -results   │
           │             │                        │ (任务结果)   │
           │ TimescaleDB │                        └─────────────┘
           │ 连续聚合     │
           └─────────────┘
```

---

## 3. Phase 1：Celery 基础设施稳定化

### 3.1 目标

确保 Celery + Redis 在 Windows 开发环境和未来 Linux 生产环境均能稳定运行，为后续功能开发提供可靠的任务队列底座。

### 3.2 环境搭建步骤（Windows 开发机）

**步骤 1：Redis 服务启动**

由于 Docker 拉取镜像存在网络问题，采用以下替代方案：

```bash
# 方案 A：使用 Memurai（Windows 原生 Redis 兼容替代品）
# 下载地址：https://www.memurai.com/
# 安装后 Redis 默认在 127.0.0.1:6379 启动

# 方案 B：使用 WSL2 安装 Redis
wsl -d Ubuntu
sudo apt update && sudo apt install redis-server
sudo service redis-server start
# 需在 WSL2 中配置 bind 0.0.0.0 以允许 Windows 宿主机访问

# 验证 Redis 是否运行
redis-cli ping
# 期望返回：PONG
```

**步骤 2：安装依赖**

```bash
venv\Scripts\python -m pip install -r requirements.txt
# 或仅安装新增依赖
venv\Scripts\python -m pip install celery redis django-celery-results
```

**步骤 3：数据库迁移（django-celery-results 需要创建结果表）**

```bash
venv\Scripts\python manage.py migrate django_celery_results
```

**步骤 4：启动 Celery Worker**

```bash
# Windows 必须使用 -P solo（prefork 在 Windows 上不可用）
venv\Scripts\celery -A mysite worker -l info -P solo

# 如需要更高的并发，可安装 eventlet：
# venv\Scripts\python -m pip install eventlet
# venv\Scripts\celery -A mysite worker -l info -P eventlet -c 4
```

**步骤 5：启动 Celery Beat（用于定时调度）**

```bash
# 在独立终端中启动
venv\Scripts\celery -A mysite beat -l info
```

### 3.3 同步模式验证（默认配置）

`settings.py` 中 `HYDROLOGY_ASYNC_MODE = False`，此时 API 为同步阻塞模式：

```bash
# Windows CMD 正确格式（注意双引号转义）
curl -X POST http://localhost:8000/api/hydrology-runs/ -H "Content-Type: application/json" -u admin1:eeqs123456 -d "{\"target_date\": \"2026-07-08\"}"

# 或使用 PowerShell
$headers = @{ "Content-Type" = "application/json" }
$cred = [System.Convert]::ToBase64String([System.Text.Encoding]::ASCII.GetBytes("admin1:eeqs123456"))
$headers["Authorization"] = "Basic $cred"
Invoke-RestMethod -Uri "http://localhost:8000/api/hydrology-runs/" -Method POST -Headers $headers -Body '{"target_date": "2026-07-08"}'
```

**期望响应（201 Created）**：
```json
{
  "id": 1,
  "run_id": "hydro-20260722-001",
  "target_date": "2026-07-08",
  "status": "success",
  ...
}
```

### 3.4 异步模式验证

将 `HYDROLOGY_ASYNC_MODE` 改为 `True`，重启 Django 服务：

```bash
# 1. 修改 settings.py 中 HYDROLOGY_ASYNC_MODE = True
# 2. 重启 Django runserver
venv\Scripts\python manage.py runserver

# 3. 确保 Celery Worker 仍在运行
```

**期望响应（202 Accepted）**：
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "queued",
  "target_date": "2026-07-08",
  "message": "水文预测任务已加入队列，请通过 /api/tasks/<task_id>/ 查询状态。"
}
```

**轮询任务状态**：
```bash
curl -u admin1:eeqs123456 http://localhost:8000/api/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890/
```

**Worker 终端应显示执行日志**。

### 3.5 关键配置项说明

| 配置项 | 当前值 | 说明 |
|--------|--------|------|
| `CELERY_BROKER_URL` | `redis://127.0.0.1:6379/0` | Redis 作为消息代理 |
| `CELERY_RESULT_BACKEND` | `django-db` | 任务结果存入 PostgreSQL（通过 django-celery-results）|
| `CELERY_TASK_TIME_LIMIT` | `3600` | 硬超时 1 小时，防止模型脚本死锁 |
| `CELERY_TASK_SOFT_TIME_LIMIT` | `3300` | 软超时 55 分钟，触发优雅退出 |
| `CELERY_TASK_ACKS_LATE` | `True` | Worker 崩溃时任务不会丢失 |
| `CELERY_WORKER_PREFETCH_MULTIPLIER` | `1` | 长任务场景下每个 Worker 一次只取 1 个任务 |
| `HYDROLOGY_ASYNC_MODE` | `False` | 功能开关：False=同步（默认），True=异步 |

### 3.6 验收标准

- [ ] Django `runserver` 启动无报错
- [ ] Celery Worker 启动无报错，自动发现 `data.tasks` 中的任务
- [ ] Celery Beat 启动无报错，按计划调度任务
- [ ] 同步模式下 POST `/api/hydrology-runs/` 返回 `201` + 预测结果
- [ ] 异步模式下 POST `/api/hydrology-runs/` 返回 `202` + `task_id`
- [ ] GET `/api/tasks/<task_id>/` 能正确返回任务状态
- [ ] Worker 终端能看到任务执行日志和结果

---

## 4. Phase 2：权限控制体系（RBAC）

### 4.1 现状分析

当前权限控制非常基础：

| 端点 | 当前权限 | 问题 |
|------|----------|------|
| `/api/stations/` | `ReadOnly`（无显式权限类） | 匿名可访问，无角色区分 |
| `/api/weatherdata/` | `ReadOnly`（无显式权限类） | 同上 |
| `/api/manual-data/` | `IsAuthenticated` | 所有登录用户均可创建 |
| `/api/hydrology-runs/` (POST) | `is_staff` 硬编码检查 | 无法支持"数据分析师"等非管理员角色 |
| `/api/hydrology-runs/` (GET) | `IsAuthenticated` | 同上 |
| `/api/tasks/<id>/` | `IsAuthenticated` | 同上 |

**痛点**：
1. 没有角色概念，仅有「匿名 / 普通用户 / 管理员」三级
2. 权限检查散落在视图方法中（`is_staff` 硬编码），难以维护
3. 无法支持「仅允许查看本站点数据」、「仅允许查看特定模型结果」等数据级权限
4. 前端无法根据角色动态渲染菜单和按钮

### 4.2 目标设计

引入基于 Django Groups + 自定义 Permission 的轻量级 RBAC 体系，覆盖：

1. **角色定义**：数据录入员、数据分析师、系统管理员
2. **功能级权限**：控制 API 端点的访问
3. **数据级权限**：控制可查看的站点、模型、时间范围
4. **操作级权限**：控制创建、修改、作废、触发预测等操作

### 4.3 角色与权限矩阵

#### 4.3.1 角色定义

| 角色 | 标识 | 典型用户 |
|------|------|----------|
| 系统管理员 | `role_admin` | 运维人员 |
| 数据分析师 | `role_analyst` | 科研人员 |
| 数据录入员 | `role_data_entry` | 野外站工作人员 |
| 只读访客 | `role_readonly` | 外部合作方 |

#### 4.3.2 功能权限清单

| 权限代码 | 说明 | 管理员 | 分析师 | 录入员 | 只读 |
|----------|------|--------|--------|--------|------|
| `view_station` | 查看站点列表 | ✅ | ✅ | ✅ | ✅ |
| `view_weatherdata` | 查看气象数据 | ✅ | ✅ | ✅ | ✅ |
| `view_hydrology_forecast` | 查看水文预测结果 | ✅ | ✅ | ✅ | ✅ |
| `view_continuous_agg` | 查看聚合数据 | ✅ | ✅ | ✅ | ✅ |
| `add_manualdatarecord` | 录入人工数据 | ✅ | ✅ | ✅ | ❌ |
| `void_manualdatarecord` | 作废人工数据 | ✅ | ✅ | ❌ | ❌ |
| `trigger_hydrology_forecast` | 手动触发预测 | ✅ | ✅ | ❌ | ❌ |
| `view_task_status` | 查看 Celery 任务状态 | ✅ | ✅ | ❌ | ❌ |
| `change_hydrologyforecastrun` | 修改预测运行记录 | ✅ | ❌ | ❌ | ❌ |
| `view_admin_dashboard` | 访问管理后台 | ✅ | ❌ | ❌ | ❌ |
| `manage_users` | 用户管理 | ✅ | ❌ | ❌ | ❌ |

### 4.4 技术方案

#### 4.4.1 方案选型：Django 原生权限 + DRF 扩展

**不引入额外依赖**（如 django-guardian），理由：
- 当前权限需求以「功能级」为主，数据级权限需求简单
- 减少依赖复杂度，降低维护成本
- 如需对象级权限（如"只能看自己录入的数据"），可通过 `queryset.filter(operator=request.user)` 实现

**如后续需要复杂对象级权限，再评估 django-guardian 或 django-rules。**

#### 4.4.2 权限中间件设计

在 `data/permissions.py` 中创建自定义权限类：

1. **`RoleBasedPermission`**：基于用户 Group 的权限控制
2. **`IsAdminOrAnalyst`**：允许管理员和分析师访问
3. **`IsDataEntryOrAbove`**：允许录入员及以上角色
4. **`IsOwnerOrStaff`**：对象级权限（用于 ManualDataRecord 的 void 操作）

#### 4.4.3 数据级权限策略

| 场景 | 实现方式 |
|------|----------|
| 仅查看指定站点数据 | `queryset.filter(station__name__in=user_allowed_stations)` |
| 仅查看指定模型结果 | `queryset.filter(model_name__in=user_allowed_models)` |
| 仅查看最近 N 天数据 | 已在 WeatherDataViewSet 中实现 `DEFAULT_DAYS_BACK` |
| 仅操作自己的记录 | `ManualDataRecordViewSet.void` 中已检查 `operator_id` |

**扩展建议**：在 User 模型或 UserProfile 模型中增加 `allowed_stations` 多对多字段，实现更灵活的数据范围控制。

#### 4.4.4 初始化脚本

创建管理命令 `init_roles`，用于：
1. 创建 Django Group（数据录入员、数据分析师、系统管理员、只读访客）
2. 为每个 Group 分配对应的 Django Permission
3. 输出初始化结果报告

```bash
venv\Scripts\python manage.py init_roles
```

### 4.5 实施步骤

| 步骤 | 内容 | 涉及的文件 |
|------|------|-----------|
| 2.1 | 创建 `data/permissions.py` | 新建 |
| 2.2 | 创建 `data/management/commands/init_roles.py` | 新建 |
| 2.3 | 修改各 ViewSet 的 `permission_classes` | `data/views.py` |
| 2.4 | 修改 `ManualDataRecordViewSet.void` 使用新权限类 | `data/views.py` |
| 2.5 | 修改 `HydrologyForecastRunViewSet.create` 使用新权限类 | `data/views.py` |
| 2.6 | 运行初始化命令并验证 | 命令行 |
| 2.7 | 更新 API 文档说明权限要求 | 自动（drf-spectacular 会读取 permission 信息）|

### 4.6 验收标准

- [ ] 匿名用户访问需认证的端点返回 `401/403`
- [ ] 普通登录用户（无角色）只能访问公共只读端点
- [ ] 数据录入员可以创建 ManualDataRecord，但不能触发预测
- [ ] 数据分析师可以触发预测、查看任务状态，但不能修改运行记录
- [ ] 系统管理员拥有所有权限
- [ ] `init_roles` 命令可重复运行（幂等），不报错

---

## 5. Phase 3：异步任务全面切换与双轨运行

### 5.1 设计原则

1. **可回滚**：通过 `HYDROLOGY_ASYNC_MODE` 开关，可随时切回同步模式
2. **零停机**：APScheduler 和 Celery Beat 并行运行，逐步验证
3. **任务可观测**：所有 Celery 任务状态可查、日志可追踪
4. **失败可恢复**：利用 Celery 的 retry 机制和结果持久化

### 5.2 双轨运行策略

```
Phase 3.1：并行验证期（1-2 周）
  - APScheduler 继续运行（weather_v4_stable, hydrology_daily_v1）
  - Celery Beat 同时运行（import_data_task, hydrology_forecast_task）
  - 两套调度产生的运行记录同时存在，便于对比验证

Phase 3.2：Celery 主运行期（1 周）
  - 停用 APScheduler 的 hydrology_daily_v1，保留 weather_v4_stable
  - HYDROLOGY_ASYNC_MODE = True（默认异步）

Phase 3.3：完全切换（Phase 4）
  - 停用所有 APScheduler 任务
  - 移除 django-apscheduler 依赖
```

### 5.3 任务调度映射

| 原 APScheduler 任务 | Celery 任务 | 调度频率 | Beat Schedule Key |
|---------------------|-------------|----------|-------------------|
| `weather_v4_stable` | `import_data_task` | 30 分钟 | `import-weather-data` |
| `hydrology_daily_v1` | `hydrology_forecast_task` | 每日 01:00 | `daily-hydrology-forecast` |

### 5.4 异步任务状态生命周期

```
PENDING  →  STARTED  →  SUCCESS
    ↓           ↓
 RETRY  ←  FAILURE（超过 max_retries）
```

**前端轮询建议**：
- 提交任务后，每隔 5 秒轮询 `/api/tasks/<task_id>/`
- 状态变为 `SUCCESS` 或 `FAILURE` 后停止轮询
- 超过 1 小时仍未完成，提示用户联系管理员

### 5.5 异常处理策略

| 异常类型 | Celery 行为 | 建议处理 |
|----------|-------------|----------|
| `SoftTimeLimitExceeded` | 触发重试 | Worker 日志记录，前端显示"任务超时，正在重试" |
| 模型脚本异常 | 触发重试（max 3 次） | 第 3 次失败后标记 `FAILURE`，写入 `error_message` |
| Redis 连接断开 | 任务暂存，恢复后自动投递 | 监控 Redis 健康状态 |
| Worker 崩溃 | `ACKS_LATE=True` 保证任务不丢失 | 重启 Worker 后自动重新执行 |

### 5.6 验收标准

- [ ] Celery Beat 定时任务按预期频率执行
- [ ] 异步模式下 API 返回 `202`，不阻塞请求
- [ ] 前端轮询能正确跟踪任务到完成
- [ ] 任务失败时正确触发重试，最终失败时记录错误信息
- [ ] Worker 重启后未完成的任务自动重新执行

---

## 6. Phase 4：APScheduler 退役与清理

### 6.1 退役条件

全部满足以下条件的 **连续 7 天** 后，方可进入退役阶段：

1. Celery Beat 所有定时任务按预期执行，无失败
2. Celery Worker 处理的任务结果与 APScheduler 产出一致
3. 异步 API 模式运行稳定，无 500 错误
4. 团队成员确认 Celery 监控和日志满足日常运维需求

### 6.2 清理清单

| 清理项 | 说明 |
|--------|------|
| 移除 `django-apscheduler` 和 `APScheduler` 依赖 | `requirements.txt` |
| 删除 APScheduler 相关的 `DjangoJobStore` 配置 | `settings.py`（如有） |
| 删除 APScheduler 启动代码 | `apps.py` 或 `ready()` 方法中的 scheduler 启动 |
| 删除 `data/tasks.py` 中的 legacy job 函数 | `import_data_job`、`hydrology_forecast_job` |
| 删除 APScheduler 数据表 | `django_apscheduler_djangojob`、`django_apscheduler_djangojobexecution` |
| 更新文档 | 移除所有 APScheduler 相关说明 |

### 6.3 回滚预案

如 Celery 退役后出现问题，回滚步骤：

1. 重新安装依赖：`pip install django-apscheduler APScheduler`
2. 恢复 APScheduler 启动代码
3. 重启 Django 服务
4. 恢复 `HYDROLOGY_ASYNC_MODE = False`
5. Celery Worker 和 Beat 可暂时保留运行，待问题修复后再试退役

---

## 7. Phase 5：运维监控与告警

### 7.1 监控指标

| 指标 | 采集方式 | 告警阈值 |
|------|----------|----------|
| Celery Worker 存活 | Flower 或自定义心跳 | Worker 离线 > 5 分钟 |
| 任务队列堆积长度 | `redis-cli LLEN celery` | 堆积 > 10 条 |
| 任务执行成功率 | Celery 结果后端查询 | 成功率 < 95% |
| 任务平均执行时间 | Celery 结果后端查询 | 水文预测 > 30 分钟 |
| Redis 内存使用率 | `INFO memory` | 使用率 > 80% |
| PostgreSQL 连接数 | `pg_stat_activity` | 连接数 > 80% max_connections |

### 7.2 Flower（可选）

```bash
# 安装 Flower 用于 Celery 监控
venv\Scripts\python -m pip install flower

# 启动 Flower 监控面板
venv\Scripts\celery -A mysite flower --port=5555
# 访问 http://localhost:5555 查看任务队列、Worker 状态、任务历史
```

### 7.3 日志规范

| 组件 | 日志位置 | 保留策略 |
|------|----------|----------|
| Django | `logs/django.log` | 7 天轮转 |
| Celery Worker | 控制台 + 文件 | 7 天轮转 |
| Celery Beat | 控制台 + 文件 | 7 天轮转 |
| 模型脚本 | 通过 `print` 输出到 Worker 日志 | 随 Worker 日志保留 |

---

## 附录 A：环境搭建参考

### A.1 Windows 开发环境完整启动流程

```cmd
:: 1. 激活虚拟环境
cd C:\Users\AINUC\Desktop\Djanbo\djangotutorial
venv\Scripts\activate

:: 2. 确保 Redis 已启动（使用已安装的 Redis 服务）
redis-cli ping

:: 3. 确保 PostgreSQL (TimescaleDB) Docker 容器已启动
docker ps | findstr django-timescale

:: 4. 启动 Django 开发服务器（终端 1）
venv\Scripts\python manage.py runserver

:: 5. 启动 Celery Worker（终端 2）
venv\Scripts\celery -A mysite worker -l info -P solo

:: 6. 启动 Celery Beat（终端 3，如需要定时调度）
venv\Scripts\celery -A mysite beat -l info
```

### A.2 依赖去重后的 requirements.txt 建议

```
Django>=5.1,<5.2
djangorestframework>=3.15,<4.0
django-cors-headers>=4.4,<5.0
django-filter>=24.2,<25.0
drf-spectacular>=0.27,<1.0
django-apscheduler>=0.7,<1.0
APScheduler>=3.10,<4.0
pytz>=2024.1
psycopg2-binary>=2.9,<3.0
pandas>=2.0,<3.0
numpy>=2.0,<3.0

# ---- Celery async task infrastructure ----
celery>=5.3,<6.0
redis>=5.0,<6.0
django-celery-results>=2.5,<3.0
```

---

## 附录 B：常见问题排查

### B.1 Docker 拉取镜像失败

**现象**：`dialing registry-1.docker.io:443 no HTTPS proxy: connecting to ... i/o timeout`

**原因**：Windows 开发机网络环境无法直接访问 Docker Hub

**解决**：
- 不使用 Docker 运行 Redis，改用本地安装的 Redis 服务或 Memurai
- 如需在 Docker 中使用，配置 Docker Desktop 的 HTTP/HTTPS 代理

### B.2 Celery Worker 在 Windows 上启动失败

**现象**：`ValueError: not enough values to unpack` 或 prefork 相关错误

**原因**：Celery 默认使用 prefork 并发模型，在 Windows 上不可用

**解决**：启动 Worker 时显式指定 `-P solo` 或安装并使用 `eventlet`：
```bash
venv\Scripts\celery -A mysite worker -l info -P solo
```

### B.3 PostgreSQL 连接拒绝

**现象**：`connection to server at "127.0.0.1", port 15432 failed: Connection refused`

**原因**：
1. Docker 容器未启动
2. 容器已启动但 PostgreSQL 服务未就绪
3. 端口映射配置错误

**排查**：
```bash
docker ps --filter "name=django-timescale"
docker logs django-timescale
```

### B.4 API 返回 403 Forbidden

**现象**：已使用 `-u admin1:eeqs123456` 但 POST 仍返回 403

**排查步骤**：
1. 确认用户存在：`User.objects.filter(username='admin1').exists()`
2. 确认用户 `is_staff=True` 或 `is_superuser=True`
3. 检查 DRF 的 `DEFAULT_AUTHENTICATION_CLASSES` 是否包含 `BasicAuthentication`
4. 检查 `DEFAULT_PERMISSION_CLASSES` 是否为 `IsAuthenticated`
5. 如使用 SessionAuthentication，确保已登录（携带 CSRF Token）

### B.5 curl 命令在 Windows 下格式错误

**现象**：`curl: (5) Could not resolve proxy: POST`

**原因**：Windows cmd 下 `-X` 被误解析，或 `-d` 的 JSON 双引号未转义

**解决**：
```cmd
:: CMD 正确格式
curl -X POST http://localhost:8000/api/hydrology-runs/ -H "Content-Type: application/json" -u admin1:eeqs123456 -d "{\"target_date\": \"2026-07-08\"}"

:: 或使用 PowerShell
$headers = @{"Content-Type"="application/json"}
$cred = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("admin1:eeqs123456"))
$headers["Authorization"] = "Basic $cred"
Invoke-RestMethod -Uri "http://localhost:8000/api/hydrology-runs/" -Method POST -Headers $headers -Body '{"target_date": "2026-07-08"}'
```

---

## 附录 C：API 权限矩阵

### C.1 当前端点一览

| 端点 | 方法 | 当前权限 | 目标权限（Phase 2 后） |
|------|------|----------|----------------------|
| `/api/stations/` | GET | 匿名 | 匿名可读 |
| `/api/weatherdata/` | GET | 匿名 | 匿名可读（默认7天） |
| `/api/weather-daily-agg/` | GET | 匿名 | 匿名可读 |
| `/api/weather-hourly-agg/` | GET | 匿名 | 匿名可读 |
| `/api/hydrology-forecast-daily/` | GET | 匿名 | 匿名可读 |
| `/api/manual-data/` | POST | `IsAuthenticated` | `IsDataEntryOrAbove` |
| `/api/manual-data/<id>/void/` | POST | 创建者或 `is_staff` | `IsOwnerOrStaff` |
| `/api/hydrology-runs/` | GET | `IsAuthenticated` | `IsAuthenticated` |
| `/api/hydrology-runs/` | POST | `is_staff` | `IsAdminOrAnalyst` |
| `/api/tasks/<task_id>/` | GET | `IsAuthenticated` | `IsAdminOrAnalyst` |
| `/api/tiles/...` | GET | 匿名 | 匿名可读 |

### C.2 推荐的数据过滤策略

| 场景 | 实现建议 |
|------|----------|
| 普通用户查看 WeatherData | 保持默认 `DEFAULT_DAYS_BACK = 7`，可配置扩展 |
| 分析师查看全部历史 | 通过 query param `timestamp_after` 指定范围，无默认限制 |
| 按站点过滤 | `?station__name=HXC`（已有支持） |
| 按模型过滤 | `?model_name=lstm`（已有支持） |

---

## 修订记录

| 版本 | 日期 | 修订内容 | 修订人 |
|------|------|----------|--------|
| v1.0 | 2026-07-22 | 初始版本，覆盖 Celery 基础设施、权限控制 RBAC、APScheduler 迁移 | — |
