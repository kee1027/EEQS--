# Windows 环境 Redis 部署指南（免 Docker）

> 适用场景：开发环境无法使用 Docker、无外网代理、需快速启动 Redis 服务

---

## 方案一：下载预编译 Redis for Windows（推荐，最稳定）

### 步骤 1：下载 Redis 压缩包

访问以下任一地址下载 Windows 版 Redis（zip 格式）：

- **官方活跃维护版**（推荐）：
  - GitHub: https://github.com/tporadowski/redis/releases
  - 下载 `Redis-x64-<版本号>.zip` 文件

- **备用镜像**（如果 GitHub 访问慢）：
  - https://github.com/microsoftarchive/redis/releases
  - 下载 `Redis-x64-3.0.504.zip`（较老但稳定）

### 步骤 2：解压到项目目录

将下载的 zip 解压到项目内，例如：

```
C:\Users\AINUC\Desktop\Djanbo\djangotutorial\
├── venv\
├── data\
├── mysite\
├── redis\               <-- 解压到这里
│   ├── redis-server.exe
│   ├── redis-cli.exe
│   └── redis.windows.conf
└── manage.py
```

### 步骤 3：启动 Redis 服务器

```bash
cd C:\Users\AINUC\Desktop\Djanbo\djangotutorial

# 启动 Redis（使用默认配置）
redis\redis-server.exe

# 或者使用自定义配置文件
redis\redis-server.exe redis\redis.windows.conf
```

启动成功后，你会看到类似输出：

```
[XXXXX] XX XXX XX:XX:XX.XXX # Server started, Redis version x.x.x
[XXXXX] XX XXX XX:XX:XX.XXX * Ready to accept connections
```

> **保持窗口运行**，Redis 服务将一直可用。

### 步骤 4：验证连接

打开另一个终端窗口：

```bash
cd C:\Users\AINUC\Desktop\Djanbo\djangotutorial
redis\redis-cli.exe ping
```

返回 `PONG` 即表示 Redis 运行正常。

### 步骤 5：在 Django 中验证 Celery

```bash
# 先确保依赖已安装
venv\Scripts\python -m pip install celery redis django-celery-results

# 运行 Django 检查
venv\Scripts\python manage.py check

# 测试 Celery 导入
venv\Scripts\python -c "from mysite.celery import app; print('Celery app:', app.main)"
```

### 步骤 6：启动 Celery Worker（测试）

```bash
# 方式 A：solo 模式（Windows 推荐，单进程）
venv\Scripts\celery -A mysite worker -l info -P solo

# 方式 B：threads 模式（多线程）
venv\Scripts\celery -A mysite worker -l info -P threads
```

### 步骤 7：启动 Celery Beat（定时调度，可选）

```bash
# 打开另一个终端
venv\Scripts\celery -A mysite beat -l info
```

---

## 方案二：使用 Memurai（Redis 的 Windows 原生替代品）

Memurai 是 Redis 的 Windows 兼容版本，有免费开发版：

1. 访问 https://www.memurai.com/
2. 下载 Memurai 免费开发版
3. 安装后，Memurai 会作为 Windows 服务自动运行
4. 无需额外配置，直接启动 Celery Worker 即可

---

## 方案三：fakeredis（纯 Python，仅适合开发/测试）

如果你**完全不想下载任何外部程序**，可以用纯 Python 的 Redis 模拟库 `fakeredis`。

> ⚠️ **注意**：fakeredis 仅适合**开发测试**，不适合生产环境。且 Celery Worker 在这种模式下实际上不会真正异步执行（任务会在调用线程同步运行）。

### 安装

```bash
venv\Scripts\python -m pip install fakeredis[lua]
```

### 修改配置（仅开发测试用）

在 `mysite/settings.py` 中，将 Celery 配置改为同步模式：

```python
# 开发测试：不启动 Redis，任务在当前线程同步执行
CELERY_TASK_ALWAYS_EAGER = True
CELERY_RESULT_BACKEND = "django-db"
# 注意：此时 CELERY_BROKER_URL 实际上不会被使用，但仍需保留
```

这样你可以运行测试和开发代码，但**没有真正的异步能力**。适合先写代码、后配环境。

---

## 方案对比

| 方案 | 需要下载 | 异步执行 | 适用场景 | 推荐度 |
|------|----------|----------|----------|--------|
| Redis for Windows | 需下载 zip | ✅ 完全异步 | 开发 + 生产 | ⭐⭐⭐⭐⭐ |
| Memurai | 需安装 msi | ✅ 完全异步 | 开发（最简单） | ⭐⭐⭐⭐ |
| fakeredis | 仅 pip install | ❌ 同步模拟 | 临时开发/测试 | ⭐⭐ |

---

## 常见问题

### Q: Redis 窗口关了服务就停了？

**A**: 是的，开发环境这是正常行为。如需后台运行：

```bash
# 方式 1：使用 start 命令后台运行
start /B redis\redis-server.exe

# 方式 2：注册为 Windows 服务（需要管理员权限）
redis\redis-server.exe --service-install redis\redis.windows.conf --service-name RedisCelery
redis\redis-server.exe --service-start
```

### Q: 端口 6379 被占用？

**A**: 修改 `redis.windows.conf` 中的 `port 6379` 为其他端口，同时更新 `settings.py` 中的 `CELERY_BROKER_URL`。

### Q: 我不想一直开着 Redis 窗口？

**A**: 使用方案二（Memurai）它会作为系统服务自动运行；或使用上述 `--service-install` 方式注册 Redis 为服务。

### Q: 能否直接用 PostgreSQL 替代 Redis 做 broker？

**A**: 技术上可行但不推荐。Celery 官方支持 Redis/RabbitMQ/SQS 等作为 broker，PostgreSQL 不是推荐 broker。保持 Redis + PostgreSQL 的分工是最佳实践。
