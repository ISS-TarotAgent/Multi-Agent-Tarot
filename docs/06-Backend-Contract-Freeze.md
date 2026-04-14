# Multi-Agent-Tarot 后端阶段 0 契约冻结

## 1. 文档目标

本文档用于完成 `docs/05-Backend-Build-Plan.md` 中剩余的三个阶段 0 交付物：

- 冻结一版工作流状态机
- 冻结一版 Pydantic schema 清单
- 冻结一版 PostgreSQL 最小表结构草案

本文档是编码契约，不是实现代码。阶段 1 之后的新文件、类、数据库迁移和测试都应以此为准。

## 2. 工作流状态机冻结

### 2.1 状态枚举

| 状态 | 是否终态 | 说明 |
| --- | --- | --- |
| `CREATED` | 否 | 会话已创建，尚未提交问题 |
| `QUESTION_RECEIVED` | 否 | 已收到原始问题，正在做 Clarifier 判断 |
| `CLARIFYING` | 否 | Clarifier 认为还需要用户补充上下文 |
| `READY_FOR_DRAW` | 否 | 输入已足够，允许进入抽牌和解读 |
| `DRAW_COMPLETED` | 否 | 抽牌和单牌解释已完成 |
| `SYNTHESIS_COMPLETED` | 否 | 综合结果已生成 |
| `SAFETY_REVIEWED` | 否 | 安全审查已执行 |
| `COMPLETED` | 是 | 正常完成并返回结果 |
| `SAFE_FALLBACK_RETURNED` | 是 | 发生异常或高风险后返回保护性结果 |
| `FAILED` | 是 | 出现不可恢复错误，未形成可返回结果 |

### 2.2 状态转移表

| 当前状态 | 触发事件 | 下一状态 | 说明 |
| --- | --- | --- | --- |
| `CREATED` | 提交原始问题 | `QUESTION_RECEIVED` | 原始问题入库，开始 Clarifier 判断 |
| `QUESTION_RECEIVED` | 问题足够明确 | `READY_FOR_DRAW` | 生成 `normalized_question` |
| `QUESTION_RECEIVED` | 需要澄清 | `CLARIFYING` | 返回 Clarifier 问题 |
| `QUESTION_RECEIVED` | Clarifier 执行失败 | `READY_FOR_DRAW` | 使用原始问题继续执行，并记 warning trace |
| `CLARIFYING` | 用户提交补充回答但仍不充分 | `CLARIFYING` | 允许再次追问 |
| `CLARIFYING` | 用户提交补充回答且信息充分 | `READY_FOR_DRAW` | 更新 `normalized_question` |
| `READY_FOR_DRAW` | Draw and Interpret 成功 | `DRAW_COMPLETED` | 三张牌结果可用 |
| `READY_FOR_DRAW` | Draw 输出非法且修复性重试仍失败 | `SAFE_FALLBACK_RETURNED` | 返回保护性结果 |
| `DRAW_COMPLETED` | Synthesis 成功 | `SYNTHESIS_COMPLETED` | 综合洞察生成完成 |
| `DRAW_COMPLETED` | Synthesis 输出非法且修复性重试仍失败 | `SAFE_FALLBACK_RETURNED` | 返回保护性结果 |
| `SYNTHESIS_COMPLETED` | Safety Guard 完成审查 | `SAFETY_REVIEWED` | 风险等级和动作决策已确定 |
| `SAFETY_REVIEWED` | 审查通过或完成安全重写 | `COMPLETED` | 输出可安全返回 |
| `SAFETY_REVIEWED` | 高风险且只能返回保护性结果 | `SAFE_FALLBACK_RETURNED` | 不下发原始结果 |
| 任意非终态 | 数据库、配置或关键依赖不可恢复失败 | `FAILED` | 记录错误 trace |

### 2.3 关键规则

- `COMPLETED`、`SAFE_FALLBACK_RETURNED`、`FAILED` 都是终态
- 每一个状态推进都必须写入 `trace_events`
- Clarifier 失败不应直接导致会话失败，优先回退到原始问题
- Draw 和 Synthesis 至多允许一次修复性重试
- Safety Guard 必须始终在最终输出前执行

### 2.4 推荐的步骤命名

为保证 trace 稳定可检索，阶段 0 冻结以下步骤名：

- `session_bootstrap`
- `clarifier`
- `draw_interpreter`
- `synthesis`
- `safety_guard`
- `persistence`

## 3. Pydantic schema 冻结原则

### 3.1 设计原则

- 所有外部输入和内部 Agent 输出都必须经过 Pydantic 校验
- 统一使用 Pydantic v2
- 默认使用 `extra="forbid"`，禁止未声明字段静默混入
- 枚举统一集中定义，避免路由层和 Agent 层各自维护一套字符串常量
- API schema、workflow schema、persistence schema 分层管理，避免混用

### 3.2 模块落位约束

| 分组 | 推荐路径 | 作用 |
| --- | --- | --- |
| API schema | `backend/app/schemas/api/` | 路由请求与响应 |
| Workflow state schema | `backend/app/schemas/workflow/` | Orchestrator 状态容器与内部 trace DTO |
| Agent I/O schema | `agent/schemas/` | Clarifier、Draw、Synthesis、Safety Guard 的输入输出 |
| Persistence schema | `backend/app/schemas/persistence/` | 存储层 DTO 或 ORM 映射输入输出 |
| Shared enums | `backend/app/domain/enums/` | 统一状态、风险、牌位等枚举 |

## 4. API schema 清单

### 4.1 公共 schema

| Schema 名称 | 推荐文件 | 关键字段 | 用途 |
| --- | --- | --- | --- |
| `ErrorResponse` | `backend/app/schemas/api/common.py` | `error_code`、`message`、`details`、`trace_id`、`retryable` | 统一错误响应 |
| `HealthResponse` | `backend/app/schemas/api/health.py` | `status`、`service`、`version`、`environment`、`timestamp` | 健康检查响应 |

### 4.2 Reading 相关 schema

| Schema 名称 | 推荐文件 | 关键字段 | 用途 |
| --- | --- | --- | --- |
| `CreateReadingRequest` | `backend/app/schemas/api/readings.py` | `question`、`locale`、`spread_type`、`client_request_id`、`metadata` | 单次调用请求 |
| `ReadingQuestionPayload` | `backend/app/schemas/api/readings.py` | `raw_question`、`normalized_question` | 问题信息 |
| `ReadingClarificationPayload` | `backend/app/schemas/api/readings.py` | `required`、`question_text`、`answer_text` | 澄清摘要 |
| `ReadingCardPayload` | `backend/app/schemas/api/readings.py` | `position`、`card_code`、`card_name`、`orientation`、`interpretation` | 单张牌输出 |
| `ReadingSynthesisPayload` | `backend/app/schemas/api/readings.py` | `summary`、`action_advice`、`reflection_question` | 综合结果 |
| `ReadingSafetyPayload` | `backend/app/schemas/api/readings.py` | `risk_level`、`action_taken`、`review_notes` | 安全审查摘要 |
| `ReadingTraceSummaryPayload` | `backend/app/schemas/api/readings.py` | `event_count`、`warning_count`、`error_count` | trace 统计 |
| `ReadingResultResponse` | `backend/app/schemas/api/readings.py` | `reading_id`、`session_id`、`status`、`question`、`cards`、`synthesis`、`safety` | 阅读详情响应 |
| `ReadingTraceEventPayload` | `backend/app/schemas/api/traces.py` | `event_id`、`step_name`、`event_status`、`attempt_no`、`latency_ms`、`error_code`、`payload_summary`、`created_at` | trace 单事件 |
| `ReadingTraceResponse` | `backend/app/schemas/api/traces.py` | `reading_id`、`session_id`、`status`、`events` | trace 列表响应 |

### 4.3 Session 相关 schema

| Schema 名称 | 推荐文件 | 关键字段 | 用途 |
| --- | --- | --- | --- |
| `CreateSessionRequest` | `backend/app/schemas/api/sessions.py` | `locale`、`spread_type`、`metadata` | 创建会话请求 |
| `CreateSessionResponse` | `backend/app/schemas/api/sessions.py` | `session_id`、`status`、`locale`、`spread_type`、`created_at` | 创建会话响应 |
| `SubmitQuestionRequest` | `backend/app/schemas/api/sessions.py` | `raw_question` | 提交原始问题 |
| `SubmitQuestionResponse` | `backend/app/schemas/api/sessions.py` | `session_id`、`status`、`normalized_question`、`clarification_required`、`clarifier_question`、`updated_at` | Clarifier 判断结果 |
| `SubmitClarificationRequest` | `backend/app/schemas/api/sessions.py` | `answer_text`、`turn_index` | 澄清回答提交 |
| `SubmitClarificationResponse` | `backend/app/schemas/api/sessions.py` | `session_id`、`status`、`normalized_question`、`clarification_required`、`next_clarifier_question`、`updated_at` | 澄清处理结果 |
| `RunSessionRequest` | `backend/app/schemas/api/sessions.py` | 无业务字段 | 运行会话请求 |
| `SessionSnapshotResponse` | `backend/app/schemas/api/sessions.py` | `session_id`、`status`、`normalized_question`、`current_reading_id`、`clarification_turn_count`、`created_at`、`updated_at`、`completed_at` | 会话状态查询 |
| `SessionHistoryItemResponse` | `backend/app/schemas/api/sessions.py` | `message_id`、`message_type`、`sender_role`、`turn_index`、`content`、`created_at` | 历史条目 |
| `SessionHistoryResponse` | `backend/app/schemas/api/sessions.py` | `session_id`、`items` | 历史查询响应 |

## 5. Workflow schema 清单

### 5.1 共享枚举

| 枚举名称 | 推荐文件 | 取值 |
| --- | --- | --- |
| `WorkflowStatus` | `backend/app/domain/enums/workflow_status.py` | `CREATED`、`QUESTION_RECEIVED`、`CLARIFYING`、`READY_FOR_DRAW`、`DRAW_COMPLETED`、`SYNTHESIS_COMPLETED`、`SAFETY_REVIEWED`、`COMPLETED`、`SAFE_FALLBACK_RETURNED`、`FAILED` |
| `SpreadType` | `backend/app/domain/enums/spread_type.py` | `THREE_CARD_REFLECTION` |
| `RiskLevel` | `backend/app/domain/enums/risk_level.py` | `LOW`、`MEDIUM`、`HIGH` |
| `SafetyAction` | `backend/app/domain/enums/safety_action.py` | `PASSTHROUGH`、`REWRITE`、`BLOCK_AND_FALLBACK` |
| `CardOrientation` | `backend/app/domain/enums/card_orientation.py` | `UPRIGHT`、`REVERSED` |
| `CardPosition` | `backend/app/domain/enums/card_position.py` | `PAST`、`PRESENT`、`FUTURE` |
| `TraceEventStatus` | `backend/app/domain/enums/trace_event_status.py` | `STARTED`、`SUCCEEDED`、`FAILED`、`FALLBACK` |
| `SessionMessageType` | `backend/app/domain/enums/session_message_type.py` | `ORIGINAL_QUESTION`、`CLARIFIER_QUESTION`、`CLARIFICATION_ANSWER`、`FINAL_RESULT_SUMMARY` |
| `SenderRole` | `backend/app/domain/enums/sender_role.py` | `USER`、`AGENT`、`SYSTEM` |

### 5.2 Agent 输入输出 schema

| Schema 名称 | 推荐文件 | 关键字段 | 用途 |
| --- | --- | --- | --- |
| `ClarifierInput` | `agent/schemas/clarifier.py` | `raw_question`、`locale` | Clarifier 输入 |
| `ClarifierOutput` | `agent/schemas/clarifier.py` | `normalized_question`、`clarification_required`、`clarifier_question`、`confidence` | Clarifier 输出 |
| `DrawInput` | `agent/schemas/draw.py` | `normalized_question`、`spread_type`、`locale` | Draw and Interpret 输入 |
| `DrawCard` | `agent/schemas/draw.py` | `position`、`card_code`、`card_name`、`orientation`、`interpretation` | 单张牌结构 |
| `DrawOutput` | `agent/schemas/draw.py` | `cards`、`draw_summary` | Draw and Interpret 输出 |
| `SynthesisInput` | `agent/schemas/synthesis.py` | `normalized_question`、`cards` | Synthesis 输入 |
| `SynthesisOutput` | `agent/schemas/synthesis.py` | `summary`、`action_advice`、`reflection_question` | Synthesis 输出 |
| `SafetyReviewInput` | `agent/schemas/safety.py` | `summary`、`action_advice`、`reflection_question`、`normalized_question` | Safety Guard 输入 |
| `SafetyReviewOutput` | `agent/schemas/safety.py` | `risk_level`、`action_taken`、`safe_summary`、`safe_action_advice`、`safe_reflection_question`、`review_notes` | Safety Guard 输出 |

### 5.3 工作流上下文 schema

| Schema 名称 | 推荐文件 | 关键字段 | 用途 |
| --- | --- | --- | --- |
| `ClarificationTurnState` | `backend/app/schemas/workflow/tarot_workflow_state.py` | `turn_index`、`question_text`、`answer_text` | 澄清轮次 |
| `TraceEventPayload` | `backend/app/schemas/workflow/trace_event.py` | `step_name`、`event_status`、`attempt_no`、`latency_ms`、`error_code`、`payload` | 内部 trace DTO |
| `TarotWorkflowState` | `backend/app/schemas/workflow/tarot_workflow_state.py` | `session_id`、`reading_id`、`status`、`raw_question`、`normalized_question`、`clarification_turns`、`cards`、`synthesis_output`、`safety_output`、`trace_events` | Orchestrator 统一状态容器 |

### 5.4 额外约束

- `ClarifierOutput.clarifier_question` 只有在 `clarification_required=true` 时允许非空
- `DrawOutput.cards` 固定 3 张，且 `position` 不可重复
- `SafetyReviewOutput` 必须始终返回 `risk_level` 与 `action_taken`
- `ReadingResultResponse.synthesis` 永远表示 Safety Guard 处理后的最终可见文本
- `TarotWorkflowState.status` 只能取 `WorkflowStatus` 枚举

## 6. Persistence schema 清单

| Schema 名称 | 推荐文件 | 关键字段 | 用途 |
| --- | --- | --- | --- |
| `SessionRecord` | `backend/app/schemas/persistence/session.py` | `id`、`status`、`locale`、`spread_type`、`normalized_question`、`created_at`、`updated_at`、`completed_at` | 会话记录 |
| `SessionMessageRecord` | `backend/app/schemas/persistence/session.py` | `id`、`session_id`、`message_type`、`sender_role`、`turn_index`、`content`、`created_at` | 会话消息记录 |
| `ReadingRecord` | `backend/app/schemas/persistence/reading.py` | `id`、`session_id`、`status`、`normalized_question`、`summary`、`action_advice`、`reflection_question`、`risk_level`、`fallback_used`、`created_at`、`completed_at` | 阅读结果记录 |
| `ReadingCardRecord` | `backend/app/schemas/persistence/reading.py` | `id`、`reading_id`、`position`、`sort_order`、`card_code`、`card_name`、`orientation`、`interpretation`、`created_at` | 卡牌记录 |
| `SafetyReviewRecord` | `backend/app/schemas/persistence/safety_review.py` | `id`、`reading_id`、`risk_level`、`action_taken`、`review_notes`、`safe_output`、`created_at` | 安全审查记录 |
| `TraceEventRecord` | `backend/app/schemas/persistence/trace_event.py` | `id`、`session_id`、`reading_id`、`step_name`、`event_status`、`attempt_no`、`latency_ms`、`error_code`、`trace_payload`、`created_at` | trace 记录 |

## 7. PostgreSQL 最小表结构草案

### 7.1 设计原则

- 表名统一使用复数小写下划线
- 首期优先使用 `text` + 应用层枚举校验，不急于引入数据库 enum
- 所有主键统一由应用层生成 UUID
- 所有时间统一使用 `timestamptz`
- 所有删除级联只覆盖同一会话内的附属事实，不跨聚合传播

### 7.2 表结构草案

```sql
create table sessions (
    id uuid primary key,
    status text not null,
    locale text not null,
    spread_type text not null,
    normalized_question text null,
    created_at timestamptz not null,
    updated_at timestamptz not null,
    completed_at timestamptz null
);

create table session_messages (
    id uuid primary key,
    session_id uuid not null references sessions(id) on delete cascade,
    message_type text not null,
    sender_role text not null,
    turn_index integer not null,
    content text not null,
    created_at timestamptz not null
);

create table readings (
    id uuid primary key,
    session_id uuid not null unique references sessions(id) on delete cascade,
    status text not null,
    normalized_question text null,
    summary text null,
    action_advice text null,
    reflection_question text null,
    risk_level text not null,
    fallback_used boolean not null default false,
    created_at timestamptz not null,
    completed_at timestamptz null
);

create table reading_cards (
    id uuid primary key,
    reading_id uuid not null references readings(id) on delete cascade,
    position text not null,
    sort_order integer not null,
    card_code text not null,
    card_name text not null,
    orientation text not null,
    interpretation text not null,
    created_at timestamptz not null,
    unique (reading_id, position)
);

create table safety_reviews (
    id uuid primary key,
    reading_id uuid not null unique references readings(id) on delete cascade,
    risk_level text not null,
    action_taken text not null,
    review_notes text null,
    safe_output text null,
    created_at timestamptz not null
);

create table trace_events (
    id uuid primary key,
    session_id uuid not null references sessions(id) on delete cascade,
    reading_id uuid null references readings(id) on delete cascade,
    step_name text not null,
    event_status text not null,
    attempt_no integer not null,
    latency_ms integer null,
    error_code text null,
    trace_payload jsonb not null,
    created_at timestamptz not null
);
```

### 7.3 推荐索引

```sql
create index idx_sessions_status on sessions(status);
create index idx_session_messages_session_turn on session_messages(session_id, turn_index);
create index idx_readings_status on readings(status);
create index idx_trace_events_session_created on trace_events(session_id, created_at);
create index idx_trace_events_reading_created on trace_events(reading_id, created_at);
```

### 7.4 字段语义说明

#### `sessions`

- 表示一个完整的 Tarot Reflection 会话
- 阶段 0 冻结为“一次会话只对应一次阅读结果”
- `normalized_question` 用于在 `/sessions/{session_id}/run` 之前保存最近一次 Clarifier 产出的归一化问题

#### `session_messages`

- 存原始问题、Clarifier 提问、用户澄清回答、最终结果摘要
- `turn_index` 是会话内稳定顺序号，不是数据库分页号

#### `readings`

- 存最终阅读聚合结果
- `summary`、`action_advice`、`reflection_question` 存最终对用户可见的版本
- `fallback_used=true` 表示结果并非完全正常链路产物

#### `reading_cards`

- 每次阅读固定 3 条记录
- `position` 在同一个 `reading_id` 下唯一

#### `safety_reviews`

- 一次阅读只允许一条最终安全审查记录
- `safe_output` 用于保存被重写后的最终返回文本摘要

#### `trace_events`

- 允许在阅读结果尚未创建时先记 `session_id` 级事件，因此 `reading_id` 可为空
- `trace_payload` 用于存脱敏后的结构化上下文

## 8. 阶段 1 实施约束

阶段 1 开始编码时，应遵守以下约束：

- 不要重新发明第二套状态名或第二套枚举字符串
- 不要把 API schema 和 Agent 输出 schema 混在同一个文件里
- 不要把数据库表结构随实现便利随意增删字段，若要改动应先更新本契约文档
- 若某项实现无法满足本契约，应优先回到文档层修正，而不是让代码和文档分叉
