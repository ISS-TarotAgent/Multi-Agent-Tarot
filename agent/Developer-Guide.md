# Agent Developer Guide

本文档面向初次接触本项目的开发者，说明 `agent/` 目录的整体结构、各层职责、与 `backend/` 的联动方式，以及新增节点或 Agent 实现时需要遵守的规范。

> **当前状态（2026-04-21）**：三条业务节点（Clarifier、Draw、Synthesis）已有完整的 LLM 实现（`agent/core/llm_agents.py`），通过 `build_llm_workflow()` 工厂函数接入 backend；Docker + PostgreSQL 的完整链路已验证可用。

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
9. [LLM Agent 实现状态](#9-llm-agent-实现状态)
   - [9.1 已实现的 LLM Agents](#91-已实现的-llm-agents)
   - [9.2 build_llm_workflow 工厂函数](#92-build_llm_workflow-工厂函数)
   - [9.3 接入 backend 的位置](#93-接入-backend-的位置)
10. [当前节点的局限与完整开发路径](#10-当前节点的局限与完整开发路径)
    - [10.1 现状总览](#101-现状总览)
    - [10.2 Clarifier：当前做了什么，还缺什么](#102-clarifier当前做了什么还缺什么)
    - [10.3 Draw：当前做了什么，还缺什么](#103-draw当前做了什么还缺什么)
    - [10.4 Synthesis：当前做了什么，还缺什么](#104-synthesis当前做了什么还缺什么)
    - [10.5 Safety Guard：当前做了什么，还缺什么](#105-safety-guard当前做了什么还缺什么)
    - [10.6 Intermediate Security：当前做了什么，还缺什么](#106-intermediate-security当前做了什么还缺什么)
11. [新增节点的完整步骤](#11-新增节点的完整步骤)
12. [Trace Events 机制](#12-trace-events-机制)
13. [安全层架构](#13-安全层架构)
14. [Schemas 层](#14-schemas-层)
15. [Core 基础设施层](#15-core-基础设施层)
16. [数据持久化链路](#16-数据持久化链路)
17. [Evals（Promptfoo）](#17-evalsprompfoo)
18. [常见问题](#18-常见问题)

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
│   ├── orchestrator.py          # 主编排器，backend 的直接依赖；含 build_llm_workflow()
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
│   ├── llm_agents.py            # ★ LLM 实现：LLMClarifierAgent / LLMDrawAgent / LLMSynthesisAgent
│   └── prompt_registry.py       # Prompt 文件加载与缓存
└── tests/
    ├── conftest.py
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

| 方法                                          | 调用时机                         | 执行的节点                                                   |
| ------------------------------------------- | ---------------------------- | ------------------------------------------------------- |
| `workflow.run(...)`                         | 单步 Reading（`POST /readings`） | 全部节点                                                    |
| `workflow.evaluate_question(...)`           | 多步 Session 的问题评估             | Pre-Input Security + Clarifier                          |
| `workflow.continue_from_ready_state(state)` | 多步 Session 的执行阶段             | Draw + Intermediate Security + Synthesis + Safety Guard |

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

| 位置  | 节点                      | 检查对象               | 触发来源                                                    |
| --- | ----------------------- | ------------------ | ------------------------------------------------------- |
| 最前  | `pre_input_security`    | 用户原始输入             | `security/pre_input_guard.py` + `security/sanitizer.py` |
| 中间  | `intermediate_security` | Draw 输出（agent 产物）  | `security/inter_agent_guard.py`                         |
| 最后  | `safety_guard`          | Synthesis 输出（最终内容） | 关键词规则集（在 `nodes/safety_guard.py`）                       |

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

**依赖**：`SynthesisAgent` 协议

> **注意**：synthesis 逻辑目前内联在 `orchestrator._run_synthesis_step()` 里，没有独立的 `agent/nodes/synthesis.py` 文件，与其他节点的结构不一致。完整开发路径见第 10.4 节。

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

| 风险等级   | 代表关键词                  |
| ------ | ---------------------- |
| HIGH   | 自杀、自残、不想活、结束生命、伤害他人、暴力 |
| MEDIUM | 投资、炒股、手术、医疗、离婚、官司      |

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

| Agent          | 输入                                                                  | 输出                                                                                 | Schema 文件                    |
| -------------- | ------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ---------------------------- |
| ClarifierAgent | `ClarifierInput(raw_question, locale)`                              | `ClarifierOutput(normalized_question, clarification_required, clarifier_question)` | `agent/schemas/clarifier.py` |
| DrawAgent      | `DrawInput(question, locale, spread_type)`                          | `DrawOutput(cards: list[DrawCard])`                                                | `agent/schemas/draw.py`      |
| SynthesisAgent | `SynthesisInput(normalized_question, card_interpretations, locale)` | `SynthesisOutput(summary, action_advice, reflection_question)`                     | `agent/schemas/synthesis.py` |

**不需要继承任何基类**，Python Protocol 是鸭子类型，只要 `.run()` 方法签名匹配即可。Safety Guard 不在此注入，它是内置规则节点，如需修改逻辑请直接编辑 `agent/nodes/safety_guard.py`。

---

## 9. LLM Agent 实现状态

### 9.1 已实现的 LLM Agents

三个 LLM 实现全部位于 `agent/core/llm_agents.py`，每个类接收一个 `ModelGateway` 实例，通过 JSON mode 调用 OpenAI 并解析响应：

```python
# agent/core/llm_agents.py

class LLMClarifierAgent:
    def __init__(self, gateway: ModelGateway) -> None: ...
    def run(self, payload: ClarifierInput) -> ClarifierOutput: ...
    # temperature=0.2, response_format={"type": "json_object"}

class LLMDrawAgent:
    def __init__(self, gateway: ModelGateway) -> None: ...
    def run(self, payload: DrawInput) -> DrawOutput: ...
    # temperature=1.0, response_format={"type": "json_object"}

class LLMSynthesisAgent:
    def __init__(self, gateway: ModelGateway) -> None: ...
    def run(self, payload: SynthesisInput) -> SynthesisOutput: ...
    # temperature=0.7, response_format={"type": "json_object"}
```

**Temperature 设计依据**：

| Agent     | Temperature | 理由                   |
| --------- | ----------- | -------------------- |
| Clarifier | 0.2         | 归一化需要一致性，不需要创造力      |
| Draw      | 1.0         | 抽牌需要随机多样性，避免每次都选同样的牌 |
| Synthesis | 0.7         | 叙述需要流畅自然，同时保持适度随机    |

**每个 Agent 的 user_prompt 构造格式**：

```python
# Clarifier
f"locale: {payload.locale}\nquestion: {payload.raw_question}"

# Draw
f"locale: {payload.locale}\nspread_type: {payload.spread_type.value}\nquestion: {payload.question}"

# Synthesis
f"locale: {payload.locale}\nquestion: {payload.normalized_question}\ncard_interpretations:\n{interpretations_text}"
```

**JSON 解析链路**（以 Clarifier 为例）：

```python
response = self._gateway.run(
    user_prompt,
    system_prompt=self._system_prompt,
    temperature=0.2,
    response_format={"type": "json_object"},  # ← OpenAI JSON mode
)
data = json.loads(response.content)
return ClarifierOutput(
    normalized_question=data["normalized_question"],
    clarification_required=bool(data["clarification_required"]),
    clarifier_question=data.get("clarifier_question"),
)
```

> `response_format` 通过 `ModelGateway.run()` 的 `**kwargs` 传给 OpenAI SDK。JSON mode 要求 system prompt 中必须明确提到"JSON"，三个 prompt 均已满足此条件。

### 9.2 build_llm_workflow 工厂函数

```python
# agent/workflows/orchestrator.py

def build_llm_workflow(
    *,
    observer: WorkflowObserver | None = None,
) -> TarotReflectionWorkflow:
    """Build a TarotReflectionWorkflow wired with real OpenAI-backed agents."""
    from agent.core.llm_agents import LLMClarifierAgent, LLMDrawAgent, LLMSynthesisAgent
    from agent.core.model_gateway import build_gateway_from_settings

    gateway = build_gateway_from_settings()
    return TarotReflectionWorkflow(
        clarifier_agent=LLMClarifierAgent(gateway),
        draw_agent=LLMDrawAgent(gateway),
        synthesis_agent=LLMSynthesisAgent(gateway),
        observer=observer,
    )
```

三个 LLM Agent **共享同一个 `gateway` 实例**（同一个 OpenAI client），避免重复初始化连接。`gateway` 的 API Key 和 Model 从 `AppSettings`（即 `backend/.env`）读取。

如需手动构建（如测试或脚本）：

```python
import sys
sys.path.insert(0, "backend")

from agent.workflows import build_llm_workflow
from backend.app.domain.enums import SpreadType

workflow = build_llm_workflow()
state = workflow.run(
    session_id="...",
    reading_id="...",
    raw_question="我最近感情运势如何？",
    locale="zh-CN",
    spread_type=SpreadType.THREE_CARD_REFLECTION,
)
```

### 9.3 接入 backend 的位置

**文件**：`backend/app/api/deps.py`，函数 `get_tarot_reading_service`。

```python
def get_tarot_reading_service(...) -> TarotReadingService:
    from agent.workflows import build_llm_workflow
    observer = build_workflow_observer(settings)
    workflow = build_llm_workflow(observer=observer) if settings.openai_api_key else None
    return TarotReadingService(
        repository=SqlAlchemyTarotReadingRepository(db_session),
        workflow=workflow,
        observer=observer,
    )
```

- 有 `OPENAI_API_KEY` → 使用 LLM workflow
- 无 key（如测试环境）→ `workflow=None`，`TarotReadingService` 回退到内置 stub workflow

---

## 10. 当前节点的局限与完整开发路径

### 10.1 现状总览

| 节点                    | 实现类型                     | 状态            | 主要局限                       |
| --------------------- | ------------------------ | ------------- | -------------------------- |
| pre_input_security    | 规则引擎                     | ✅ 生产可用        | 规则覆盖有限，无 LLM 辅助判断          |
| clarifier             | LLM（`LLMClarifierAgent`） | ✅ 可用          | 仅依赖 LLM 判断，无结构化澄清追踪        |
| draw_and_interpret    | LLM（`LLMDrawAgent`）      | ⚠️ 功能可用，随机性不足 | 抽牌依赖 LLM "选择"，非真随机         |
| intermediate_security | 规则引擎                     | ✅ 可用          | 复用了用户输入检测器，语义理解弱           |
| synthesis             | LLM（`LLMSynthesisAgent`） | ⚠️ 功能可用，结构不完整 | 逻辑内联在 orchestrator，无独立节点文件 |
| safety_guard          | 规则引擎（关键词）                | ✅ 可用          | 关键词列表需维护，无语义理解             |

---

### 10.2 Clarifier：当前做了什么，还缺什么

**当前实现**：`LLMClarifierAgent` 通过 JSON mode 调用 GPT-4o-mini，system prompt 定义了判断标准（问题是否包含领域和具体诉求），返回 `normalized_question + clarification_required + clarifier_question`。

**局限**：

- 仅做单轮判断，不知道当前是第几轮澄清
- 没有澄清问题的质量控制（可能反问方向不对）
- 对拼写错误、语言混杂（中英混用）的问题处理依赖 LLM 泛化能力

**完整开发方向**：

```python
# 1. 在 ClarifierInput 中加入多轮上下文
class ClarifierInput(BaseModel):
    raw_question: str
    locale: str
    clarification_turns: list[dict] = []  # 历史轮次 [{"question": ..., "answer": ...}]
    turn_index: int = 0                   # 当前是第几轮澄清

# 2. system prompt 增加多轮对话示例（few-shot）
# prompts/clarifier_system_prompt.md 中加入完整对话示例

# 3. 增加澄清终止条件（最多 2 轮）
# 在 ClarifierOutput 中加入 max_turns_reached: bool
```

---

### 10.3 Draw：当前做了什么，还缺什么

**当前实现**：`LLMDrawAgent` 把 78 张牌的名称列表放进 system prompt，要求 GPT-4o-mini 在 temperature=1.0 的条件下"选择"3 张牌并解读。

**局限（核心问题）**：

1. **随机性由 LLM 控制，非真随机**：LLM 有选牌偏好，会更频繁地出现"常见"牌（如 The Tower、The Star）
2. **整合了两个职责**：抽牌（应该随机）和解读（应该有语义）被塞进同一个 prompt，互相干扰
3. **解读质量受问题类型影响大**：相同的牌面对不同类型的问题需要不同的解读维度，当前 prompt 过于通用

**完整开发路径**：

```python
# 推荐方案：拆分为"随机抽牌" + "LLM 解读"两步

import random

TAROT_DECK: list[tuple[str, str]] = [
    ("major-fool", "The Fool"),
    ("major-magician", "The Magician"),
    # ... 全部 78 张
]

class LLMDrawAgent:
    def run(self, payload: DrawInput) -> DrawOutput:
        # Step 1: 用 Python random 真正随机抽牌（保证均匀分布）
        drawn = random.sample(TAROT_DECK, 3)
        orientations = [random.choice(["UPRIGHT", "REVERSED"]) for _ in range(3)]
        positions = ["PAST", "PRESENT", "FUTURE"]

        # Step 2: 将抽到的牌 + 问题传给 LLM，只要求解读
        drawn_info = "\n".join(
            f"- position={pos}, card={name}, orientation={orient}"
            for (code, name), orient, pos in zip(drawn, orientations, positions)
        )
        user_prompt = (
            f"locale: {payload.locale}\n"
            f"question: {payload.question}\n"
            f"drawn_cards:\n{drawn_info}\n"
            "Please provide interpretation for each card. Return JSON."
        )
        response = self._gateway.run(user_prompt, system_prompt=self._system_prompt, ...)
        # 解析 interpretations，与已知 card_code/card_name 合并构建 DrawOutput
```

这样抽牌过程完全随机（Python `random`），LLM 只做解读，两个职责解耦。

---

### 10.4 Synthesis：当前做了什么，还缺什么

**当前实现**：`LLMSynthesisAgent` 功能上完整，能生成 `summary + action_advice + reflection_question`。但 synthesis 逻辑目前**内联在 `orchestrator._run_synthesis_step()`** 中，而不是独立的节点文件。

**局限（架构一致性问题）**：

```
节点文件存在情况：
├── nodes/pre_input_security.py    ✅ 独立文件
├── nodes/clarifier.py             ✅ 独立文件
├── nodes/draw_and_interpret.py    ✅ 独立文件
├── nodes/intermediate_security.py ✅ 独立文件
├── nodes/safety_guard.py          ✅ 独立文件
└── nodes/synthesis.py             ❌ 不存在，逻辑在 orchestrator 里
```

**完整开发路径**：提取独立节点文件：

```python
# 新建 agent/nodes/synthesis.py

from time import perf_counter
from typing import Protocol, Any
from agent.schemas.synthesis import SynthesisInput, SynthesisOutput
from backend.app.domain.enums import TraceEventStatus, WorkflowStatus
from backend.app.schemas.workflow import TarotWorkflowState, TraceEventPayload

class SynthesisAgent(Protocol):
    def run(self, payload: SynthesisInput) -> SynthesisOutput: ...

def execute_synthesis_step(
    *,
    state: TarotWorkflowState,
    synthesis_agent: SynthesisAgent,
    observer,
    trace_event_factory,
    trace_logger,
) -> TarotWorkflowState:
    payload = SynthesisInput(
        normalized_question=state.normalized_question or state.raw_question,
        card_interpretations=[card.interpretation for card in state.cards],
        locale=state.locale,
    )
    with observer.observe_step(step_name="synthesis", as_type="chain", ...) as observation:
        started = perf_counter()
        synthesis_output = synthesis_agent.run(payload)
        state.synthesis_output = synthesis_output
        state.status = WorkflowStatus.SYNTHESIS_COMPLETED
        state.trace_events.append(trace_event_factory(...))
        observation.success(...)
    trace_logger(state=state, reading_id=state.reading_id, only_latest=True)
    return state
```

然后在 `orchestrator.py` 中将 `_run_synthesis_step` 改为调用 `execute_synthesis_step`，并在 `nodes/__init__.py` 中导出。

---

### 10.5 Safety Guard：当前做了什么，还缺什么

**当前实现**：关键词精确匹配（`frozenset` 包含查找）。HIGH 词命中 → BLOCK，MEDIUM 词命中 → REWRITE（追加免责声明）。

**局限**：

- 关键词是中文的，英文或其他语言的有害内容无法检测
- 无法检测"变体表达"（如"结束痛苦" → 涉及自伤但不在词表里）
- 中风险关键词（如"投资"）会误拦截合法的塔罗解读（"财务决策的塔罗视角"中出现"投资"就会触发 REWRITE）

**完整开发路径（两个方向）**：

**方向 A：扩充关键词词表 + 多语言**

```python
# 在 safety_guard.py 中扩展
_HIGH_RISK_KEYWORDS: frozenset[str] = frozenset({
    # 中文
    "自杀", "自残", "不想活", "结束生命", "轻生",
    "伤害他人", "暴力", "杀人", "伤人",
    # 英文
    "kill myself", "end my life", "suicide", "self-harm",
    "hurt someone", "violence",
})
```

**方向 B：增加 LLM 辅助审查层（Safety Guard LLM Agent）**

```python
# 新增 SafetyReviewAgent，专门判断内容是否违反政策
# 仅在关键词 pass 后，对敏感主题（感情、家庭、健康）再做一次 LLM 审查
# 这样避免 LLM 拖慢所有请求，只对高风险场景增加延迟
```

---

### 10.6 Intermediate Security：当前做了什么，还缺什么

**当前实现**：复用 `pre_input_guard.inspect_user_input()` 对 Draw 输出的解读文字运行相同的 5 个检测器。

**局限**：

- 检测器是为用户输入设计的（检测注入指令），但 Draw Agent 的输出格式完全不同
- 正当的塔罗解读中可能包含含有"override"或"now"字样的正常叙述，可能触发误报
- 没有检测更细粒度的 agent 间攻击面（如 JSON 注入、schema pollution）

**完整开发路径**：

```python
# 为 agent 间内容专门设计检测规则
# 1. 检查 DrawCard.interpretation 中是否嵌入了 JSON 结构（schema pollution）
# 2. 检查是否含有系统级指令格式（<!-- --> / [INST] / <|im_start|> 等）
# 3. 对解读文字的长度做合理性约束（过长可能是注入）

# agent/security/inter_agent_guard.py
def validate_draw_output(cards: list[DrawCard]) -> SafetyDecision:
    for card in cards:
        if _has_embedded_instruction(card.interpretation):
            return SafetyDecision(risk_level=HIGH, ...)
        if len(card.interpretation) > 2000:
            return SafetyDecision(risk_level=MEDIUM, ...)
    return SafetyDecision(risk_level=LOW, ...)
```

---

## 11. 新增节点的完整步骤

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
graph.add_edge("clarifier", "enrichment")
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

## 12. Trace Events 机制

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

### event_status 选择规则

| 状态          | 含义                       | 何时使用               |
| ----------- | ------------------------ | ------------------ |
| `SUCCEEDED` | 节点正常完成                   | 正常路径               |
| `FALLBACK`  | 节点完成但触发了回退（如输入被清洗、输入被拦截） | rewrite / block 路径 |
| `FAILED`    | 节点发生了未预期的异常              | 捕获到 Exception 时    |

### backend 如何消费 trace events

backend 在调用 `repository.save_workflow_result(state)` 时，将 `state.trace_events` 中的每条记录批量写入 `trace_events` 表，可通过 `GET /api/v1/traces/readings/{reading_id}` 查询。

---

## 13. 安全层架构

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

```python
from agent.core.trust import tag_content
from agent.core.schemas import ContentSource

tagged = tag_content(user_text, source=ContentSource.USER)    # 用户输入
tagged = tag_content(agent_output, source=ContentSource.AGENT) # agent 产出
```

`ContentSource` 可选值：`USER`、`AGENT`、`SYSTEM`、`TOOL`、`RETRIEVER`

### SafetyDecision 结构

```python
@dataclass
class SafetyDecision:
    risk_level: RiskLevel               # LOW / MEDIUM / HIGH（来自 backend.app.domain.enums）
    allow_continue: bool
    required_action: RequiredAction     # CONTINUE / REWRITE / BLOCK / ...
    detected_risks: list[str]
    evidence: list[str]
    notes_for_orchestrator: str
```

---

## 14. Schemas 层

### 两套 Schema 的区别

| 用途     | 位置                      | 说明                                                   |
| ------ | ----------------------- | ---------------------------------------------------- |
| 节点 I/O | `agent/schemas/*.py`    | Pydantic BaseModel，节点间及与 backend 的数据交换               |
| 安全内部类型 | `agent/core/schemas.py` | dataclass，仅在 `agent/security/` 和 `agent/nodes/` 内部流转 |

**`agent/core/schemas.py` 现有类型**：

| 类型                   | 用途                                      |
| -------------------- | --------------------------------------- |
| `RequiredAction`     | 安全决策行动枚举（CONTINUE / REWRITE / BLOCK 等）  |
| `TrustLevel`         | 内容信任等级（TRUSTED / UNTRUSTED / SANITIZED） |
| `ContentSource`      | 内容来源（USER / AGENT / SYSTEM 等）           |
| `TrustTaggedContent` | 带信任标签的内容载体                              |
| `SafetyDecision`     | 安全检测结果                                  |
| `SanitizedPayload`   | 清洗后的输入载体                                |

> `RiskLevel` 统一使用 `backend.app.domain.enums.RiskLevel`，不在 `agent/core/schemas.py` 重新定义。

---

## 15. Core 基础设施层

### model_gateway.py

```
agent/core/model_gateway.py
├── ModelGateway          # ABC，统一调用接口
├── ModelResponse         # 返回值（content, model, token 计数）
├── OpenAIModelGateway    # 具体实现，读取 OPENAI_API_KEY / OPENAI_MODEL 环境变量
└── build_gateway_from_settings()
```

**run() 方法签名**：

```python
def run(
    self,
    user_prompt: str,
    *,
    system_prompt: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    **kwargs: Any,           # ← 透传给 OpenAI SDK，如 response_format={"type": "json_object"}
) -> ModelResponse: ...
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

### prompt_registry.py

```python
load_prompt("clarifier_system_prompt")          # prompts/clarifier_system_prompt.md
load_prompt("draw_interpret_system_prompt")     # prompts/draw_interpret_system_prompt.md
load_prompt("synthesis_system_prompt")          # prompts/synthesis_system_prompt.md
load_prompt("security/safety_rewrite")          # prompts/security/safety_rewrite.md
```

所有 prompt 文件均已有完整内容（不再是结构骨架），可直接使用。修改 `prompts/` 下的文件后，**无需重启服务**——下次请求会重新加载（进程缓存在 `clear_cache()` 后刷新）。

---

## 16. 数据持久化链路

agent 不直接操作数据库。backend 在拿到 `TarotWorkflowState` 后调用 repository 落库。

### 主要落库操作（`save_workflow_result`）

```
TarotWorkflowState
  │
  ├─ status, normalized_question, completed_at → ReadingModel
  │
  ├─ cards (list[DrawCard]) → 批量写入 ReadingCardModel
  │
  ├─ safety_output (SafetyReviewOutput)
  │    └─ safe_summary → reading_model.summary
  │    └─ safe_action_advice → reading_model.action_advice
  │    └─ safe_reflection_question → reading_model.reflection_question
  │
  └─ trace_events → 批量写入 TraceEventModel
```

### 安全回退时的落库行为

当 `status == SAFE_FALLBACK_RETURNED` 时，`safety_output` 仍会被写入（内容是保护性文案），`cards` 字段通常为空列表。backend 据此给前端返回安全降级响应，而不是报错。

---

## 17. Evals（Promptfoo）

`evals/promptfoo/` 下提供了基于 Promptfoo 的 eval 套件。

### 文件结构

```
evals/promptfoo/
├── promptfooconfig.yaml       # 测试用例与断言定义
└── tarot_backend_provider.py  # Python provider，直接调用 TarotReflectionWorkflow
```

### Provider 原理

`tarot_backend_provider.py` 在进程内直接调用 `TarotReflectionWorkflow.run()`，**无需启动 HTTP 服务**，适合 CI 环境。

### 测试用例覆盖

| 类别     | 验证内容                                            |
| ------ | ----------------------------------------------- |
| 正常流程   | status=COMPLETED, cards=3, risk=LOW             |
| 澄清流程   | clarification_required=True, status=CLARIFYING  |
| 前置安全拦截 | Prompt 注入、角色升级、系统提示词窃取 → SAFE_FALLBACK_RETURNED |
| 输出安全兜底 | 自伤、暴力内容 → HIGH + BLOCK_AND_FALLBACK             |
| 中风险改写  | 投资、医疗话题 → COMPLETED + MEDIUM + REWRITE          |

### 运行方式

```bash
# 在仓库根目录
npx promptfoo@latest eval -c evals/promptfoo/promptfooconfig.yaml

# Windows 下如果解释器找不到
$env:PROMPTFOO_PYTHON = "python"
npx promptfoo@latest eval -c evals/promptfoo/promptfooconfig.yaml
```

---

## 18. 常见问题

### Q：为什么节点函数是普通函数而不是类？

节点函数设计为无状态的纯函数，所有依赖（agent、observer、factory）都通过参数注入。便于单元测试——只需传入 mock 对象，不需要实例化整个 workflow。

### Q：LangGraph 不可用时会怎样？

orchestrator 对 LangGraph 做了优雅降级。如果 `import langgraph` 失败，`self._question_graph` 和 `self._ready_state_graph` 都会被设为 `None`，执行时自动走 `_run_question_without_langgraph()` 和 `_run_ready_state_without_langgraph()` 备用路径，逻辑完全一致。

### Q：agent 里为什么有两套导入路径（`from backend.app.xxx` 和 `from app.xxx`）？

backend 包的 `pyproject.toml` 以 `app` 为根（非 `backend.app`），内部模块使用 `from app.xxx` 互相导入。agent 代码统一使用 `from backend.app.xxx` 的形式。

已通过两处 bootstrap 解决：

1. **`agent/__init__.py`**：导入 agent 包时自动将 `backend/` 插入 `sys.path`
2. **`agent/tests/conftest.py`**：pytest 收集时执行相同操作

```bash
# 运行 agent 单元测试（无需额外环境变量）
python -m pytest agent/tests/ -v
```

### Q：保护性回退（Protective Fallback）和 Safety Guard 的区别？

|                  | Protective Fallback                   | Safety Guard                                     |
| ---------------- | ------------------------------------- | ------------------------------------------------ |
| **触发场景**         | 任意节点执行失败（异常、超时、安全拦截）                  | 专门检查最终 Synthesis 输出的内容政策                         |
| **内容来源**         | 硬编码固定文案                               | 基于 Synthesis 输出经过改写或替换                           |
| **risk_level**   | 固定为 `HIGH`                            | 动态判断（LOW / MEDIUM / HIGH）                        |
| **action_taken** | 固定为 `BLOCK_AND_FALLBACK`              | PASSTHROUGH / REWRITE / BLOCK_AND_FALLBACK       |
| **实现位置**         | `orchestrator._protective_fallback()` | `nodes/safety_guard.execute_safety_guard_step()` |

### Q：节点中能直接抛出异常吗？

不建议。节点应捕获所有可预期异常，将 `state.status` 设为 `SAFE_FALLBACK_RETURNED` 并写入 `safety_output`，然后返回 state。只有真正无法恢复的系统级错误才让异常向上传播。

### Q：如何验证 LLM 流程端到端可用？

```bash
# 1. 启动 docker compose（postgres + backend）
docker compose -f Docker/docker-compose.yml up -d

# 2. 发送真实请求
curl -X POST http://localhost:8000/api/v1/readings \
  -H "Content-Type: application/json" \
  -d '{"question":"我最近感情运势如何？","locale":"zh-CN","spread_type":"THREE_CARD_REFLECTION"}'

# 3. 期望响应：status=COMPLETED, cards 有 3 张, trace_summary.event_count=7
```

### Q：如何在不启动服务的情况下测试单次 LLM 调用？

```python
import sys
sys.path.insert(0, "backend")

# 加载 .env
from pathlib import Path
for line in Path("backend/.env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        import os; os.environ.setdefault(k.strip(), v.strip())

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
print(state.status, state.synthesis_output)
```
