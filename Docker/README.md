# Docker

存放阶段 6 的容器化交付文件。

- `backend.Dockerfile`: 构建 FastAPI 后端镜像，启动时自动执行 Alembic migration 并拉起 `uvicorn`
- 根目录 `docker-compose.yml`: 编排 `backend + PostgreSQL` 的本地演示环境
