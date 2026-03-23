# Backend

基于 **Python 3.12 + FastAPI** 的后端服务骨架，负责承接前端请求、调度多
Agent 工作流、接入 Model Gateway 与 MySQL、输出可观测性日志。

目录结构：

- `app/main.py`：FastAPI 入口，注册 v1 路由与启动/关闭钩子（TODO）。
- `app/api/`：对外接口，`v1/tarot.py`、`v1/health.py` 仅含 TODO。
- `app/api/deps.py`：数据库与工作流依赖占位，等待实现。
- `app/models/dto.py`：API 用 Pydantic 模型骨架。
- `app/services/`：Orchestrator & SessionStorage 服务层占位。
- `app/core/`：配置、日志、ModelGateway 装配的基础设施。
- `app/db/`：SQLAlchemy/Alembic 相关结构。
- `app/tests/`：PyTest 占位，提醒后续补集成测试。

所有文件目前只有结构和 TODO，实际逻辑由后续开发者补齐。
