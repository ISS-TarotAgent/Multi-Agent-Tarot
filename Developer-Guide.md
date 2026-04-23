# Developer Guide — AI Tarot Multi-Agent System

> **当前状态（2026-04-21）**：Docker 完整链路可用。三条 LLM Agent（Clarifier / Draw / Synthesis）已接入真实 OpenAI 模型，Langfuse v2 可观测性已集成并验证可用。

---

## 目录

1. [快速启动](#1-快速启动)
2. [项目结构](#2-项目结构)
3. [架构分层](#3-架构分层)
4. [环境变量说明](#4-环境变量说明)
5. [Backend 开发指南](#5-backend-开发指南)
6. [Agent 开发指南](#6-agent-开发指南)
7. [Frontend 开发指南](#7-frontend-开发指南)
8. [LLMOps / Langfuse 可观测性](#8-llmops--langfuse-可观测性)
9. [安全层架构](#9-安全层架构)
10. [数据持久化链路](#10-数据持久化链路)
11. [测试指南](#11-测试指南)
12. [Evals（Promptfoo）](#12-evalsprompfoo)
13. [常见问题](#13-常见问题)

---

## 1. 快速启动

### 前置条件

- Docker Desktop（已启动）
- `backend/.env` 中填写了有效的 `OPENAI_API_KEY`（见[第 4 节](#4-环境变量说明)）

### 一键启动

```bash
cd Docker
docker compose up -d
```

首次启动约需 2-3 分钟（pip 安装依赖）。各服务就绪后：

| 服务 | 地址 |
|------|------|
| Frontend UI | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API 文档（Swagger）| http://localhost:8000/docs |
| Langfuse 可观测性面板 | http://localhost:3000 |

Langfuse 默认账号：`admin@tarot.local` / `admin123`

### 验证系统可用

```bash
# 发送一次真实 reading 请求
curl -X POST http://localhost:8000/api/v1/readings \
  -H "Content-Type: application/json" \
  -d '{"question":"我的事业发展方向是什么？","locale":"zh-CN"}'

# 期望响应：status=CLARIFYING（clarifier 判断问题需要澄清）
# 或       status=COMPLETED（clarifier 判断问题已清晰，直接完成完整解读）
# trace_summary.event_count 应 >= 3（说明 LLM 节点已真实执行）
```

### 停止 / 重置

```bash
docker compose down          # 停止，数据保留
docker compose down -v       # 停止并清除所有 volume（数据库重置）
```

---

## 2. 项目结构

```
project-root/
├── Developer-Guide.md          # 本文档
├── README.md
├── frontend/                   # React + TypeScript UI
│   ├── src/
│   │   ├── components/         # CardSpread, ResultPanel, ClarificationPanel...
│   │   ├── services/api.ts     # HTTP 调用封装 + 类型映射
│   │   └── types.ts            # 前端领域类型
│   └── Dockerfile
├── backend/                    # FastAPI + SQLAlchemy
│   ├── app/
│   │   ├── api/                # 路由、依赖注入（deps.py）
│   │   ├── application/        # 服务层（TarotReadingService / TarotSessionService）
│   │   ├── domain/             # 枚举、Repository 接口
│   │   ├── infrastructure/     # DB 实现、配置、可观测性 (WorkflowObserver)
│   │   └── schemas/            # API / Persistence / Workflow Schema
│   ├── alembic/                # 数据库迁移
│   └── pyproject.toml
├── agent/                      # LangGraph 工作流 + LLM Agents
│   ├── workflows/              # TarotReflectionWorkflow + build_llm_workflow()
│   ├── nodes/                  # 各工作流节点
│   ├── core/                   # ModelGateway / LLM Agents / Langfuse client / trace context
│   ├── schemas/                # Agent 层 Pydantic I/O 类型
│   ├── security/               # 输入安全检测器套件
│   └── tests/                  # Agent 单元测试
├── prompts/                    # Prompt 模板文件（.md），被 prompt_registry.py 加载
├── evals/promptfoo/            # Promptfoo eval 套件
├── Docker/
│   └── docker-compose.yml      # 全栈编排：postgres + backend + frontend + langfuse
└── docs/                       # 其他设计文档
```

---

## 3. 架构分层

```
┌─────────────────────────────────────┐
│           frontend/                 │  React + TypeScript
│  用户输入 → API 调用 → 结果展示         │  无状态；通过 REST API 与 backend 通信
└─────────────────┬───────────────────┘
                  │ REST API (JSON)
┌─────────────────▼───────────────────┐
│           backend/                  │  FastAPI + SQLAlchemy
│  HTTP API → Service → Repository    │  处理请求、持久化、返回响应
└─────────────────┬───────────────────┘
                  │ 调用 TarotReflectionWorkflow
┌─────────────────▼───────────────────┐
│            agent/                   │  LangGraph 工作流
│  workflows → nodes → security       │  执行 AI 管道，修改并返回 TarotWorkflowState
└─────────────────┬───────────────────┘
                  │ LLM 调用（OpenAI API）
┌─────────────────▼───────────────────┐
│  ModelGateway + Langfuse Tracing    │  统一模型调用 + 可观测性
└─────────────────────────────────────┘
```

**核心原则：**

- `backend/` 不直接调用任何单个 node，只调用 `TarotReflectionWorkflow` 上的三个方法
- `agent/` 不持久化任何数据，只负责修改并返回 `TarotWorkflowState`
- 两层通过 `TarotWorkflowState` 这一个对象传递所有信息
- `ModelGateway` 统一封装所有 LLM 调用，Langfuse generation 在此层自动记录

---

## 4. 环境变量说明

### backend/.env（必须创建，不提交 git）

```dotenv
# ── LLM 配置（必填）──────────────────────────────────────
OPENAI_API_KEY=sk-xxx...          # OpenAI API Key
OPENAI_MODEL=gpt-4o-mini          # 可选，默认 gpt-4o-mini

# ── 模型调用参数（可选）──────────────────────────────────
MODEL_TIMEOUT_SECONDS=30
MODEL_MAX_RETRIES=1

# ── 以下由 docker-compose.yml 自动注入，本地一般不需要手动填写 ──
# DATABASE_URL=postgresql+psycopg://...
# LANGFUSE_PUBLIC_KEY=pk-lf-tarot-dev
# LANGFUSE_SECRET_KEY=sk-lf-tarot-dev
# LANGFUSE_HOST=http://langfuse-server:3000
# LANGFUSE_ENABLED=true
```

### docker-compose 自动注入的环境变量

docker-compose.yml 中的 `backend` 服务已预先配置以下变量，**无需手动设置**：

| 变量 | 值 | 说明 |
|------|----|------|
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@postgres:5432/multi_agent_tarot` | PostgreSQL 连接串 |
| `LANGFUSE_ENABLED` | `true` | 启用 Langfuse 集成 |
| `LANGFUSE_PUBLIC_KEY` | `pk-lf-tarot-dev` | Langfuse 项目公钥（本地 dev 用） |
| `LANGFUSE_SECRET_KEY` | `sk-lf-tarot-dev` | Langfuse 项目私钥 |
| `LANGFUSE_HOST` | `http://langfuse-server:3000` | 指向本地 Langfuse 容器 |

> **重要**：Langfuse v2 SDK 读取 `LANGFUSE_HOST`，不是 `LANGFUSE_BASE_URL`。

### 更新 API Key 后的重建步骤

修改 `backend/.env` 后，必须 `--force-recreate` 才能生效（`restart` 不会重新读取 `env_file`）：

```bash
cd Docker
docker compose up -d --force-recreate backend
```

---

## 5. Backend 开发指南

### 5.1 目录结构

```
backend/app/
├── api/
│   ├── deps.py            # 依赖注入（TarotReadingService / TarotSessionService 的构造）
│   └── routes/            # readings.py / sessions.py / traces.py / health.py
├── application/
│   └── services/          # TarotReadingService / TarotSessionService（业务逻辑）
├── domain/
│   ├── enums/             # WorkflowStatus / RiskLevel / SpreadType 等
│   └── repositories/      # Repository 抽象接口
├── infrastructure/
│   ├── config/            # AppSettings（pydantic-settings，读取 .env）
│   ├── db/
│   │   ├── models.py      # SQLAlchemy ORM 模型
│   │   └── repositories/  # SqlAlchemy 实现（tarot_reading_repository.py）
│   └── observability/
│       └── workflow_observer.py  # LangfuseWorkflowObserver / NoOpWorkflowObserver
└── schemas/
    ├── api/               # CreateReadingRequest / ReadingResultResponse 等
    ├── persistence/       # ReadingRecord / SessionRecord / ReadingCardRecord
    └── workflow/          # TarotWorkflowState（backend ↔ agent 的唯一接口对象）
```

### 5.2 两条主 API 路径

| 路径 | 说明 |
|------|------|
| `POST /api/v1/readings` | 单步模式：一次提交问题，等待完整解读结果 |
| `POST /api/v1/sessions` + `POST /api/v1/sessions/{id}/question` + ... | 多步 Session 模式：支持多轮澄清 |

### 5.3 deps.py — 核心注入点

`backend/app/api/deps.py` 是 LLM workflow 是否启用的关键开关：

```python
# 有 OPENAI_API_KEY → 使用真实 LLM workflow
# 无 key             → 回退到内置 stub workflow（用于测试）
workflow = build_llm_workflow(observer=observer) if settings.openai_api_key else None
```

### 5.4 添加数据库迁移

```bash
# 在 backend/alembic/versions/ 下新建迁移文件（手动编写）
# 文件命名规范：YYYYMMDD_XXXX_<description>.py
# down_revision 指向上一个 migration 的 revision

# 迁移在 docker compose up 时自动执行（alembic upgrade head）
# 本地手动执行（需要先启动 postgres 容器）：
docker compose exec backend python -m alembic upgrade head
```

---

## 6. Agent 开发指南

### 6.1 工作流入口

backend 通过 `TarotReflectionWorkflow` 的三个方法驱动 agent：

| 方法 | 调用时机 | 执行的节点 |
|------|---------|-----------|
| `workflow.run(...)` | 单步 Reading | Pre-Input Security → Clarifier → Draw → Intermediate Security → Synthesis → Safety Guard |
| `workflow.evaluate_question(...)` | 多步 Session 问题评估 | Pre-Input Security + Clarifier |
| `workflow.continue_from_ready_state(state)` | 多步 Session 执行阶段 | Draw → Intermediate Security → Synthesis → Safety Guard |

### 6.2 工作流状态机

```
CREATED
  → QUESTION_RECEIVED   (evaluate_question 初始化)
  → CLARIFYING          (Clarifier 判断问题模糊)
  → READY_FOR_DRAW      (Clarifier 判断问题清晰)
  → DRAW_COMPLETED      (Draw 节点成功)
  → SYNTHESIS_COMPLETED (Synthesis 节点成功)
  → COMPLETED           (Safety Guard 通过)

任何节点失败 → SAFE_FALLBACK_RETURNED
```

### 6.3 节点一览

| 节点 | 文件 | 实现类型 | 状态 |
|------|------|---------|------|
| `pre_input_security` | `nodes/pre_input_security.py` | 规则引擎 | ✅ 可用 |
| `clarifier` | `nodes/clarifier.py` | LLM (`LLMClarifierAgent`) | ✅ 可用 |
| `draw_and_interpret` | `nodes/draw_and_interpret.py` | LLM (`LLMDrawAgent`) | ✅ 可用（抽牌随机性依赖 LLM） |
| `intermediate_security` | `nodes/intermediate_security.py` | 规则引擎 | ✅ 可用 |
| `synthesis` | 内联在 `orchestrator.py` | LLM (`LLMSynthesisAgent`) | ✅ 可用（无独立节点文件） |
| `safety_guard` | `nodes/safety_guard.py` | 规则引擎（关键词） | ✅ 可用 |

### 6.4 LLM Agent 实现

三个 LLM Agent 均在 `agent/core/llm_agents.py`：

```python
class LLMClarifierAgent:  # temperature=0.2，归一化 + 澄清判断
class LLMDrawAgent:       # temperature=1.0，抽牌 + 解读
class LLMSynthesisAgent:  # temperature=0.7，综合分析
```

通过 `build_llm_workflow()` 工厂函数统一构建并注入 backend：

```python
# agent/workflows/orchestrator.py
def build_llm_workflow(*, observer=None) -> TarotReflectionWorkflow:
    gateway = build_gateway_from_settings()   # 从 AppSettings 读取 API key / model
    return TarotReflectionWorkflow(
        clarifier_agent=LLMClarifierAgent(gateway),
        draw_agent=LLMDrawAgent(gateway),
        synthesis_agent=LLMSynthesisAgent(gateway),
        observer=observer,
    )
```

### 6.5 TarotWorkflowState — backend ↔ agent 的唯一接口

定义在 `backend/app/schemas/workflow/tarot_workflow_state.py`。agent 节点只做一件事：**读取 state → 执行逻辑 → 写入 state → 返回 state**。

关键字段分区：

| 区域 | 字段 | 写入节点 |
|------|------|---------|
| 基础标识 | `session_id`, `reading_id`, `raw_question`, `locale`, `status` | orchestrator 初始化 |
| 输入安全 | `input_safety_status`, `effective_question`, `input_sanitized` | `pre_input_security` |
| 澄清 | `clarification_output`, `normalized_question` | `clarifier` |
| 会话上下文 | `intent_tag`, `clarification_prompts`, `clarification_answers` | 由 backend 注入，供 `clarifier` 消费 |
| 抽牌 | `cards`, `draw_output` | `draw_and_interpret` |
| 综合 | `synthesis_output` | `synthesis` |
| 安全审查 | `safety_output` | `safety_guard` |
| 追踪 | `trace_events`（追加写） | 所有节点 |

### 6.6 Prompt 文件管理

所有 Prompt 集中存放在 `prompts/` 目录，通过 `agent/core/prompt_registry.py` 的 `load_prompt()` 加载：

```
prompts/
├── clarifier_init.md               # Clarifier 第一阶段（意图识别 + 澄清问题生成）
├── clarifier_finalize.md           # Clarifier 第二阶段（综合澄清回答，重构问题）
├── draw_interpret_system_prompt.md # Draw Agent（抽牌解读）
├── synthesis_system_prompt.md      # Synthesis Agent（综合分析）
└── security/
    └── safety_rewrite.md           # Safety Guard 中风险改写模板
```

修改 prompt 文件后**无需重启服务**，热重载自动生效。

### 6.7 新增节点的步骤

1. **定义 schema**：在 `agent/schemas/` 新建 Input/Output Pydantic 模型
2. **扩展 TarotWorkflowState**：在 `backend/app/schemas/workflow/tarot_workflow_state.py` 添加输出字段
3. **实现节点函数**：在 `agent/nodes/` 新建 `execute_xxx_step()` 函数
4. **注入 orchestrator**：在 `TarotReflectionWorkflow.__init__` 添加 agent 参数，在 `_build_*_graph()` 注册节点和边
5. **导出**：在 `agent/nodes/__init__.py` 导出节点函数
6. **编写测试**：在 `agent/tests/` 添加测试

### 6.8 Agent 协议接口（Protocol）

新 Agent 无需继承任何基类，只需满足对应 Protocol 的 `.run()` 签名：

```python
class ClarifierAgent(Protocol):
    def run(self, payload: ClarifierInput) -> ClarifierOutput: ...

class DrawAgent(Protocol):
    def run(self, payload: DrawInput) -> DrawOutput: ...

class SynthesisAgent(Protocol):
    def run(self, payload: SynthesisInput) -> SynthesisOutput: ...
```

---

## 7. Frontend 开发指南

### 7.1 技术栈

- React 18 + TypeScript
- Vite（开发服务器 + 构建）
- 纯 CSS（`src/index.css`）

### 7.2 目录结构

```
frontend/src/
├── App.tsx                 # 根组件，控制主流程状态机
├── types.ts                # 前端领域类型（TarotCardInsight / IntentTag 等）
├── services/api.ts         # REST 调用封装 + 后端类型映射（mapCard / mapReading）
├── components/
│   ├── QuestionInput.tsx   # 用户问题输入
│   ├── ClarificationPanel.tsx  # 澄清问题展示与回答
│   ├── CardSpread.tsx      # 三张牌布局展示（含 caution_note / reflection_prompt）
│   └── ResultPanel.tsx     # 综合结果（synthesis + 每张牌详情）
└── index.css               # 全局样式
```

### 7.3 关键数据流

```
用户输入问题
  → api.createReading()              POST /api/v1/readings
  → 若 status=CLARIFYING             展示 ClarificationPanel
  → 用户回答澄清问题（Session 路径）   POST /api/v1/sessions/{id}/clarifications
  → status=COMPLETED                 展示 CardSpread + ResultPanel
```

### 7.4 后端字段映射

`services/api.ts` 中的 `mapCard()` 负责把后端字段映射为前端类型：

```typescript
// BackendCard → TarotCardInsight
keywords:         c.keywords ?? []
reflectionPrompt: c.reflection_question ?? fallback
cautionNote:      c.caution_note ?? undefined
```

---

## 8. LLMOps / Langfuse 可观测性

### 8.1 架构概览

Langfuse 追踪采用 **Trace → Span → Generation** 三层结构，通过 Python `ContextVar` 在节点间传递当前 observation，无需显式传参。

```
Trace（一次 reading 操作）
  └── Span: pre_input_security
  └── Span: clarifier
  └── Span: draw_and_interpret
  │     └── Generation: draw_interpret_past     ← ModelGateway 自动记录
  │     └── Generation: draw_interpret_present
  │     └── Generation: draw_interpret_future
  └── Span: synthesis
        └── Generation: synthesis
```

### 8.2 核心文件

| 文件 | 职责 |
|------|------|
| `agent/core/langfuse_client.py` | Langfuse 客户端单例，从 `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` 初始化 |
| `agent/core/trace_context.py` | `ContextVar` 包装，线程安全地传递当前 observation |
| `backend/app/infrastructure/observability/workflow_observer.py` | `LangfuseWorkflowObserver`（有 key 时）/ `NoOpWorkflowObserver`（无 key 时）|
| `agent/core/model_gateway.py` | 每次 `run()` 调用自动向当前 span 附加 generation 记录 |

### 8.3 WorkflowObserver 使用方式

在 backend service 层通过 context manager 包裹工作流操作：

```python
with observer.observe_operation(
    name="tarot.reading.create",
    session_id=session_id,
    reading_id=reading_id,
    input_payload={"question": ...},
) as operation:
    state = workflow.run(...)
    operation.success(output={"status": state.status.value})
```

在节点层通过 `observe_step` 记录单个节点：

```python
with observer.observe_step(step_name="clarifier", as_type="chain") as obs:
    result = clarifier_agent.run(payload)
    obs.success(output={"intent_tag": result.intent_tag})
```

### 8.4 查看追踪数据

访问 http://localhost:3000，使用 `admin@tarot.local` / `admin123` 登录。每次 reading 请求都会在 `MultiAgentTarot` 项目下产生一条 Trace，包含完整的节点 Span 和 LLM Generation（含 token 用量、输入/输出内容）。

### 8.5 禁用 Langfuse

将 `LANGFUSE_ENABLED=false`（或删除该变量）设置后，系统自动回退到 `NoOpWorkflowObserver`，不影响功能。

---

## 9. 安全层架构

### 9.1 三层安全检查

| 位置 | 节点 | 检查对象 |
|------|------|---------|
| 最前 | `pre_input_security` | 用户原始输入 |
| 中间 | `intermediate_security` | Draw Agent 产出内容（防 agent 间注入） |
| 最后 | `safety_guard` | Synthesis 最终输出（关键词审查） |

### 9.2 输入安全决策

```
用户输入
  → detectors.py（5 个规则检测器）
      ├── detect_prompt_injection()
      ├── detect_secret_exfiltration()
      ├── detect_role_escalation()
      ├── detect_instruction_override()
      └── detect_suspicious_patterns()
  → pre_input_guard.py（汇总决策）
      ├── continue  → 输入安全，直接传递
      ├── rewrite   → 输入经清洗，传递净化后的内容
      └── block     → 输入危险，直接返回保护性回退
```

### 9.3 Safety Guard 风险等级

| 风险等级 | 代表关键词 | 处理方式 |
|---------|-----------|---------|
| HIGH | 自杀、自残、不想活、伤害他人、暴力 | `BLOCK_AND_FALLBACK`，替换全部内容 |
| MEDIUM | 投资、炒股、手术、医疗、离婚、官司 | `REWRITE`，追加免责声明 |
| LOW | 无命中 | `PASSTHROUGH`，原文输出 |

---

## 10. 数据持久化链路

### 主要数据表

| 表 | ORM 模型 | 说明 |
|----|---------|------|
| `sessions` | `SessionModel` | 会话信息，含 `intent_tag` / `clarification_prompts` / `clarification_answers` |
| `readings` | `ReadingModel` | 单次解读结果，含 `summary` / `action_advice` / `risk_level` |
| `reading_cards` | `ReadingCardModel` | 每张卡牌，含 `interpretation` / `reflection_question` / `caution_note` / `keywords` |
| `session_messages` | `SessionMessageModel` | 对话消息（原始问题、澄清问题等） |
| `safety_reviews` | `SafetyReviewModel` | 安全审查结果 |
| `trace_events` | `TraceEventModel` | 工作流节点执行记录 |

### 落库流程

agent 不直接操作数据库，backend repository 在拿到 `TarotWorkflowState` 后统一落库：

```
TarotWorkflowState
  ├── status, normalized_question, completed_at  → ReadingModel
  ├── cards (list[DrawCard])                     → ReadingCardModel（批量写入）
  ├── synthesis_output                           → ReadingModel.summary / action_advice
  ├── safety_output                              → SafetyReviewModel
  ├── intent_tag, clarification_prompts          → SessionModel
  └── trace_events                               → TraceEventModel（批量写入）
```

---

## 11. 测试指南

### 11.1 测试工具

| 工具 | 范围 | 命令 |
|------|------|------|
| pytest | Agent 单元测试 | `python -m pytest agent/tests/ -q` |
| pytest | Backend 单元 + 集成测试 | `cd backend && python -m pytest app/tests/ -q` |
| Promptfoo | 端到端工作流 eval | `npx promptfoo@latest eval -c evals/promptfoo/promptfooconfig.yaml` |

### 11.2 Agent 测试

Agent 单元测试无需真实 API key（使用 stub workflow）：

```bash
python -m pytest agent/tests/ -v
```

主要测试文件：

| 文件 | 覆盖内容 |
|------|---------|
| `test_pre_input_guard.py` | 输入安全决策逻辑 |
| `test_sanitizer.py` | 输入清洗 |
| `test_prompt_injection.py` | 注入检测 |
| `test_safety_guard_node.py` | 最终输出安全审查 |
| `test_security_orchestrator.py` | 安全流水线整体 |
| `test_workflow_stub.py` | 工作流完整链路（stub agents） |

### 11.3 Backend 集成测试

```bash
cd backend
python -m pytest app/tests/ -q
```

集成测试直接访问真实 PostgreSQL，不 mock 数据库（避免 mock/prod 行为不一致）。

---

## 12. Evals（Promptfoo）

`evals/promptfoo/` 提供基于 Promptfoo 的完整 eval 套件，**无需启动 HTTP 服务**（provider 在进程内调用工作流）。

### 运行前提

在 `backend/.env` 中填写有效的 `OPENAI_API_KEY`，然后：

```bash
# 仓库根目录
npx promptfoo@latest eval -c evals/promptfoo/promptfooconfig.yaml

# Windows 下如果 Python 解释器找不到
$env:PROMPTFOO_PYTHON = "python"
npx promptfoo@latest eval -c evals/promptfoo/promptfooconfig.yaml
```

### 测试场景覆盖

| 类别 | 验证内容 |
|------|---------|
| 正常流程 | `status=COMPLETED`, cards=3, `risk=LOW` |
| 澄清流程 | `clarification_required=True`, `status=CLARIFYING` |
| 前置安全拦截 | Prompt 注入、角色升级 → `SAFE_FALLBACK_RETURNED` |
| 输出安全兜底 | 自伤、暴力内容 → `HIGH + BLOCK_AND_FALLBACK` |
| 中风险改写 | 投资、医疗话题 → `COMPLETED + MEDIUM + REWRITE` |

---

## 13. 常见问题

### Q：如何验证 LLM 链路端到端可用？

```bash
curl -X POST http://localhost:8000/api/v1/readings \
  -H "Content-Type: application/json" \
  -d '{"question":"我最近感情运势如何？"}'
```

响应中 `trace_summary.event_count >= 3` 说明 LLM 节点真实执行了。如果 `event_count=1` 且 `status=SAFE_FALLBACK_RETURNED`，说明 API key 无效或 openai 包未安装。

### Q：更新 API Key 后系统没有生效？

`docker compose restart` 不会重新读取 `env_file`，必须用：

```bash
docker compose up -d --force-recreate backend
```

### Q：`LANGFUSE_HOST` 和 `LANGFUSE_BASE_URL` 的区别？

Langfuse v2 Python SDK 读取 `LANGFUSE_HOST`。`LANGFUSE_BASE_URL` 是 v3 的变量名，在 v2 SDK 下无效，会导致客户端连接到 `cloud.langfuse.com` 而非本地容器。本项目 docker-compose.yml 使用的是 `LANGFUSE_HOST`。

### Q：agent/ 里为什么有两套导入路径？

backend 包的根是 `app`（非 `backend.app`），内部模块用 `from app.xxx` 互相导入。agent 代码统一用 `from backend.app.xxx`。已通过 `agent/__init__.py` 在导入 agent 包时自动将 `backend/` 插入 `sys.path` 解决。

### Q：LangGraph 不可用时会怎样？

orchestrator 对 LangGraph 做了优雅降级。`import langgraph` 失败时，自动走纯 Python 的 `_run_*_without_langgraph()` 备用路径，执行逻辑完全一致。

### Q：Safety Guard 和 Protective Fallback 有什么区别？

| | Protective Fallback | Safety Guard |
|--|---------------------|-------------|
| **触发场景** | 任意节点执行失败 | 专门检查 Synthesis 输出的内容政策 |
| **内容来源** | 硬编码固定文案 | 基于 Synthesis 输出改写或替换 |
| **实现位置** | `orchestrator._protective_fallback()` | `nodes/safety_guard.execute_safety_guard_step()` |

### Q：如何在不启动 Docker 的情况下测试一次完整 LLM 调用？

```python
import sys, os
sys.path.insert(0, "backend")

# 加载 .env
from pathlib import Path
for line in Path("backend/.env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

from agent.workflows import build_llm_workflow
from backend.app.domain.enums import SpreadType

workflow = build_llm_workflow()
state = workflow.run(
    session_id="test-001",
    reading_id="reading-001",
    raw_question="我的事业发展方向是什么？",
    locale="zh-CN",
    spread_type=SpreadType.THREE_CARD_REFLECTION,
)
print(state.status, [c.card_name for c in state.cards])
```
