# Backend Delivery Runbook

本文档是阶段 6 的交付 runbook，目标是让团队成员在不猜测环境细节的前提下，稳定完成本地启动、演示与回归验证。

## 1. 交付物范围

阶段 6 当前包含以下落地文件：

- `docker-compose.yml`
- `Docker/backend.Dockerfile`
- `.github/workflows/backend-ci.yml`
- `README.md`
- `backend/README.md`

## 2. 最短演示路径

在仓库根目录执行：

```bash
docker compose up --build
```

当两个服务都启动后，可用以下命令验证：

```powershell
Invoke-RestMethod -Method Get -Uri 'http://127.0.0.1:8000/api/v1/health'
```

预期看到：

- `status=ok`
- `service=multi-agent-tarot-backend`
- `environment=docker`

然后可以直接验证主链路：

```powershell
$body = @{
  question = '最近在工作选择上很犹豫，我应该继续坚持当前方向吗？'
  locale = 'zh-CN'
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri 'http://127.0.0.1:8000/api/v1/readings' `
  -ContentType 'application/json' `
  -Body $body
```

预期看到：

- `status=COMPLETED`
- `cards` 数量为 3
- `trace_summary.event_count` 大于等于 8

停止环境：

```bash
docker compose down
```

如果要一并清空 PostgreSQL volume：

```bash
docker compose down -v
```

## 3. 本地开发路径

如果不走容器，先在 `backend/` 初始化虚拟环境：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

再准备 PostgreSQL：

```powershell
docker run --rm -d --name multi-agent-tarot-postgres `
  -e POSTGRES_DB=multi_agent_tarot `
  -e POSTGRES_USER=postgres `
  -e POSTGRES_PASSWORD=postgres `
  -p 5432:5432 `
  postgres:16-alpine
```

然后执行：

```powershell
alembic upgrade head
uvicorn app.main:app --reload
```

## 4. 回归命令

后端测试：

```bash
cd backend
python -m pytest app/tests -q
```

Promptfoo 回归：

```bash
npx promptfoo@latest eval -c evals/promptfoo/promptfooconfig.yaml
```

如果 Promptfoo 在 Windows 上错误地使用了系统 Python，可显式指定解释器：

```powershell
$env:PROMPTFOO_PYTHON = ".\\backend\\.venv\\Scripts\\python.exe"
npx promptfoo@latest eval -c evals/promptfoo/promptfooconfig.yaml
```

## 5. GitHub Actions 对齐方式

`.github/workflows/backend-ci.yml` 当前执行顺序是：

1. `actions/checkout`
2. `actions/setup-python` 安装 Python 3.12
3. `actions/setup-node` 安装 Node 20
4. 在 `backend/` 下执行 `python -m pip install -e ".[dev]"`
5. 运行 `python -m pytest app/tests -q`
6. 运行 `npx promptfoo@latest eval -c evals/promptfoo/promptfooconfig.yaml`

这意味着本地如果想复现 CI，最接近的路径就是同样先装 Python 依赖，再跑 `pytest` 和 `Promptfoo`，而不是只验证接口能启动。

## 6. 常见问题排查

### 6.1 `docker compose up --build` 卡在 backend 启动

先看 PostgreSQL 是否健康：

```bash
docker compose ps
docker compose logs postgres
docker compose logs backend
```

如果 backend 日志里出现数据库连接错误，优先确认：

- `postgres` 服务是否已经 `healthy`
- `DATABASE_URL` 是否仍然指向 `localhost`
- 本机 5432 端口是否被其他 PostgreSQL 实例占用

### 6.2 8000 或 5432 端口被占用

报错通常表现为 bind 失败。处理方式：

- 停掉当前占用端口的本地服务
- 或临时修改 `docker-compose.yml` 的 host 端口映射
- 如果改了 host 端口，测试命令也要同步改成新的地址

### 6.3 Alembic migration 失败

先确认当前使用的 `DATABASE_URL`：

```powershell
Get-Content backend/.env.example
```

容器内默认应指向：

```text
postgresql+psycopg://postgres:postgres@postgres:5432/multi_agent_tarot
```

本地直跑时默认应指向：

```text
postgresql+psycopg://postgres:postgres@localhost:5432/multi_agent_tarot
```

### 6.4 Promptfoo 找不到 `langgraph` 或 `fastapi`

这是解释器错位问题，不是 Promptfoo 用例本身失败。优先检查：

- 当前 shell 是否已经激活 `backend/.venv`
- 是否设置了 `PROMPTFOO_PYTHON`
- `python -c "import fastapi, langgraph"` 是否能在当前解释器下通过

### 6.5 看不到 Langfuse trace

当前仓库默认：

```text
LANGFUSE_ENABLED=false
```

如果要启用 Langfuse，需要在 `.env` 中补齐：

- `LANGFUSE_ENABLED=true`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_BASE_URL`

如果这些值未配置，系统仍会正常返回结果，但只会保留本地结构化日志，不会向 Langfuse 上报。

