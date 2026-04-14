# Multi-Agent-Tarot 后端构建计划

## 1. 文档目标

本文档用于把当前仓库中已经写明的后端目标、架构意图、测试规范和工程约束，收敛成一份可执行的后端建设计划。

这份计划遵循两个原则：

- 先尊重当前磁盘事实，再给目标方案。
- 先完成课程项目需要的可运行主链路，再补强工程化能力，避免一次性过度设计。

## 2. 当前仓库真相

基于当前磁盘状态，项目已经不再是“文档先行、实现未落地”，而是“后端主链路已落地、LangGraph 已接入运行时”的阶段。

- `docs/03-API-Interface.md`、`docs/04-System-Architecture.md`、`docs/06-Backend-Contract-Freeze.md` 已经补齐，API、架构、状态机和最小表结构已有冻结文本。
- `backend/` 已有 FastAPI app、配置读取、结构化日志、SQLAlchemy/Alembic、`readings` / `sessions` / `traces` 路由、Pydantic schema、仓储层以及单元测试和集成测试。
- `agent/` 已有 Clarifier、Draw and Interpret、Synthesis、Safety Guard 四个最小 Agent 和 `agent/workflows/tarot_reflection_graph.py` 工作流实现，能够支撑同步 `readings` 与会话式 `sessions` 主链路。
- `evals/promptfoo/` 已有 Promptfoo provider 与配置，`Langfuse` observer 也已经以可选基础设施的形式接入。
- 阶段 4 已完成：`backend/pyproject.toml` 已声明 `langgraph>=1.0.8,<1.1`，`agent/workflows/tarot_reflection_graph.py` 已切换为真实 `StateGraph` 编排，`clarifier`、`draw_interpreter`、`synthesis`、`safety_guard`、`persistence` 都已收敛为图节点，并保留了现有 `TarotWorkflowState`、`WorkflowStatus`、`TraceEventPayload`、fallback 与 trace 事件名契约。
- `TarotReflectionWorkflow.evaluate_question()`、`run()` 与 `continue_from_ready_state()` 现在统一通过 LangGraph 适配层驱动；`backend/app/tests/unit/test_tarot_workflow.py` 与现有 integration/postgres 回归已覆盖澄清分支、checkpointer 接入、fallback、trace 数量与持久化一致性。
- 阶段 5 已补齐：`Langfuse` observer 已接入 `readings` / `sessions` 服务与工作流节点观测，结构化 JSON logs 已覆盖 HTTP 请求与 workflow trace，`PyTest` 与 `Promptfoo` 回归入口都已落地。
- `evals/promptfoo/tarot_backend_provider.py` 现会自动补入 `backend/.venv` 依赖路径，避免 Promptfoo 误用系统 Python 时缺失 `langgraph`；`backend/app/tests/conftest.py` 中的 PostgreSQL 容器回归也已改为“Docker 不可用时显式 skip”，让阶段 5 回归结果更稳定、更诚实。
- 阶段 6 已补齐：根目录 `docker-compose.yml`、`Docker/backend.Dockerfile`、`.github/workflows/backend-ci.yml`、`README.md` / `backend/README.md` 运行说明，以及 `docs/07-Backend-Delivery-Runbook.md` 排障文档都已落盘，团队成员现在可以直接按仓库内命令复现本地演示与 CI 验证路径。
- 当前剩余的主要建设项已收敛为真实 `Model Gateway` / OpenAI 调用链，而不再是 Docker Compose 或 GitHub Actions 交付底座。

## 3. 已冻结的后端约束

以下内容已经在仓库文档中表达得足够清楚，应作为本计划的真相源：

- 技术栈：Python 3.12、FastAPI、LangGraph、OpenAI、PostgreSQL、PyTest、Promptfoo、Langfuse、结构化 JSON Logs、Docker Compose、GitHub Actions。
- 产品主链路：用户提问 -> Clarifier -> Draw and Interpret -> Synthesis -> Safety Guard -> 最终输出。
- 后端职责：前后端数据交互、输入校验、会话管理、Agent 编排、存储、日志与可观测性。
- 非目标：复杂多租户权限系统、大规模高并发生产部署、自训练大模型。
- 工程约束：Prompt 独立管理、Agent 输出必须结构化、异常必须可追踪且可降级、测试必须覆盖主链路和安全边界。

## 4. 建设原则

### 4.1 KISS

- 首期只做课程项目真正需要的后端能力，不引入消息队列、事件总线、分布式任务系统、向量数据库等重型组件。
- 先用同步请求链路打通 MVP，再根据前端交互需要扩展为会话式流程。

### 4.2 YAGNI

- 首期不做用户体系、权限中心、管理后台、插件化 Agent 市场、多模型路由策略。
- `Tarot Knowledge Database` 首期不落成独立数据库服务，先用版本化静态知识文件承载牌义和卡牌元数据，后续确有编辑和检索需求再升级。

### 4.3 DRY

- 所有 Agent 的输入输出结构统一由 schema 定义。
- 所有模型调用统一经过 `Model Gateway`。
- 所有日志、trace、错误分类统一通过基础设施层收口。

### 4.4 SOLID

- API 层只负责协议和校验，不负责业务编排。
- Orchestrator 只负责任务推进、重试、降级和状态流转，不直接处理 HTTP 和数据库细节。
- Agent 只关心单一能力，不直接知道路由、数据库或前端页面。
- 存储、模型调用、可观测性通过抽象接口暴露，便于测试替换。

## 5. 目标架构

根据 `README.md`、开发文档和系统架构图，建议后端按以下分层落地。

| 层级 | 职责 | 首期落地方式 |
| --- | --- | --- |
| Presentation Layer | Web UI / Demo Interface | 由前端承担，不在本计划中实现 |
| Backend API Layer | 请求接入、参数校验、会话路由、错误码 | FastAPI 路由层 |
| Application Layer | Orchestrator、状态推进、重试、fallback | 应用服务层 + LangGraph 工作流适配 |
| Agent Layer | Clarifier、Draw、Synthesis、Safety Guard | 独立 Agent 模块，强制结构化 I/O |
| Knowledge Layer | Tarot card meanings / metadata | 首期使用版本化 YAML 或 JSON 资源文件 |
| Storage Layer | 会话、澄清、抽牌、结果、trace 摘要 | PostgreSQL |
| Support Layer | Model Gateway、config、logging、Langfuse | 基础设施层 |
| DevOps Layer | Docker、CI、env、migration、quality gates | Docker Compose + GitHub Actions |

## 6. 推荐目录结构

为兼容当前仓库已经规划好的根目录，建议保留 `backend/` 与 `agent/` 分离，只在各自内部补齐职责。

```text
backend/
├── pyproject.toml
├── .env.example
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── deps.py
│   │   ├── routes/
│   │   │   ├── health.py
│   │   │   ├── readings.py
│   │   │   ├── sessions.py
│   │   │   └── traces.py
│   ├── application/
│   │   ├── services/
│   │   ├── use_cases/
│   │   └── orchestrator_adapter.py
│   ├── domain/
│   │   ├── entities/
│   │   ├── enums/
│   │   └── repositories/
│   ├── schemas/
│   │   ├── api/
│   │   ├── workflow/
│   │   └── persistence/
│   ├── infrastructure/
│   │   ├── config/
│   │   ├── db/
│   │   ├── logging/
│   │   ├── model_gateway/
│   │   └── observability/
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── test_data/
agent/
├── workflows/
│   └── tarot_reflection_graph.py
├── agents/
│   ├── clarifier.py
│   ├── draw_interpreter.py
│   ├── synthesis.py
│   └── safety_guard.py
├── schemas/
│   ├── clarifier.py
│   ├── draw.py
│   ├── synthesis.py
│   └── safety.py
└── resources/
    └── tarot_cards.yaml
prompts/
├── clarifier/
├── draw_interpreter/
├── synthesis/
└── safety_guard/
evals/
├── promptfoo/
└── cases/
Docker/
├── backend.Dockerfile
└── postgres/
```

## 7. 核心领域模型

首期建议只建立支撑主流程所必需的领域对象。

- `Session`
  - 表示一次 Tarot Reflection 会话。
  - 关键字段：`id`、`status`、`created_at`、`updated_at`、`completed_at`。
- `UserQuestion`
  - 表示用户原始问题和规范化后的问题。
  - 关键字段：`session_id`、`raw_question`、`normalized_question`。
- `ClarificationTurn`
  - 表示澄清问题与用户回答。
  - 关键字段：`session_id`、`question_text`、`answer_text`、`turn_index`。
- `TarotReading`
  - 表示一次完整抽牌与解读过程。
  - 关键字段：`session_id`、`reading_status`、`summary`、`reflection_question`、`risk_level`。
- `DrawnCard`
  - 表示三张牌及其位置、正逆位、解释。
  - 关键字段：`reading_id`、`position`、`card_name`、`orientation`、`interpretation`。
- `SafetyReview`
  - 表示 Safety Guard 对结果的审查与修正。
  - 关键字段：`reading_id`、`risk_level`、`action_taken`、`review_notes`。
- `TraceEvent`
  - 表示结构化工作流节点日志。
  - 关键字段：`session_id`、`step_name`、`status`、`latency_ms`、`trace_payload`。

## 8. 工作流状态机

当前文档中存在一个需要先统一的点：

- 架构图更像“分层编排 + 知识源接入”。
- 测试文档更像“严格线性 pipeline”。

因此，后端开始编码前，应先冻结一版工作流状态机，建议首版采用线性主链路，降低复杂度。

```text
CREATED
-> QUESTION_RECEIVED
-> CLARIFYING
-> READY_FOR_DRAW
-> DRAW_COMPLETED
-> SYNTHESIS_COMPLETED
-> SAFETY_REVIEWED
-> COMPLETED

异常分支:
-> FAILED
-> SAFE_FALLBACK_RETURNED
```

对应规则如下：

- Clarifier 失败：退回原始问题继续执行，记录 warning trace。
- Draw 或 Synthesis 输出结构非法：先做一次修复性重试，仍失败则进入安全降级。
- Safety Guard 判定为高风险：重写或拒绝，并返回保护性结果。
- 所有步骤都必须产出结构化 trace。

## 9. API 建设方案

当前仓库没有现成接口契约，因此建议分两阶段冻结 API。

### 9.1 第一阶段：MVP 单次调用接口

目标是最快打通“问题输入到最终结果输出”的完整链路，便于后端先独立联调。

- `GET /api/v1/health`
  - 健康检查。
- `POST /api/v1/readings`
  - 输入：用户问题。
  - 输出：完整 Tarot Reflection 结果。
  - 行为：同步执行 Clarifier -> Draw -> Synthesis -> Safety Guard。
- `GET /api/v1/readings/{reading_id}`
  - 查询一次已完成或失败的结果。
- `GET /api/v1/readings/{reading_id}/trace`
  - 查询该次执行的 trace 摘要。

### 9.2 第二阶段：会话式接口

目标是支撑文档中已经规划的“澄清页面”和“历史记录页面”。

- `POST /api/v1/sessions`
  - 创建会话。
- `POST /api/v1/sessions/{session_id}/question`
  - 提交原始问题。
- `POST /api/v1/sessions/{session_id}/clarifications`
  - 提交澄清回答。
- `POST /api/v1/sessions/{session_id}/run`
  - 从当前状态继续执行到完成。
- `GET /api/v1/sessions/{session_id}`
  - 查看会话状态。
- `GET /api/v1/sessions/{session_id}/result`
  - 查看最终结果。
- `GET /api/v1/sessions/{session_id}/history`
  - 查询当前会话下的历史记录。

首期不建议一开始就直接实现第二阶段接口，否则会话状态、页面联动、异常恢复会同时放大复杂度。

## 10. Model Gateway 设计

`Model Gateway` 是后端必须优先落地的抽象层，否则测试和后续模型替换都会失控。

建议它至少统一以下能力：

- `generate_structured_output(prompt, schema, options)`
- provider 配置读取
- timeout
- retry
- 日志和 trace 埋点
- mock provider

首期只接 OpenAI，但接口必须设计成可替换。

首期不做的内容：

- 多模型智能路由
- 成本优化策略
- provider 级流量调度
- 流式输出

## 11. Tarot Knowledge 设计

虽然架构图中写的是 `Tarot Knowledge Database`，但首期不建议真的建成独立知识库服务。

建议首期方案：

- 把卡牌基础信息、正逆位含义、常见象征、适用反思问题做成 `agent/resources/tarot_cards.yaml`。
- Draw Agent 负责抽牌。
- Draw and Interpret Agent 从知识文件读取卡牌元数据，再结合模型生成解释。

这样做的原因：

- 课程项目首期没有复杂知识运营需求。
- 静态资源更容易版本管理、测试和回放。
- 避免把“用户会话存储”和“塔罗知识内容”耦合进同一套数据库模型。

升级条件：

- 出现多人协作编辑牌义内容的需求。
- 需要后台管理知识内容。
- 需要更复杂的检索、分类和内容版本控制。

## 12. 存储与迁移方案

PostgreSQL 只负责业务事实存储，不承载 Prompt 文件和完整原始日志。

建议首期表集合：

- `sessions`
- `session_messages`
- `readings`
- `reading_cards`
- `safety_reviews`
- `trace_events`

建议的数据归属：

- PostgreSQL：会话状态、澄清轮次、抽牌结果、最终输出、风险等级、trace 摘要。
- Prompt 文件：保存在 `prompts/`，以 Git 作为版本真相源。
- 详细运行日志：结构化 JSON logs。
- LLM 调用观测：Langfuse。

首期必须补齐：

- 数据库连接配置
- migration 工具
- 初始化脚本
- 本地开发数据种子

## 13. 测试计划

测试要求在开发文档中已经写得比较完整，后端计划应直接落到目录和执行项，而不是停留在口头规则。

### 13.1 单元测试

- 输入清洗
- schema 校验
- 风险等级判断
- 默认降级逻辑
- 配置读取
- 日志包装

### 13.2 集成测试

- 正常问题输入到最终结果输出
- 模糊问题触发澄清
- Agent 输出字段缺失后触发 fallback
- Safety Guard 判定高风险并重写

### 13.3 回归测试

- Promptfoo 用例覆盖正常输入、模糊输入、高风险输入、边界输入。
- 每次改 Prompt、改 schema、改工作流都必须重新跑回归。

### 13.4 CI 最小门禁

GitHub Actions 首期建议至少执行：

- 依赖安装
- 单元测试
- 集成测试
- schema 校验测试
- Promptfoo 核心回归

首期可暂缓：

- 覆盖率门禁
- 镜像发布
- 多环境部署流水线

## 14. 部署计划

项目文档已经明确“本地优先通过 Docker Compose 启动”，因此部署建设应先服务本地联调和课程演示。

首期交付应包含：

- `backend` Dockerfile
- `docker-compose.yml`
- `backend + postgresql` 本地组合启动
- `.env.example`
- 数据库初始化与迁移命令

可选增强项：

- 本地接入 Langfuse
- 单独的测试 compose 配置

暂不建议首期引入：

- Kubernetes
- 多环境 Helm
- 复杂 secret manager

## 15. 分阶段实施计划

基于当前仓库进度，阶段 0 到阶段 5 已完成；当前最需要补的是阶段 6 的交付底座。

建议将后续计划理解为“已完成阶段的状态标记 + 剩余阶段的执行顺序”，而不是重新从零开始。

### 阶段 0：冻结契约（已完成）

目标：把“计划意图”变成“可编码契约”。

交付物：

- 补全 `docs/03-API-Interface.md`
- 补全文字版系统架构说明
- 冻结一版工作流状态机
- 冻结一版 Pydantic schema 清单
- 冻结一版 PostgreSQL 最小表结构草案

### 阶段 1：搭脚手架（已完成）

目标：让后端目录具备可启动、可测试、可配置的基础形态。

交付物：

- `pyproject.toml`
- `.env.example`
- FastAPI app 工厂
- 基础配置模块
- 结构化日志模块
- 数据库连接和 migration 工具
- 基础健康检查接口

### 阶段 2：打通 MVP 主链路（已完成，并补齐 PostgreSQL 实链路验证）

目标：通过单次调用接口跑通完整 Tarot Reflection。

交付物：

- `POST /api/v1/readings`
- 等价工作流最小实现
- Clarifier、Draw and Interpret、Synthesis、Safety Guard 四个 Agent 最小实现
- Tarot knowledge 静态资源文件
- 结果持久化
- trace 摘要查询
- 基于真实 PostgreSQL 容器 + Alembic migration 的阶段 2 集成回归，用于验证 `/api/v1/readings`、持久化事实和 `/api/v1/readings/{reading_id}/trace` 查询链路

### 阶段 3：扩展会话能力（已完成基础版）

目标：支撑前端的澄清页面和历史记录页面。

交付物：

- session 相关接口
- clarification turn 存储
- 会话状态机
- 历史查询接口

### 阶段 4：补齐 LangGraph 支持（已完成）

目标：把当前自定义工作流升级为真实 LangGraph 编排，同时不破坏已经存在的 API、schema、持久化和 trace 契约。

交付物：

- `backend/pyproject.toml` 已补齐 `langgraph>=1.0.8,<1.1` 依赖，并锁定运行时版本范围。
- 已以现有 `TarotWorkflowState`、`WorkflowStatus` 和 `TraceEventPayload` 为边界，建立可编译的 LangGraph `StateGraph` 工作流入口。
- `clarifier`、`draw_interpreter`、`synthesis`、`safety_guard`、`persistence` 已收敛为稳定节点；“继续澄清 / 继续执行 / fallback / 终态返回”已用显式条件路由表达。
- 已保留现有修复性重试、fallback 和 trace 语义，LangGraph 接入后继续沿用原有错误码、事件名和状态转移约定。
- `evaluate_question()`、`run()` 与 `continue_from_ready_state()` 已提供 LangGraph 适配层；checkpoint 仅作为可选执行恢复能力，不替代 PostgreSQL 业务事实存储。
- 已新增 LangGraph 迁移回归测试，并通过现有 unit / integration / postgres 回归验证路径分支、状态恢复、trace 数量与 fallback 行为保持一致。

### 阶段 5：补齐观测与测试（已完成）

目标：把可维护性和可演示性补齐。

交付物：

- `backend/app/infrastructure/observability/workflow_observer.py` 已通过 `build_workflow_observer()` 接入 `Langfuse`，并由 `TarotReadingService`、`TarotSessionService` 与 `TarotWorkflowRunner` 统一产出 operation / step 观测。
- `backend/app/main.py` 与 `backend/app/infrastructure/logging/workflow_events.py` 已将 HTTP 请求、错误响应和 workflow trace 收口为结构化 JSON logs。
- `backend/app/tests/unit/` 与 `backend/app/tests/integration/` 已覆盖日志、observer、fallback、错误分类、会话状态流转和 PostgreSQL 持久化回归。
- `evals/promptfoo/promptfooconfig.yaml`、`evals/promptfoo/tarot_backend_provider.py` 与 `evals/promptfoo/README.md` 已形成可直接执行的 Promptfoo 回归套件，并自动补齐 `backend/.venv` 依赖路径。
- PostgreSQL 容器回归在 Docker daemon 不可用时会显式 skip，而不是把整个 PyTest 套件打成错误，保证阶段 5 的演示与本地回归出口稳定可解释。

### 阶段 6：补齐交付底座（已完成）

目标：保证团队成员能稳定复现和演示。

交付物：

- 根目录 `docker-compose.yml`，用于编排 `backend + PostgreSQL` 本地演示环境。
- `Docker/backend.Dockerfile`，用于构建后端镜像，并在启动时自动执行 Alembic migration 后拉起 `uvicorn`。
- `.github/workflows/backend-ci.yml`，用于执行 Python 3.12 + Node 20 环境下的 `pytest` 与 Promptfoo 核心回归。
- `README.md` 与 `backend/README.md` 中的后端运行说明，覆盖 Docker Compose 与本地直跑两条路径。
- `docs/07-Backend-Delivery-Runbook.md`，收口阶段 6 的常见问题、验证命令与 CI 对齐方式。

## 16. 风险与应对

### 16.1 文档意图与实现边界不一致

风险：

- 架构图、测试文档、API 文档三者可能继续分叉。

应对：

- 阶段 0 先冻结接口、状态机和 schema，不冻结就不进入编码。

### 16.2 Agent 输出不稳定

风险：

- LLM 返回自然语言、字段缺失或 JSON 非法，导致下游崩溃。

应对：

- 所有 Agent 输出强制 schema 校验。
- Orchestrator 内置一次修复性重试和统一降级。

### 16.3 会话流过早复杂化

风险：

- 一开始就做多轮澄清、历史、页面状态同步，导致后端状态管理失控。

应对：

- 先做单次调用 MVP，再演进为会话式接口。

### 16.4 可观测性缺失导致难以演示

风险：

- 课程项目最怕“能跑但讲不清”，没有 trace 和结构化日志就无法解释系统行为。

应对：

- trace 和 JSON logs 不是附加项，而是主链路交付项。

### 16.5 过度设计知识库

风险：

- 过早把塔罗知识源做成独立数据库或检索系统，成本高且收益低。

应对：

- 首期静态资源化，后期按需求升级。

## 17. 首批任务建议

建议把第一批 Jira 任务控制在以下范围内：

1. 补全 API 契约文档。
2. 冻结工作流状态机和 schema 清单。
3. 建立 `backend/` Python 工程与基础配置。
4. 建立 FastAPI app 与健康检查接口。
5. 建立 PostgreSQL 连接和 migration 基础设施。
6. 建立 `Model Gateway` 抽象与 OpenAI 适配器。
7. 建立 Clarifier、Draw and Interpret、Synthesis、Safety Guard 最小实现。
8. 建立 `agent/resources/tarot_cards.yaml`。
9. 建立 `POST /api/v1/readings` MVP 接口。
10. 建立最小单元测试、集成测试和 Promptfoo 回归。
11. 建立 Docker Compose 和 `.env.example`。
12. 建立 GitHub Actions 最小 CI。

## 18. 完成标准

当以下条件满足时，可以认为后端首期建设完成：

- 后端可通过 Docker Compose 在本地启动。
- 能通过一个 API 请求完成 Tarot Reflection 主链路。
- 主工作流已由 LangGraph 驱动，且不破坏现有 API、状态机、trace 事件名和持久化契约。
- Clarifier、Draw、Synthesis、Safety Guard 均有结构化输入输出。
- PostgreSQL 中可查到会话、结果和 trace 摘要。
- PostgreSQL 继续作为业务事实真相源；若使用 LangGraph checkpoint，也只承担执行恢复，不替代业务表。
- Langfuse 或结构化日志中可追踪完整调用过程。
- PyTest 和 Promptfoo 核心用例可在 CI 中稳定通过。
- API 契约、架构文档和运行说明与实际代码保持一致。

## 19. 结论

当前项目最缺的已经不是“有没有后端骨架”，也不是“LangGraph 是否真正进入运行时主链路”，因为这部分已经落地。

因此，正确的后端后续建设顺序应调整为：

1. 保持现有 API、schema 和 PostgreSQL 事实源不变。
2. 维持当前 Langfuse、结构化日志、PyTest、Promptfoo 与 fallback 回归闭环，不再回退阶段 5 已完成的能力。
3. 阶段 6 已完成，Docker Compose、CI、运行说明与排障 runbook 已经到位。
4. 下一步优先补真实 `Model Gateway` / OpenAI 调用链与演示级运维文档。

这个顺序最符合当前仓库的真实状态，也能把对现有 `readings` / `sessions` 接口与测试的回归风险压到最低。
