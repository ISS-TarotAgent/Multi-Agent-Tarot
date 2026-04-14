# Multi-Agent-Tarot API 接口契约

## 1. 文档目标

本文档用于完成 `docs/05-Backend-Build-Plan.md` 中阶段 0 的 API 契约冻结工作。

目标不是描述“将来可能怎么做”，而是给出当前仓库可以直接据此编码的接口协议，作为后端、前端、测试和后续 OpenAPI 生成的统一真相源。

关联文档：

- 架构职责与运行边界见 `docs/04-System-Architecture.md`
- 工作流状态机、Pydantic schema 清单、PostgreSQL 草案见 `docs/06-Backend-Contract-Freeze.md`

## 2. 阶段 0 冻结范围

当前阶段只冻结课程项目首期需要的接口契约，不引入额外复杂度。

- 基础路径固定为 `/api/v1`
- 所有请求与响应固定为 `application/json`
- 阶段 0 不包含鉴权、用户体系、分页历史筛选、异步任务队列、WebSocket、流式输出
- 阶段 1 和阶段 2 可以基于本契约编码，不应再反向修改字段语义

## 3. 通用约定

### 3.1 编码与时间

- 字符编码统一为 UTF-8
- 时间字段统一使用 ISO 8601 UTC 字符串，例如 `2026-04-03T09:30:00Z`
- 所有资源主键统一使用后端生成的 UUID 字符串

### 3.2 JSON 命名

- 字段名统一使用 `snake_case`
- 枚举值统一使用大写下划线风格，例如 `COMPLETED`、`SAFE_FALLBACK_RETURNED`

### 3.3 响应风格

为保持 KISS，本项目不使用额外的通用 envelope。

- 成功响应直接返回资源对象
- 失败响应统一返回 `ErrorResponse`

### 3.4 错误响应模型

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `error_code` | `string` | 是 | 稳定错误码，供前后端和测试使用 |
| `message` | `string` | 是 | 面向开发者的错误描述 |
| `details` | `object \| null` | 否 | 补充上下文，例如字段错误、状态冲突信息 |
| `trace_id` | `string \| null` | 否 | 本次请求或工作流追踪标识 |
| `retryable` | `boolean` | 是 | 是否建议重试 |

错误响应示例：

```json
{
  "error_code": "INVALID_STATE_TRANSITION",
  "message": "Session is not ready to run the reading workflow.",
  "details": {
    "session_id": "2c3e5a0b-c4ef-47b0-88a3-bfe0f4d3d176",
    "current_status": "CLARIFYING"
  },
  "trace_id": "req_5d3d93ce6f5e",
  "retryable": false
}
```

### 3.5 统一错误码

| HTTP 状态码 | `error_code` | 说明 |
| --- | --- | --- |
| `400` | `INVALID_REQUEST` | 请求体缺失、字段类型错误、文本为空等 |
| `404` | `RESOURCE_NOT_FOUND` | `reading_id` 或 `session_id` 不存在 |
| `409` | `INVALID_STATE_TRANSITION` | 状态不允许当前操作 |
| `422` | `SCHEMA_VALIDATION_FAILED` | Agent 输出或内部结构校验失败 |
| `502` | `MODEL_GATEWAY_ERROR` | 外部模型调用失败且未完成安全降级 |
| `503` | `DEPENDENCY_UNAVAILABLE` | PostgreSQL、Langfuse 等依赖不可用 |

## 4. 领域资源总览

### 4.1 Reading 资源

`Reading` 表示一次完整的 Tarot Reflection 结果，包含用户问题、抽牌结果、综合建议、安全审查摘要和 trace 摘要。

终态只允许以下三种：

- `COMPLETED`
- `SAFE_FALLBACK_RETURNED`
- `FAILED`

### 4.2 Session 资源

`Session` 表示一次会话式交互过程。一个会话只对应一次最终阅读结果。

中间状态见 `docs/06-Backend-Contract-Freeze.md` 中的状态机定义。

### 4.3 Trace 资源

`Trace` 用于暴露结构化流程事件摘要，服务调试、测试、演示和回归比对，不直接暴露完整日志文件。

## 5. MVP 单次调用接口

### 5.1 `GET /api/v1/health`

用途：检查后端服务基础可用性。

成功响应字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `status` | `string` | 是 | 固定为 `ok` |
| `service` | `string` | 是 | 服务名，固定为 `multi-agent-tarot-backend` |
| `version` | `string` | 是 | 当前后端版本号 |
| `environment` | `string` | 是 | 当前环境，例如 `local` |
| `timestamp` | `string` | 是 | 服务器 UTC 时间 |

响应示例：

```json
{
  "status": "ok",
  "service": "multi-agent-tarot-backend",
  "version": "0.1.0",
  "environment": "local",
  "timestamp": "2026-04-03T09:30:00Z"
}
```

### 5.2 `POST /api/v1/readings`

用途：同步执行完整主链路，直接返回最终阅读结果。

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `question` | `string` | 是 | 用户原始问题，长度 1 到 2000 |
| `locale` | `string` | 否 | 语言环境，默认 `zh-CN` |
| `spread_type` | `string` | 否 | 阶段 0 固定为 `THREE_CARD_REFLECTION` |
| `client_request_id` | `string \| null` | 否 | 客户端幂等排查用标识 |
| `metadata` | `object \| null` | 否 | 非业务核心扩展字段，阶段 0 只透传不解释 |

请求示例：

```json
{
  "question": "最近在工作选择上很犹豫，我应该继续坚持当前方向吗？",
  "locale": "zh-CN",
  "spread_type": "THREE_CARD_REFLECTION",
  "client_request_id": "web-demo-0001"
}
```

#### 成功响应

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `reading_id` | `string` | 是 | 阅读结果 ID |
| `session_id` | `string` | 是 | 后端内部自动创建的会话 ID |
| `status` | `string` | 是 | `COMPLETED`、`SAFE_FALLBACK_RETURNED` 或 `FAILED` |
| `locale` | `string` | 是 | 与请求一致 |
| `spread_type` | `string` | 是 | 当前固定为 `THREE_CARD_REFLECTION` |
| `question.raw_question` | `string` | 是 | 原始问题 |
| `question.normalized_question` | `string \| null` | 否 | Clarifier 归一化后的问题 |
| `clarification.required` | `boolean` | 是 | 单次调用模式下是否曾触发澄清判断 |
| `clarification.question_text` | `string \| null` | 否 | 若 Clarifier 生成过澄清问题，则返回文本 |
| `clarification.answer_text` | `string \| null` | 否 | 单次调用模式下固定为 `null` |
| `cards` | `array` | 是 | 三张牌结果；失败时允许为空数组 |
| `synthesis.summary` | `string \| null` | 否 | 总结性洞察 |
| `synthesis.action_advice` | `string \| null` | 否 | 行动建议 |
| `synthesis.reflection_question` | `string \| null` | 否 | 反思问题 |
| `safety.risk_level` | `string` | 是 | `LOW`、`MEDIUM`、`HIGH` |
| `safety.action_taken` | `string` | 是 | `PASSTHROUGH`、`REWRITE`、`BLOCK_AND_FALLBACK` |
| `safety.review_notes` | `string \| null` | 否 | 安全审查摘要 |
| `trace_summary.event_count` | `integer` | 是 | trace 事件总数 |
| `trace_summary.warning_count` | `integer` | 是 | warning 数量 |
| `trace_summary.error_count` | `integer` | 是 | error 数量 |
| `created_at` | `string` | 是 | 阅读创建时间 |
| `completed_at` | `string \| null` | 否 | 工作流结束时间 |

`cards` 数组元素字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `position` | `string` | 是 | `PAST`、`PRESENT`、`FUTURE` |
| `card_code` | `string` | 是 | 稳定卡牌编码 |
| `card_name` | `string` | 是 | 展示用名称 |
| `orientation` | `string` | 是 | `UPRIGHT` 或 `REVERSED` |
| `interpretation` | `string` | 是 | 单牌解释 |

结果可见性规则：

- `synthesis` 中的字段始终表示最终对用户可见的内容
- 如果 Safety Guard 执行了重写或保护性降级，API 仍只返回重写后的最终文本
- 安全审查前的原始综合文本不通过对外接口暴露

响应示例：

```json
{
  "reading_id": "7f6c4a8a-8f90-4f8f-98b5-20bc7c2a4c5d",
  "session_id": "5aee6c02-f347-4ba0-baae-0d7d86ee3f4a",
  "status": "COMPLETED",
  "locale": "zh-CN",
  "spread_type": "THREE_CARD_REFLECTION",
  "question": {
    "raw_question": "最近在工作选择上很犹豫，我应该继续坚持当前方向吗？",
    "normalized_question": "我是否应该继续投入当前职业路径，以及接下来更合适的行动重点是什么？"
  },
  "clarification": {
    "required": false,
    "question_text": null,
    "answer_text": null
  },
  "cards": [
    {
      "position": "PAST",
      "card_code": "the_fool",
      "card_name": "愚者",
      "orientation": "UPRIGHT",
      "interpretation": "过去的你更重视尝试和可能性。"
    },
    {
      "position": "PRESENT",
      "card_code": "two_of_wands",
      "card_name": "权杖二",
      "orientation": "UPRIGHT",
      "interpretation": "你正处在评估方向和资源的阶段。"
    },
    {
      "position": "FUTURE",
      "card_code": "strength",
      "card_name": "力量",
      "orientation": "UPRIGHT",
      "interpretation": "后续更需要稳住节奏，而不是被焦虑推动。"
    }
  ],
  "synthesis": {
    "summary": "继续当前方向是可行的，但前提是先缩小决策范围并把下一步行动具体化。",
    "action_advice": "先明确三周内要验证的一件关键事项，再决定是否继续追加投入。",
    "reflection_question": "如果不再被“必须马上做对”的压力推动，你会先验证哪一步？"
  },
  "safety": {
    "risk_level": "LOW",
    "action_taken": "PASSTHROUGH",
    "review_notes": null
  },
  "trace_summary": {
    "event_count": 8,
    "warning_count": 0,
    "error_count": 0
  },
  "created_at": "2026-04-03T09:30:00Z",
  "completed_at": "2026-04-03T09:30:04Z"
}
```

#### 状态语义

- `COMPLETED`：主链路完成，返回正常结果
- `SAFE_FALLBACK_RETURNED`：主链路部分失败或安全审查拦截，但系统已返回保护性结果
- `FAILED`：最终未能形成可返回结果，但阅读记录与 trace 已落库

#### 失败响应

- `400 INVALID_REQUEST`
- `422 SCHEMA_VALIDATION_FAILED`
- `503 DEPENDENCY_UNAVAILABLE`

### 5.3 `GET /api/v1/readings/{reading_id}`

用途：查询某次已创建阅读的最终状态和结果。

#### 路径参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `reading_id` | `string` | 阅读结果 ID |

#### 成功响应

返回结构与 `POST /api/v1/readings` 成功响应完全一致。

#### 失败响应

- `404 RESOURCE_NOT_FOUND`

### 5.4 `GET /api/v1/readings/{reading_id}/trace`

用途：查询工作流 trace 摘要。

#### 成功响应

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `reading_id` | `string` | 是 | 阅读结果 ID |
| `session_id` | `string` | 是 | 所属会话 ID |
| `status` | `string` | 是 | 阅读当前状态 |
| `events` | `array` | 是 | 时间顺序排列的 trace 事件 |

`events` 数组元素字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `event_id` | `string` | 是 | 事件 ID |
| `step_name` | `string` | 是 | 例如 `clarifier`、`draw_interpreter` |
| `event_status` | `string` | 是 | `STARTED`、`SUCCEEDED`、`FAILED`、`FALLBACK` |
| `attempt_no` | `integer` | 是 | 当前步骤第几次尝试，从 1 开始 |
| `latency_ms` | `integer \| null` | 否 | 步骤耗时 |
| `error_code` | `string \| null` | 否 | 若失败或 fallback，则返回稳定错误码 |
| `payload_summary` | `object` | 是 | 经过脱敏后的事件摘要 |
| `created_at` | `string` | 是 | 事件时间 |

响应示例：

```json
{
  "reading_id": "7f6c4a8a-8f90-4f8f-98b5-20bc7c2a4c5d",
  "session_id": "5aee6c02-f347-4ba0-baae-0d7d86ee3f4a",
  "status": "COMPLETED",
  "events": [
    {
      "event_id": "940cf6bd-2d6e-4558-b1cb-7f9c836f5ea3",
      "step_name": "clarifier",
      "event_status": "SUCCEEDED",
      "attempt_no": 1,
      "latency_ms": 612,
      "error_code": null,
      "payload_summary": {
        "clarification_required": false
      },
      "created_at": "2026-04-03T09:30:00Z"
    }
  ]
}
```

#### 失败响应

- `404 RESOURCE_NOT_FOUND`

## 6. 会话式接口

会话式接口是阶段 2 的目标，但必须在阶段 0 先冻结契约，避免后续和 MVP 单次调用分叉。

### 6.1 `POST /api/v1/sessions`

用途：创建空白会话。

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `locale` | `string` | 否 | 默认 `zh-CN` |
| `spread_type` | `string` | 否 | 默认 `THREE_CARD_REFLECTION` |
| `metadata` | `object \| null` | 否 | 扩展元数据 |

#### 成功响应

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `session_id` | `string` | 是 | 会话 ID |
| `status` | `string` | 是 | 固定为 `CREATED` |
| `locale` | `string` | 是 | 当前会话语言 |
| `spread_type` | `string` | 是 | 当前牌阵类型 |
| `created_at` | `string` | 是 | 创建时间 |

### 6.2 `POST /api/v1/sessions/{session_id}/question`

用途：提交用户原始问题，并触发 Clarifier 做充分性判断。

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `raw_question` | `string` | 是 | 用户原始问题 |

#### 成功响应

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `session_id` | `string` | 是 | 会话 ID |
| `status` | `string` | 是 | `CLARIFYING` 或 `READY_FOR_DRAW` |
| `normalized_question` | `string \| null` | 否 | Clarifier 归一化后的问题 |
| `clarification_required` | `boolean` | 是 | 是否需要继续澄清 |
| `clarifier_question` | `string \| null` | 否 | 下一条澄清问题 |
| `updated_at` | `string` | 是 | 更新时间 |

状态规则：

- 若问题足够明确，直接进入 `READY_FOR_DRAW`
- 若需要补充上下文，进入 `CLARIFYING`
- 若 Clarifier 失败，则记录 warning trace，并使用原始问题进入 `READY_FOR_DRAW`

### 6.3 `POST /api/v1/sessions/{session_id}/clarifications`

用途：提交澄清回答。

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `answer_text` | `string` | 是 | 用户澄清回答 |
| `turn_index` | `integer` | 是 | 第几轮澄清，从 1 开始 |

#### 成功响应

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `session_id` | `string` | 是 | 会话 ID |
| `status` | `string` | 是 | `CLARIFYING` 或 `READY_FOR_DRAW` |
| `normalized_question` | `string \| null` | 否 | 当前归一化问题 |
| `clarification_required` | `boolean` | 是 | 是否仍需继续澄清 |
| `next_clarifier_question` | `string \| null` | 否 | 若仍需澄清，则返回下一问 |
| `updated_at` | `string` | 是 | 更新时间 |

### 6.4 `POST /api/v1/sessions/{session_id}/run`

用途：从当前状态继续执行到生成最终结果。

#### 请求体

阶段 0 冻结为“无业务字段的空对象”：

```json
{}
```

#### 成功响应

返回结构与 `GET /api/v1/readings/{reading_id}` 一致。

#### 失败响应

- `404 RESOURCE_NOT_FOUND`
- `409 INVALID_STATE_TRANSITION`

### 6.5 `GET /api/v1/sessions/{session_id}`

用途：查询会话当前状态。

#### 成功响应

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `session_id` | `string` | 是 | 会话 ID |
| `status` | `string` | 是 | 当前会话状态 |
| `locale` | `string` | 是 | 会话语言 |
| `spread_type` | `string` | 是 | 牌阵类型 |
| `normalized_question` | `string \| null` | 否 | 当前归一化问题 |
| `current_reading_id` | `string \| null` | 否 | 若已进入执行阶段，则返回关联阅读 ID |
| `clarification_turn_count` | `integer` | 是 | 已完成澄清轮数 |
| `created_at` | `string` | 是 | 创建时间 |
| `updated_at` | `string` | 是 | 更新时间 |
| `completed_at` | `string \| null` | 否 | 完成时间 |

### 6.6 `GET /api/v1/sessions/{session_id}/result`

用途：查询当前会话的最终结果。

#### 成功响应

返回结构与 `GET /api/v1/readings/{reading_id}` 一致。

#### 失败响应

- `404 RESOURCE_NOT_FOUND`
- `409 INVALID_STATE_TRANSITION`

`409` 表示会话尚未进入终态。

### 6.7 `GET /api/v1/sessions/{session_id}/history`

用途：查询当前会话的消息历史。

#### 成功响应

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `session_id` | `string` | 是 | 会话 ID |
| `items` | `array` | 是 | 按时间排序的历史条目 |

`items` 数组元素字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `message_id` | `string` | 是 | 消息 ID |
| `message_type` | `string` | 是 | `ORIGINAL_QUESTION`、`CLARIFIER_QUESTION`、`CLARIFICATION_ANSWER`、`FINAL_RESULT_SUMMARY` |
| `sender_role` | `string` | 是 | `USER`、`AGENT`、`SYSTEM` |
| `turn_index` | `integer` | 是 | 会话内顺序号 |
| `content` | `string` | 是 | 消息内容 |
| `created_at` | `string` | 是 | 创建时间 |

## 7. 状态约束

接口必须遵守以下状态约束：

- `POST /api/v1/sessions/{session_id}/question` 只允许在 `CREATED` 执行
- `POST /api/v1/sessions/{session_id}/clarifications` 只允许在 `CLARIFYING` 执行
- `POST /api/v1/sessions/{session_id}/run` 只允许在 `READY_FOR_DRAW` 执行
- `GET /api/v1/sessions/{session_id}/result` 只允许在终态返回结果，否则返回 `409`

## 8. 与阶段 1 和阶段 2 的衔接约束

- 阶段 1 实现健康检查和基础 FastAPI app 时，不得改动本文件字段名
- 阶段 2 实现会话能力时，应优先复用 `Reading` 结果结构，避免两套结果格式
- 如果未来需要流式输出，应新增接口或明确版本升级，而不是直接改写现有同步响应
