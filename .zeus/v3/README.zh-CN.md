# ZeusOpen v3

> 面向 AI 驱动软件工程的生产级多 Agent 框架。

ZeusOpen v3 是对 v2 执行引擎的彻底重写，核心目标包括：
- **以数据库为中心的状态管理**（SQLite/PostgreSQL），取代基于文件锁的 `task.json` 修改
- **队列-工作器分离**，支持水平扩展
- **实时可观测性**，通过 SSE 和 Vue 3 仪表板实现
- **Agent 结果协议（ARP）** — 结构化的 `zeus-result.json` 作为唯一可信来源
- **多容器部署**，支持 Docker Compose 和 Redis

---

## 快速开始（本地）

### 1. 安装依赖

```bash
cd .zeus/v3/scripts
pip install -r requirements.txt
```

所需包（当前环境已安装）：
- `fastapi`, `uvicorn`, `sse-starlette`
- `sqlalchemy[asyncio]`, `aiosqlite`, `asyncpg`, `alembic`
- `redis`, `pydantic-settings`
- `opentelemetry-api`, `opentelemetry-sdk`（可选，用于链路追踪）

### 2. 初始化数据库

```bash
python -c "from db.engine import make_async_engine; from db.models import Base; import asyncio; e=make_async_engine('sqlite+aiosqlite:///./.zeus/v3/state.db'); asyncio.run(e.begin().__aenter__().conn.run_sync(Base.metadata.create_all))"
```

或者直接运行 `run.py` — 首次启动时会自动创建表结构。

### 3. 运行完整流水线（调度器 + 工作器）

```bash
python run.py --project-root . --max-workers 3
```

执行流程：
1. 将 `task.json` 导入数据库
2. 启动工作器池
3. 运行调度器循环，直到所有任务完成
4. 输出执行摘要

### 4. 启动 API 服务器 + 仪表板

```bash
python run.py --mode serve --project-root . --host 0.0.0.0 --port 8000
```

在浏览器中打开 http://127.0.0.1:8000/dashboard 。

---

## CLI 模式

`run.py` 通过 `--mode` 支持四种执行模式：

| 模式 | 说明 |
|------|------|
| `combined`（默认） | 在同一个进程中运行调度器 + 工作器池 |
| `scheduler` | 仅运行调度循环（将就绪任务入队） |
| `worker` | 仅运行工作器池（消费队列） |
| `serve` | 启动 FastAPI 服务器 + SSE 流 + 仪表板 |

### 多进程示例（内存队列）

终端 1：
```bash
python run.py --mode scheduler
```

终端 2：
```bash
python run.py --mode worker --max-workers 2
```

### 多节点示例（Redis 队列）

终端 1（调度器）：
```bash
python run.py --mode scheduler --queue-backend redis --redis-url redis://localhost:6379/0
```

终端 2-3（工作器）：
```bash
python run.py --mode worker --max-workers 3 --queue-backend redis --redis-url redis://localhost:6379/0
```

---

## 任务配置

任务定义在 `.zeus/v3/task.json`（静态计划）中，运行时会导入数据库。

示例任务：

```json
{
  "version": "v3",
  "updated_at": "2026-04-13T00:00:00Z",
  "tasks": [
    {
      "id": "T-101",
      "title": "Add metrics API",
      "description": "Implement /metrics/summary endpoint",
      "type": "feat",
      "wave": 1,
      "depends_on": [],
      "files": [".zeus/v3/scripts/api/server.py"]
    }
  ]
}
```

执行 `python run.py --import-only` 可仅导入不执行。

---

## 工作空间后端

可选择 Agent 工作空间的创建方式：

| 后端 | 配置 | 适用场景 |
|------|------|----------|
| `copytree`（默认） | `"workspace": {"backend": "copytree"}` | 完整复制项目；简单安全 |
| `git_worktree` | `"workspace": {"backend": "git_worktree"}` | 通过 `git worktree` 零拷贝；需要 git 仓库 |

---

## API 端点

基础地址：`http://127.0.0.1:8000`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/tasks` | 列出所有任务（可通过 `?status=` 或 `?wave=` 过滤） |
| GET | `/tasks/{id}` | 获取单个任务详情 |
| GET | `/events` | 查询事件日志（分页） |
| GET | `/events/stream` | **SSE** 实时事件流 |
| GET | `/metrics/summary` | 高层指标 + 通过率 |
| GET | `/metrics/tasks` | 每个任务的耗时和状态 |
| GET | `/metrics/bottleneck` | 最慢的 Top-N 任务 |
| GET | `/metrics/blocked` | 因失败/隔离而被阻塞的依赖链 |
| GET | `/dashboard/` | Vue 3 单页应用仪表板 |

---

## Docker Compose 部署

```bash
cd .zeus/v3
docker compose up --build
```

服务组成：
- `redis` — 共享任务队列
- `zeus-api` — FastAPI，暴露端口 `8000`
- `zeus-scheduler` — 调度器循环
- `zeus-worker` — 2 副本的工作器池

扩展工作器数量：
```bash
docker compose up --scale zeus-worker=4
```

---

## Kubernetes 部署

```bash
cd .zeus/v3/k8s
kubectl apply -f namespace.yaml
kubectl apply -f pvc.yaml
kubectl apply -f redis.yaml
kubectl apply -f zeus-api.yaml
kubectl apply -f zeus-scheduler.yaml
kubectl apply -f zeus-worker.yaml
```

组件说明：
- `redis` — 集群内 Redis 服务
- `zeus-api` — LoadBalancer Service，端口 80
- `zeus-scheduler` — 单例调度器 Deployment
- `zeus-worker` — 带 HPA 的 Deployment（2-10 副本，CPU 70%）
- `zeus-state-pvc` — 共享 SQLite 存储卷（ReadWriteMany）

> **注意：** `ReadWriteMany` 需要支持该模式的 CSI 驱动（例如 NFS、EFS、Azure Files）。对于单节点集群（kind/minikube），请使用 `hostPath` 或切换为单副本 SQLite 方案。

---

## 调度器模式

在 `.zeus/v3/config.json` 的 `subagent.dispatcher` 下配置：

| 调度器 | 行为 |
|--------|------|
| `mock` | 立即写入一个 stub `zeus-result.json` |
| `kimi` | 启动 `kimi --prompt ... --work-dir ...` |
| `claude` | 启动 `claude -p ... --cwd ...` |
| `docker` | 在 Docker 容器中运行，挂载可写工作空间 |
| `auto` | 自动检测 `kimi` → `claude` → 回退到 `mock` |

Docker 调度器配置示例：

```json
{
  "subagent": {
    "dispatcher": "docker",
    "docker": {
      "image": "python:3.13-slim",
      "memory_limit": "512m",
      "cpu_limit": "1.5"
    }
  }
}
```

---

## OpenTelemetry 链路追踪

启用控制台链路导出：

```bash
python run.py --trace
```

每次调度器运行会产生一个 `scheduler-run` span，包含子级 `scheduler-tick` span。

---

## 开发

### 构建仪表板

```bash
cd .zeus/v3/web
npm install
npm run build
```

构建结果输出到 `.zeus/v3/scripts/api/static/`，由 FastAPI 在 `/dashboard/` 下提供访问。

### 运行测试

```bash
cd .zeus/v3/scripts
python -m pytest tests/ -v
```

---

## 架构

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  task.json  │────▶│  导入器       │────▶│  状态数据库   │
│  (静态)      │     │              │     │(SQLite/PG)  │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                 │
    ┌─────────────┐    ┌─────────────┐    ┌────▼──────┐
    │   工作器    │◄───│   任务队列   │◄───│  调度器    │
    │   池        │    │(内存/Redis/ │    │           │
    └──────┬──────┘    │ SQLite)     │    └───────────┘
           │            └─────────────┘
           ▼
    ┌─────────────┐
    │  工作空间    │────▶ zeus-result.json
    │  管理器      │
    └─────────────┘
           │
           ▼
    ┌─────────────┐
    │   调度器     │
    │(mock/kimi/  │
    │claude/docker)│
    └─────────────┘
```

---

## 从 v2 迁移

1. 将 v2 的 `task.json` 复制到 `.zeus/v3/task.json`
2. 运行 `python run.py --import-only` 将运行时状态迁移到 v3 数据库
3. 启动调度器 / 工作器或 Docker Compose 集群
4. 打开 `/dashboard` 进行实时监控
