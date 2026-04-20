# Agent Developer Guide

本文档面向初次接触本项目的开发者，说明 `agent/` 目录的整体结构、各层职责、与 `backend/` 的联动方式，以及新增节点或 Agent 实现时需要遵守的规范。

---

## 目录

1. [项目整体分层](#1-项目整体分层)
2. [目录结构速览](#2-目录结构速览)
3. [TarotWorkflowState：唯一的联动接口](#3-tarotworkflowstate唯一的联动接口)
4. [两条主工作流](#4-两条主工作流)
   - [4.1 单步 Reading](#41-单步-reading)
   - [4.2 多步 Session（含澄清）](#42-多步-session含澄清)
5. [工作流状态机](#5-工作流状态机)
6. [节点执行机制](#6-节点执行机制)
   - [6.1 Question Graph（问题评估阶段）](#61-question-graph问题评估阶段)
   - [6.2 Ready-State Graph（主解读阶段）](#62-ready-state-graph主解读阶段)
   - [6.3 安全链路](#63-安全链路)
7. [各节点详解](#7-各节点详解)
8. [Agent 协议接口（Protocol）](#8-agent-协议接口protocol)
9. [如何替换 Default Agent 实现](#9-如何替换-default-agent-实现)
10. [Trace Events 机制](#10-trace-events-机制)
11. [安全层架构](#11-安全层架构)
12. [Schemas 层](#12-schemas-层)
13. [Core 基础设施层](#13-core-基础设施层)
14. [数据持久化链路](#14-数据持久化链路)
15. [新增节点的完整步骤](#15-新增节点的完整步骤)
16. [Evals（Promptfoo）](#16-evalsprompfoo)
17. [常见问题](#17-常见问题)

---

## 1. 项目整体分层

```
┌─────────────────────────────────────┐
│           backend/                  │  FastAPI + SQLAlchemy
│  HTTP API → Service → Repository    │  处理请求、持久化、返回响应
└──────────────┬──────────────────────┘
               │  调用 workflow 方法
               │  传入参数，接收 TarotWorkflowState
               ▼
┌─────────────────────────────────────┐
│            agent/                   │  LangGraph 工作流
│  workflows → nodes → security       │  执行 AI 管道，修改并返回状态
└─────────────────────────────────────┘
```

**核心原则：**

- `backend/` 不直接调用任何单个 node，只调用 `TarotReflectionWorkflow` 上的三个方法。
- `agent/` 不持久化任何数据，只负责修改并返回 `TarotWorkflowState`。
- 两层通过 `TarotWorkflowState` 这一个对象传递所有信息。

---

## 2. 目录结构速览

```
agent/
├── workflows/
│   ├── orchestrator.py          # 主编排器，backend 的直接依赖
│   └── security_orchestrator.py # 输入安全流水线（供节点复用）
├── nodes/
│   ├── pre_input_security.py    # 节点：输入安全检查
│   ├── clarifier.py             # 节点：问题澄清与归一化
│   ├── draw_and_interpret.py    # 节点：抽牌与解读
│   ├── intermediate_security.py # 节点：agent 间内容安全检查
│   └── safety_guard.py          # 节点：最终输出安全审查 + fallback 工具
├── security/
│   ├── detectors.py             # 规则检测器（注入、越权等）
│   ├── pre_input_guard.py       # 输入安全决策器
│   ├── sanitizer.py             # 输入清洗器
│   └── inter_agent_guard.py     # agent 间输出检测器
├── schemas/
│   ├── clarifier.py             # ClarifierInput / ClarifierOutput
│   ├── draw.py                  # DrawInput / DrawCard / DrawOutput
│   ├── synthesis.py             # SynthesisInput / SynthesisOutput
│   └── safety.py                # SafetyReviewInput / SafetyReviewOutput
├── core/
│   ├── schemas.py               # 安全域内部类型（RequiredAction、SafetyDecision 等）
│   ├── trust.py                 # 内容信任标签工具
│   ├── model_gateway.py         # 模型调用抽象层（OpenAI 实现）
│   └── prompt_registry.py       # Prompt 文件加载与缓存
└── tests/
    ├── conftest.py                   # sys.path bootstrap（使 backend/app 可导入）
    ├── test_inter_agent_guard.py
    ├── test_pre_input_guard.py
    ├── test_prompt_injection.py
    ├── test_safety_guard_node.py
    ├── test_sanitizer.py
    ├── test_security_orchestrator.py
    └── test_workflow_stub.py
```

---

## 3. TarotWorkflowState：唯一的联动接口

`TarotWorkflowState` 定义在 `backend/app/schemas/workflow/tarot_workflow_state.py`，是 backend 和 agent 之间传递数据的**唯一接口对象**。

agent 的所有节点只做一件事：**读取 state，执行逻辑，写入 state，返回 state**。

### 字段全览

```python
class TarotWorkflowState(WorkflowSchema):
    # ── 基础标识 ──────────────────────────────────────────────
    session_id: str
    reading_id: str
    status: WorkflowStatus          # 工作流状态机（见第5节）
    locale: str                     # 语言区域，如 "zh-CN"
    spread_type: SpreadType         # 牌阵类型，如 THREE_CARD_REFLECTION
    raw_question: str               # 用户原始问题

    # ── 可选元信息 ────────────────────────────────────────────
    client_request_id: str | None
    metadata: dict[str, Any] | None
    created_at: datetime
    completed_at: datetime | None

    # ── Pre-Input Security 节点写入 ───────────────────────────
    input_safety_status: str | None         # "continue" / "rewrite" / "block"
    input_required_action: str | None       # RequiredAction 枚举值
    input_risk_level: str | None            # RiskLevel 枚举值
    input_detected_risks: list[str]         # 检测到的风险类型
    input_removed_segments: list[str]       # 被清洗掉的文本片段
    input_preserved_intent: str | None      # 清洗后保留的意图描述
    input_sanitized: bool                   # 是否经过了清洗

    # ── Clarifier 节点写入 ────────────────────────────────────
    effective_question: str | None          # 安全处理后的实际问题
    normalized_question: str | None         # 归一化后的问题（进入 draw）
    clarification_output: ClarifierOutput | None
    clarification_turns: list[ClarificationTurnState]

    # ── Draw 节点写入 ─────────────────────────────────────────
    cards: list[DrawCard]
    draw_output: DrawOutput | None

    # ── Synthesis 节点写入 ────────────────────────────────────
    synthesis_output: SynthesisOutput | None

    # ── Safety Guard 节点写入 ─────────────────────────────────
    safety_output: SafetyReviewOutput | None

    # ── 所有节点累积写入 ──────────────────────────────────────
    trace_events: list[TraceEventPayload]
```

### 关键规则

- **只有 agent 写入，backend 只读取**：backend 在拿到返回的 state 后，直接读取字段落库，不会再修改它。
- **trace_events 是追加写**：每个节点执行完毕后，向 `state.trace_events` **追加**一条记录，不覆盖已有记录。
- **status 是全局信号**：任何节点将 `status` 设为 `SAFE_FALLBACK_RETURNED`，后续所有节点都会跳过执行。

---

## 4. 两条主工作流

backend 通过 `TarotReflectionWorkflow` 的三个方法驱动 agent：

| 方法 | 调用时机 | 执行的节点 |
|------|---------|-----------|
| `workflow.run(...)` | 单步 Reading（`POST /readings`） | 全部节点 |
| `workflow.evaluate_question(...)` | 多步 Session 的问题评估 | Pre-Input Security + Clarifier |
| `workflow.continue_from_ready_state(state)` | 多步 Session 的执行阶段 | Draw + Intermediate Security + Synthesis + Safety Guard |

### 4.1 单步 Reading

适用于 `POST /readings`，用户一次提交问题、直接拿到完整解读结果。

```
backend: TarotReadingService.create_reading()
  │
  ├─ repository.bootstrap_reading()          # 建 Session + Reading DB 记录
  │
  ├─ workflow.run(                            # ← 调用 agent
  │      session_id=..., reading_id=...,
  │      raw_question=..., locale=...,
  │      spread_type=...,
  │      persistence_handler=save_fn         # 可选回调，执行完后自动落库
  │  )
  │    内部执行顺序：
  │    1. evaluate_question()   → Pre-Input Security → Clarifier
  │    2. if READY_FOR_DRAW:
  │          continue_from_ready_state() → Draw → Intermediate Security
  │                                      → Synthesis → Safety Guard
  │    3. if persistence_handler: persistence_handler(state)
  │
  └─ 返回 TarotWorkflowState → 构建 ReadingResultResponse
```

### 4.2 多步 Session（含澄清）

适用于需要多轮交互的场景，用户可能需要回答澄清问题。

```
POST /sessions
└─ repository.create_session()                     → status=CREATED

POST /sessions/{id}/question
└─ workflow.evaluate_question(raw_question=...)
      Pre-Input Security → Clarifier
   若 Clarifier 判断问题过短或过于模糊：
      → status=CLARIFYING，clarification_output.clarifier_question="..."
   若 Clarifier 认为问题清晰：
      → status=READY_FOR_DRAW

POST /sessions/{id}/clarifications  （可重复多轮）
└─ workflow.evaluate_question(raw_question=合并后的问题)
      重新执行 Pre-Input Security → Clarifier
   直到 status=READY_FOR_DRAW

POST /sessions/{id}/run
└─ workflow.continue_from_ready_state(state)
      Draw → Intermediate Security → Synthesis → Safety Guard
      → status=COMPLETED 或 SAFE_FALLBACK_RETURNED
```

> **注意**：`evaluate_question` 每次都从头构建新的 `TarotWorkflowState`，之前轮次的上下文由 backend 负责拼接进 `raw_question`，agent 不持有多轮历史。

---

## 5. 工作流状态机

`WorkflowStatus` 枚举定义在 `backend/app/domain/enums/workflow_status.py`。

```
CREATED
  │
  ▼
QUESTION_RECEIVED  ←── evaluate_question() 初始化 state 时设置
  │
  ▼
CLARIFYING         ←── Clarifier 判断需要澄清
  │  （用户提交澄清后重新 evaluate_question）
  ▼
READY_FOR_DRAW     ←── Clarifier 判断问题已清晰
  │
  ▼
DRAW_COMPLETED     ←── Draw 节点成功
  │
  ▼
SYNTHESIS_COMPLETED ←── Synthesis 节点成功
  │
  ▼
COMPLETED          ←── Safety Guard 节点成功

任何节点失败 ──────────→ SAFE_FALLBACK_RETURNED
```

**安全回退的触发条件：**

- Pre-Input Security 检测到高风险输入（`block` 决策）
- Draw 节点连续重试失败
- Intermediate Security 检测到 agent 间内容异常
- Synthesis 节点执行失败
- Safety Guard 节点执行失败
- 任何步骤发现 `synthesis_output` 为 `None`

一旦 `status` 被设为 `SAFE_FALLBACK_RETURNED`，orchestrator 会跳过所有后续节点，直接返回当前 state。

---

## 6. 节点执行机制

### 6.1 Question Graph（问题评估阶段）

```
START
  │
  ▼
pre_input_security
  │
  ├─ status=SAFE_FALLBACK_RETURNED ──→ END
  │
  ▼
clarifier
  │
  ▼
END
```

图定义位于 `orchestrator.py` 的 `_build_question_graph()` 方法。

### 6.2 Ready-State Graph（主解读阶段）

```
START
  │
  ▼
draw_interpreter
  │
  ├─ status=SAFE_FALLBACK_RETURNED ──→ END
  │
  ▼
intermediate_security
  │
  ├─ status=SAFE_FALLBACK_RETURNED ──→ END
  │
  ▼
synthesis
  │
  ├─ status=SAFE_FALLBACK_RETURNED ──→ END
  │
  ▼
safety_guard
  │
  ▼
END
```

图定义位于 `orchestrator.py` 的 `_build_ready_state_graph()` 方法。

### 6.3 安全链路

安全检查分布在工作流的三个位置，互相独立：

| 位置 | 节点 | 检查对象 | 触发来源 |
|------|------|---------|---------|
| 最前 | `pre_input_security` | 用户原始输入 | `security/pre_input_guard.py` + `security/sanitizer.py` |
| 中间 | `intermediate_security` | Draw 输出（agent 产物） | `security/inter_agent_guard.py` |
| 最后 | `safety_guard` | Synthesis 输出（最终内容） | 关键词规则集（在 `nodes/safety_guard.py`） |

---

## 7. 各节点详解

### `pre_input_security`（输入安全检查）

**文件**：`agent/nodes/pre_input_security.py`

**执行函数**：`execute_pre_input_security_step(...)`

**逻辑**：

1. 调用 `run_pre_input_security_pipeline(state.raw_question)`
2. 检测结果为三种决策之一：
   - `continue`：输入安全，`state.effective_question = state.raw_question`
   - `rewrite`：输入经过清洗，`state.effective_question = 清洗后的问题`，`state.input_sanitized = True`
   - `block`：输入危险，`state.status = SAFE_FALLBACK_RETURNED`，流程终止
3. 向 `state.trace_events` 追加一条记录

**写入的 state 字段**：`input_safety_status`、`input_required_action`、`input_risk_level`、`input_detected_risks`、`effective_question`、`input_sanitized`、`input_removed_segments`、`input_preserved_intent`

---

### `clarifier`（问题澄清）

**文件**：`agent/nodes/clarifier.py`

**执行函数**：`execute_clarifier_step(...)`

**逻辑**：

1. 从 `state.effective_question` 或 `state.raw_question` 取问题
2. 构建 `ClarifierInput`，调用 `clarifier_agent.run(payload)`
3. 根据 `ClarifierOutput.clarification_required`：
   - `True` → `state.status = CLARIFYING`
   - `False` → `state.status = READY_FOR_DRAW`，`state.normalized_question = 归一化后的问题`
4. 向 `state.trace_events` 追加记录

**写入的 state 字段**：`clarification_output`、`normalized_question`、`status`

**依赖**：`ClarifierAgent` 协议（见第 8 节）

---

### `draw_and_interpret`（抽牌与解读）

**文件**：`agent/nodes/draw_and_interpret.py`

**执行函数**：`execute_draw_step(...)`

**逻辑**：

1. 从 `state.normalized_question` 或 `state.raw_question` 取问题
2. 构建 `DrawInput`，调用 `draw_agent.run(payload)`，最多重试 2 次
3. 成功：`state.cards = DrawOutput.cards`，`state.status = DRAW_COMPLETED`
4. 失败：`state.status = SAFE_FALLBACK_RETURNED`，写入 `state.safety_output`（保护性回退）

**写入的 state 字段**：`cards`、`draw_output`、`status`

**依赖**：`DrawAgent` 协议

---

### `intermediate_security`（agent 间内容检查）

**文件**：`agent/nodes/intermediate_security.py`

**执行函数**：`execute_intermediate_security_step(...)`

**逻辑**：

1. 将 `state.cards` 中每张牌的 `interpretation` 拼接成字符串
2. 用 `tag_content()` 将其标记为来自 `ContentSource.AGENT` 的内容
3. 调用 `inspect_user_input(tagged_content)` 运行检测器套件
4. 通过：继续流程
5. 阻断：`state.status = SAFE_FALLBACK_RETURNED`，写入 `state.safety_output`

**核心逻辑**：检测 Draw Agent 的输出中是否嵌入了恶意指令（防止被污染的 LLM 输出影响后续节点）

---

### `synthesis`（综合解读）

**在 orchestrator 中的方法**：`_run_synthesis_step(state)`

**逻辑**：

1. 构建 `SynthesisInput`（包含 `normalized_question` 和所有 `card.interpretation`）
2. 调用 `synthesis_agent.run(payload)`
3. `state.synthesis_output = SynthesisOutput`，`state.status = SYNTHESIS_COMPLETED`

**写入的 state 字段**：`synthesis_output`、`status`

**依赖**：`SynthesisAgent` 协议（注：synthesis 逻辑在 orchestrator 内部，无独立节点文件）

---

### `safety_guard`（最终输出安全审查）

**文件**：`agent/nodes/safety_guard.py`

**执行函数**：`execute_safety_guard_step(...)`

**逻辑**：

1. 若 `state.synthesis_output` 为 `None`，调用 `protective_fallback_factory` 并设 `SAFE_FALLBACK_RETURNED`
2. 将 `synthesis_output.summary` + `action_advice` 拼接后逐词扫描关键词
3. 根据命中结果三路分支：
   - **无命中** → `SafetyAction.PASSTHROUGH`，`state.status = COMPLETED`，原文写入 `safety_output`
   - **中风险关键词**（投资、医疗、法律等）→ `SafetyAction.REWRITE`，追加免责声明，`state.status = COMPLETED`
   - **高风险关键词**（自杀、暴力等）→ `SafetyAction.BLOCK_AND_FALLBACK`，替换保护性文案，`state.status = SAFE_FALLBACK_RETURNED`

**写入的 state 字段**：`safety_output`、`status`、`completed_at`

**关键词集**（`nodes/safety_guard.py` 模块级常量）：

| 风险等级 | 代表关键词 |
|---------|----------|
| HIGH | 自杀、自残、不想活、结束生命、伤害他人、暴力 |
| MEDIUM | 投资、炒股、手术、医疗、离婚、官司 |

---

## 8. Agent 协议接口（Protocol）

`TarotReflectionWorkflow` 通过 Python `Protocol` 定义了三个可插拔的 Agent 接口，全部在 `agent/workflows/orchestrator.py` 中声明：

```python
class ClarifierAgent(Protocol):
    def run(self, payload: ClarifierInput) -> ClarifierOutput: ...

class DrawAgent(Protocol):
    def run(self, payload: DrawInput) -> DrawOutput: ...

class SynthesisAgent(Protocol):
    def run(self, payload: SynthesisInput) -> SynthesisOutput: ...
```

**每个协议的输入输出类型**：

| Agent | 输入 | 输出 | Schema 文件 |
|-------|------|------|------------|
| ClarifierAgent | `ClarifierInput(raw_question, locale)` | `ClarifierOutput(normalized_question, clarification_required, clarifier_question)` | `agent/schemas/clarifier.py` |
| DrawAgent | `DrawInput(question, locale, spread_type)` | `DrawOutput(cards: list[DrawCard])` | `agent/schemas/draw.py` |
| SynthesisAgent | `SynthesisInput(normalized_question, card_interpretations, locale)` | `SynthesisOutput(summary, action_advice, reflection_question)` | `agent/schemas/synthesis.py` |

目前每个接口都有一个默认实现（`_DefaultClarifierAgent` 等），使用硬编码逻辑，不调用真实 LLM。这些默认实现用于开发和测试阶段，可通过构造函数注入真实 LLM 实现替换（见第 9 节）。

> **注意**：Safety Guard 不是可插拔 Agent，而是内置的规则节点（同 `intermediate_security`），直接在 `nodes/safety_guard.py` 中以关键词检查实现。如需替换为 LLM 审查，修改 `execute_safety_guard_step` 的内部逻辑即可。

---

## 9. 如何替换 Default Agent 实现

通过 `TarotReflectionWorkflow` 的构造函数注入真实实现：

```python
from agent.workflows import TarotReflectionWorkflow

# 实现 Protocol 接口（无需继承，只需方法签名匹配）
class MyClarifierAgent:
    def run(self, payload: ClarifierInput) -> ClarifierOutput:
        # 调用 OpenAI / Claude 等 LLM
        ...

# 注入（三个可插拔 Agent）
workflow = TarotReflectionWorkflow(
    clarifier_agent=MyClarifierAgent(),
    draw_agent=MyDrawAgent(),
    synthesis_agent=MySynthesisAgent(),
)
```

**不需要继承任何基类**，Python Protocol 是鸭子类型，只要 `.run()` 方法签名匹配即可。Safety Guard 不在此注入，它是内置规则节点，如需修改逻辑请直接编辑 `agent/nodes/safety_guard.py`。

### 使用 ModelGateway 实现 LLM Agent

`agent/core/model_gateway.py` 提供了 OpenAI 调用的统一封装，推荐在自定义 Agent 实现中使用：

```python
from agent.core.model_gateway import build_gateway_from_settings
from agent.core.prompt_registry import load_prompt
from agent.schemas.clarifier import ClarifierInput, ClarifierOutput

class LLMClarifierAgent:
    def __init__(self):
        # 从 backend/.env 中读取 OPENAI_API_KEY / OPENAI_MODEL 等配置
        self._gateway = build_gateway_from_settings()
        self._system_prompt = load_prompt("clarifier_system_prompt")

    def run(self, payload: ClarifierInput) -> ClarifierOutput:
        response = self._gateway.run(
            user_prompt=payload.raw_question,
            system_prompt=self._system_prompt,
        )
        # 解析 response.content（JSON 字符串）为 ClarifierOutput
        ...
```

`ModelGateway` 接口说明：

| 参数 | 类型 | 说明 |
|------|------|------|
| `user_prompt` | `str` | 用户侧内容 |
| `system_prompt` | `str \| None` | 系统提示词（可选） |
| `temperature` | `float \| None` | 覆盖实例默认值 |
| `max_tokens` | `int \| None` | 覆盖实例默认值 |

返回 `ModelResponse`，字段：`content: str`、`model: str`、`prompt_tokens: int`、`completion_tokens: int`。

---

## 10. Trace Events 机制

每个节点执行完毕后，必须向 `state.trace_events` 追加一条 `TraceEventPayload`。这是 backend 监控和调试的主要数据来源。

### TraceEventPayload 结构

```python
class TraceEventPayload:
    event_id: str           # UUID，自动生成
    step_name: str          # 节点名称，如 "clarifier"
    event_status: TraceEventStatus  # SUCCEEDED / FAILED / FALLBACK
    attempt_no: int         # 重试次数（从 1 开始）
    latency_ms: int | None  # 执行耗时（毫秒）
    error_code: str | None  # 错误码（仅失败时填写）
    payload: dict           # 节点输出摘要（不含敏感信息）
    created_at: datetime
```

### 如何产生 trace event

在 orchestrator 中统一使用 `self._trace_event(...)` 工厂方法创建：

```python
state.trace_events.append(
    self._trace_event(
        step_name="my_node",
        event_status=TraceEventStatus.SUCCEEDED,
        attempt_no=1,
        started=started,          # perf_counter() 的起始值
        payload={"key": "value"}, # 摘要信息，不要放完整内容
    )
)
```

在独立节点函数中（如 `execute_pre_input_security_step`），使用传入的 `trace_event_factory` 参数（签名与上述相同）。

### event_status 选择规则

| 状态 | 含义 | 何时使用 |
|------|------|---------|
| `SUCCEEDED` | 节点正常完成 | 正常路径 |
| `FALLBACK` | 节点完成但触发了回退（如输入被清洗、输入被拦截） | rewrite / block 路径 |
| `FAILED` | 节点发生了未预期的异常 | 捕获到 Exception 时 |

### backend 如何消费 trace events

backend 在调用 `repository.save_workflow_result(state)` 时，将 `state.trace_events` 中的每条记录批量写入 `trace_events` 表，可通过 `GET /readings/{reading_id}/trace` 查询。

---

## 11. 安全层架构

### 模块分工

```
agent/security/
├── detectors.py           # 纯规则检测，返回 DetectionResult 列表
├── pre_input_guard.py     # 汇总检测结果，输出 SafetyDecision
├── sanitizer.py           # 根据决策清洗输入，输出 SanitizedPayload
└── inter_agent_guard.py   # 封装 tag_content + inspect_user_input，用于 agent 间检查
```

### 调用链（输入安全）

```
用户输入
  │
  ▼ security_orchestrator.run_pre_input_security_pipeline()
  ├─ tag_content(input, source=USER)        # core/trust.py
  ├─ inspect_user_input(tagged)             # security/pre_input_guard.py
  │    └─ run_all_detectors(text)           # security/detectors.py
  │         ├─ detect_prompt_injection()
  │         ├─ detect_secret_exfiltration()
  │         ├─ detect_role_escalation()
  │         ├─ detect_instruction_override()
  │         └─ detect_suspicious_patterns()
  └─ if REWRITE: sanitize_user_input()      # security/sanitizer.py
```

### 内容信任标签（TrustTaggedContent）

所有进入检测器的内容都需要先打上信任标签：

```python
from agent.core.trust import tag_content
from agent.core.schemas import ContentSource

# 用户输入
tagged = tag_content(user_text, source=ContentSource.USER)

# agent 产出（用于 intermediate_security）
tagged = tag_content(agent_output, source=ContentSource.AGENT)
```

`ContentSource` 可选值：`USER`、`AGENT`、`SYSTEM`、`TOOL`、`RETRIEVER`

### SafetyDecision 结构

```python
@dataclass
class SafetyDecision:
    risk_level: RiskLevel               # LOW / MEDIUM / HIGH（来自 backend.app.domain.enums）
    allow_continue: bool                # True = 可继续
    required_action: RequiredAction     # CONTINUE / REWRITE / BLOCK / ...
    detected_risks: list[str]           # 风险类型标识
    evidence: list[str]                 # 命中的文本片段
    notes_for_orchestrator: str         # 给编排器的说明
```

> **注意**：`RiskLevel` 统一使用 `backend.app.domain.enums.RiskLevel`（大写值 `"LOW"`, `"MEDIUM"`, `"HIGH"`），`agent/core/schemas.py` 不再自行定义，直接 re-import。

---

## 12. Schemas 层

`agent/schemas/` 定义了各节点的输入输出类型，`agent/core/schemas.py` 定义了安全域的内部类型。

### 注意两套 Schema 的区别

| 用途 | 位置 | 说明 |
|------|------|------|
| 节点 I/O | `agent/schemas/*.py` | Pydantic BaseModel，用于 agent 与 backend 的数据交换 |
| 安全内部类型 | `agent/core/schemas.py` | dataclass，仅在 `agent/security/` 和 `agent/nodes/` 内部流转，不暴露给 backend |

**`agent/core/schemas.py` 现有类型**（仅安全域内部使用）：

| 类型 | 用途 |
|------|------|
| `RequiredAction` | 安全决策行动枚举（CONTINUE / REWRITE / BLOCK 等） |
| `TrustLevel` | 内容信任等级（TRUSTED / UNTRUSTED / SANITIZED） |
| `ContentSource` | 内容来源（USER / AGENT / SYSTEM 等） |
| `TrustTaggedContent` | 带信任标签的内容载体 |
| `SafetyDecision` | 安全检测结果（由 pre_input_guard 产出，在安全层内部流转） |
| `SanitizedPayload` | 清洗后的输入载体 |

> `RiskLevel` 不在此定义，直接使用 `backend.app.domain.enums.RiskLevel`。

### backend 使用的类型（来自 `agent/schemas/`）

backend 的 `TarotWorkflowState` 直接引用这些类型：

```python
from agent.schemas.clarifier import ClarifierOutput
from agent.schemas.draw import DrawCard, DrawOutput
from agent.schemas.safety import SafetyReviewOutput
from agent.schemas.synthesis import SynthesisOutput
```

修改这些类的字段时，需同步检查 `TarotWorkflowState` 和 `repository` 的落库逻辑。

---

## 13. Core 基础设施层

`agent/core/` 提供跨节点共享的基础能力，节点代码不应直接依赖 OpenAI SDK 或文件系统，而是通过这一层调用。

### model_gateway.py

**功能**：封装 OpenAI chat completions，对节点屏蔽 SDK 细节。

```
agent/core/model_gateway.py
├── ModelGateway          # ABC，统一调用接口
├── ModelResponse         # 返回值（content, model, token 计数）
├── OpenAIModelGateway    # 具体实现，读取 OPENAI_API_KEY / OPENAI_MODEL 环境变量
└── build_gateway_from_settings()  # 从 AppSettings 构造网关（推荐使用）
```

**构造方式**：

```python
# 推荐：自动读取 backend/.env 中的配置
from agent.core import build_gateway_from_settings
gateway = build_gateway_from_settings()

# 手动指定（测试时）
from agent.core import OpenAIModelGateway
gateway = OpenAIModelGateway(api_key="sk-xxx", model="gpt-4o-mini", timeout=30)
```

**配置来源**（优先级从高到低）：
1. 构造函数参数
2. 环境变量 `OPENAI_API_KEY` / `OPENAI_MODEL`
3. `backend/app/infrastructure/config/settings.py` 中的 `AppSettings`（通过 `build_gateway_from_settings()` 读取）

### prompt_registry.py

**功能**：从 `prompts/` 目录加载 Prompt 模板文件，提供进程级缓存。

```
agent/core/prompt_registry.py
├── load_prompt(name)    # 按名称加载（相对 prompts/ 目录，无需 .md 后缀）
├── list_prompts()       # 返回所有可用 Prompt 的 name→Path 字典
└── clear_cache()        # 清空缓存（测试时使用）
```

**Prompt 命名规则**（与 `prompts/` 目录结构对应）：

| 文件路径 | load_prompt 调用 |
|---------|----------------|
| `prompts/clarifier_system_prompt.md` | `load_prompt("clarifier_system_prompt")` |
| `prompts/synthesis_system_prompt.md` | `load_prompt("synthesis_system_prompt")` |
| `prompts/draw_interpret_system_prompt.md` | `load_prompt("draw_interpret_system_prompt")` |
| `prompts/security/safety_rewrite.md` | `load_prompt("security/safety_rewrite")` |

**注意**：`prompts/` 下各模板文件目前只有结构骨架，LLM Agent 实现时需先填充实际内容。

---

## 14. 数据持久化链路

agent 不直接操作数据库。backend 在拿到 `TarotWorkflowState` 后，调用 repository 的方法落库。

### 主要落库操作（`save_workflow_result`）

```
TarotWorkflowState
  │
  ├─ status, normalized_question, completed_at
  │    └─ 写入 ReadingModel
  │
  ├─ cards (list[DrawCard])
  │    └─ 清空旧记录 + 批量写入 ReadingCardModel
  │
  ├─ safety_output (SafetyReviewOutput)
  │    └─ 替换 SafetyReviewModel
  │         ├─ safe_summary → reading_model.summary
  │         ├─ safe_action_advice → reading_model.action_advice
  │         └─ safe_reflection_question → reading_model.reflection_question
  │
  └─ trace_events (list[TraceEventPayload])
       └─ 批量写入 TraceEventModel
```

### 安全回退时的落库行为

当 `status == SAFE_FALLBACK_RETURNED` 时，`safety_output` 仍会被写入，内容是保护性文案，`cards` 字段通常为空列表。backend 会据此给前端返回一个安全的降级响应，而不是报错。

---

## 15. 新增节点的完整步骤

以新增一个假设的 `enrichment`（问题丰富化）节点为例：

### Step 1：定义 schema

在 `agent/schemas/` 下新建或扩展文件：

```python
# agent/schemas/enrichment.py
from pydantic import BaseModel, ConfigDict

class EnrichmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    normalized_question: str
    locale: str

class EnrichmentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enriched_question: str
    added_context: str
```

### Step 2：在 TarotWorkflowState 中添加输出字段

在 `backend/app/schemas/workflow/tarot_workflow_state.py` 中添加：

```python
enrichment_output: EnrichmentOutput | None = None
```

### Step 3：实现节点函数

在 `agent/nodes/` 下新建文件：

```python
# agent/nodes/enrichment.py
from time import perf_counter
from typing import Protocol, Any

from agent.schemas.enrichment import EnrichmentInput, EnrichmentOutput
from backend.app.domain.enums import TraceEventStatus
from backend.app.schemas.workflow import TarotWorkflowState

class EnrichmentAgent(Protocol):
    def run(self, payload: EnrichmentInput) -> EnrichmentOutput: ...

def execute_enrichment_step(
    *,
    state: TarotWorkflowState,
    enrichment_agent: EnrichmentAgent,
    observer,
    trace_event_factory,
    trace_logger,
) -> TarotWorkflowState:
    payload = EnrichmentInput(
        normalized_question=state.normalized_question or state.raw_question,
        locale=state.locale,
    )
    with observer.observe_step(step_name="enrichment", as_type="chain") as observation:
        started = perf_counter()
        output = enrichment_agent.run(payload)
        state.enrichment_output = output
        state.trace_events.append(
            trace_event_factory(
                step_name="enrichment",
                event_status=TraceEventStatus.SUCCEEDED,
                attempt_no=1,
                started=started,
                payload={"enriched": True},
            )
        )
        observation.success()
    trace_logger(state=state, reading_id=state.reading_id, only_latest=True)
    return state
```

### Step 4：在 orchestrator 中注入和注册

在 `TarotReflectionWorkflow.__init__` 中添加：

```python
self._enrichment_agent = enrichment_agent or _DefaultEnrichmentAgent()
```

在 `_build_ready_state_graph()` 中添加节点和边：

```python
graph.add_node("enrichment", self._graph_enrichment_node)
graph.add_edge("clarifier", "enrichment")  # 调整边的顺序
```

在 `_run_ready_state_without_langgraph()` 中添加调用：

```python
state = self._run_enrichment_step(state)
if state.status is WorkflowStatus.SAFE_FALLBACK_RETURNED:
    return state
```

### Step 5：导出节点函数

在 `agent/nodes/__init__.py` 中添加：

```python
from .enrichment import execute_enrichment_step
```

### Step 6：编写测试

在 `agent/tests/` 下添加测试文件，验证节点的输入输出、trace event 记录、fallback 行为。

---

## 16. Evals（Promptfoo）

`evals/promptfoo/` 下提供了基于 Promptfoo 的 eval 套件，用于验证工作流的端到端行为。

### 文件结构

```
evals/promptfoo/
├── promptfooconfig.yaml       # 测试用例与断言定义
└── tarot_backend_provider.py  # Python provider，直接调用 TarotReflectionWorkflow
```

### Provider 原理

`tarot_backend_provider.py` 直接在进程内调用 `TarotReflectionWorkflow.run()`，**无需启动 HTTP 服务**，适合 CI 环境。它会自动把 `repo_root/` 和 `backend/` 加入 `sys.path`。

### 测试用例覆盖

| 类别 | 用例数 | 验证内容 |
|------|--------|---------|
| 正常流程 | 1 | status=COMPLETED, cards=3, risk=LOW |
| 澄清流程 | 2 | clarification_required=True, status=CLARIFYING |
| 前置安全拦截 | 3 | Prompt 注入、角色升级、系统提示词窃取 → SAFE_FALLBACK_RETURNED |
| 输出安全兜底 | 2 | 自伤、暴力内容 → HIGH + BLOCK_AND_FALLBACK |
| 中风险改写 | 2 | 投资、医疗话题 → COMPLETED + MEDIUM + REWRITE |

### 运行方式

```bash
# 在仓库根目录
npx promptfoo@latest eval -c evals/promptfoo/promptfooconfig.yaml

# Windows 下如果解释器找不到，显式指定
$env:PROMPTFOO_PYTHON = "python"
npx promptfoo@latest eval -c evals/promptfoo/promptfooconfig.yaml
```

### 在 pytest 中验证 provider 模块

```bash
cd backend
python -m pytest app/tests/unit/test_phase5_runtime_helpers.py -v
```

---

## 17. 常见问题

### Q：为什么节点函数是普通函数而不是类？

节点函数设计为无状态的纯函数，所有依赖（agent、observer、factory）都通过参数注入。这样便于单元测试——测试时只需传入 mock 对象，不需要实例化整个 workflow。

### Q：LangGraph 不可用时会怎样？

orchestrator 对 LangGraph 做了优雅降级。如果 `import langgraph` 失败，`self._question_graph` 和 `self._ready_state_graph` 都会被设为 `None`，执行时自动走 `_run_question_without_langgraph()` 和 `_run_ready_state_without_langgraph()` 这两个备用路径，逻辑完全一致。

### Q：agent 里为什么有两套导入路径（`from backend.app.xxx` 和 `from app.xxx`）？

背景：backend 包的 `pyproject.toml` 以 `app` 为根（非 `backend.app`），内部模块使用 `from app.xxx` 互相导入。agent 代码统一使用 `from backend.app.xxx` 的形式。

**当前已通过两处 bootstrap 解决**，无需手动设置 `PYTHONPATH`：

1. **`agent/__init__.py`**：在 agent 包被导入时自动将 `backend/` 插入 `sys.path`，使 `from app.xxx` 在所有场景下可用。
2. **`agent/tests/conftest.py`**：pytest 收集测试时由 conftest 执行相同操作，保证测试环境一致。

运行 agent 单元测试直接执行即可，无需额外环境变量：

```bash
# 在项目根目录
python -m pytest agent/tests/ -v
```

### Q：保护性回退（Protective Fallback）和 Safety Guard 的区别？

| | Protective Fallback | Safety Guard |
|---|---|---|
| **触发场景** | 任意节点执行失败（异常、超时、安全拦截） | 专门检查最终 Synthesis 输出的内容政策 |
| **内容来源** | 硬编码的固定文案 | 基于 Synthesis 输出经过改写或替换 |
| **risk_level** | 固定为 `HIGH` | 动态判断（LOW / MEDIUM / HIGH） |
| **action_taken** | 固定为 `BLOCK_AND_FALLBACK` | PASSTHROUGH / REWRITE / BLOCK_AND_FALLBACK |
| **实现位置** | `orchestrator._protective_fallback()` | `nodes/safety_guard.execute_safety_guard_step()` |

### Q：如何在本地运行 agent 的单元测试？

```bash
# 在项目根目录（无需额外 PYTHONPATH，conftest.py 已自动处理）
python -m pytest agent/tests/ -v
```

### Q：节点中能直接抛出异常吗？

不建议。节点应当捕获所有可预期的异常，将 `state.status` 设为 `SAFE_FALLBACK_RETURNED` 并写入 `safety_output`，然后返回 state。这样 orchestrator 能正常走完回退路径，backend 也能得到一个有效的 state 对象并落库，而不是收到一个未处理的异常。

只有真正无法恢复的系统级错误（如 OOM）才应该让异常向上传播。
