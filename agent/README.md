# Agent Module

`agent/` 是面向 `backend` 的多节点编排层。

它需要满足 `backend` 当前的调用方式：

- 由 `agent.workflows.TarotReflectionWorkflow` 提供统一入口
- 支持 `evaluate_question(...)`
- 支持 `continue_from_ready_state(...)`
- 支持 `run(...)`
- 返回 `backend.app.schemas.workflow.TarotWorkflowState`
- 在状态里持续写入 `trace_events`
- 在需要时触发前置安全检查、中间内容检查和最终安全审查

换句话说，`backend` 不直接调单个 agent node，而是依赖 `agent/` 产出一条完整、可持久化、可追踪的工作流状态。

## Package Layout

### `agent/__init__.py`

包级导出入口。

需要完成的事：

- 暴露上层需要导入的公共对象
- 避免调用方直接依赖过深的内部路径

作用：

- 让 `backend` 或测试代码通过稳定路径导入 `agent` 能力

### `agent/core/`

这一层放跨节点共享的基础设施，不负责具体业务编排。

#### `agent/core/__init__.py`

核心工具的统一导出。

需要完成的事：

- 汇总 `core` 下对外可用的对象

作用：

- 提供稳定的核心能力访问入口

#### `agent/core/model_gateway.py`

模型调用抽象层。

需要完成的事：

- 定义统一的模型调用接口
- 屏蔽 OpenAI 或其他模型提供方的具体差异
- 承载调用上下文、超时、重试、观测信息

作用：

- 让各个 node 只关心“调用模型并得到结果”，不关心底层 SDK

#### `agent/core/prompt_registry.py`

Prompt 资源注册与加载层。

需要完成的事：

- 从 `prompts/` 或其他约定目录加载 prompt
- 提供按名称查找、列出 prompt 的能力
- 后续支持 prompt 版本化

作用：

- 避免 prompt 散落在 node 代码中

#### `agent/core/schemas.py`

Agent 侧的安全与信任域模型。

需要完成的事：

- 定义输入安全检查所需的数据结构
- 定义内容来源、信任等级、安全决策等通用类型

作用：

- 支撑 `security/` 和部分 safety node
- 提供 agent 内部的安全语义

说明：

- 这里的类型主要服务 agent 内部安全域，不直接等同于 backend 的工作流枚举

#### `agent/core/trust.py`

内容信任标签工具。

需要完成的事：

- 给用户输入、系统内容、agent 输出打上来源和 trust level
- 支持 sanitized/untrusted/trusted 等状态转换

作用：

- 让安全检查不仅看文本，还能看内容来源和信任状态

### `agent/schemas/`

这一层放面向业务节点的结构化输入输出模型。

它们最终需要能无缝映射到 `TarotWorkflowState`，从而满足 backend 的持久化和 API 响应要求。

#### `agent/schemas/__init__.py`

统一导出节点 schema。

需要完成的事：

- 汇总 clarifier、draw、synthesis、safety 的 schema

作用：

- 给 workflow 和 node 提供稳定导入入口

#### `agent/schemas/clarifier.py`

Clarifier 节点的输入输出模型。

需要完成的事：

- 定义原始问题输入结构
- 定义澄清结果结构

作用：

- 支撑 `clarifier` 节点产出 `normalized_question`
- 支撑 backend 的 `CLARIFYING / READY_FOR_DRAW` 分支

#### `agent/schemas/draw.py`

Draw & Interpret 节点模型。

需要完成的事：

- 定义抽牌输入
- 定义卡牌与解释输出

作用：

- 产出 backend 需要落库的牌阵和解释结果

#### `agent/schemas/synthesis.py`

Synthesis 节点模型。

需要完成的事：

- 定义综合解读输入
- 定义总结、行动建议、反思问题输出

作用：

- 为 backend 的最终阅读结果提供结构化综合内容

#### `agent/schemas/safety.py`

最终安全审查节点模型。

需要完成的事：

- 定义送入安全审查的内容
- 定义安全审查后的安全输出、风险等级和动作

作用：

- 为 backend 的 `safety_output` 和安全回退路径提供统一结构

### `agent/security/`

这一层放与具体业务节点解耦的安全规则与预处理逻辑。

#### `agent/security/detectors.py`

规则检测器集合。

需要完成的事：

- 识别 prompt injection
- 识别 secret exfiltration
- 识别 role escalation
- 识别 instruction override
- 识别其他可疑模式

作用：

- 为 pre-input 和中间内容安全检查提供基础检测能力

#### `agent/security/pre_input_guard.py`

输入前安全决策器。

需要完成的事：

- 基于 detectors 汇总风险
- 给出 `continue / rewrite / block` 决策

作用：

- 决定用户原始输入能否进入主工作流

#### `agent/security/sanitizer.py`

输入清洗器。

需要完成的事：

- 删除危险片段
- 保留尽可能多的合法占卜意图
- 输出清洗后的问题与元数据

作用：

- 支撑 `rewrite` 路径
- 让 clarifier 优先处理清洗后的问题，而不是危险原文

### `agent/nodes/`

这一层放 LangGraph 的节点执行器。

每个文件只负责一个步骤的输入消费、状态更新、trace 记录和异常回退。

理想状态下，业务逻辑逐步从 `workflows/orchestrator.py` 下沉到这里。

#### `agent/nodes/__init__.py`

节点执行器统一导出。

需要完成的事：

- 汇总当前 workflow 会调用的节点函数

作用：

- 让 orchestrator 通过统一入口接入节点

#### `agent/nodes/pre_input_security.py`

输入前安全节点。

需要完成的事：

- 复用 `security_orchestrator` 的预检查流水线
- 把结果写入 `TarotWorkflowState`
- 在 `continue / rewrite / block` 三种结果之间切换
- 记录输入安全 trace

作用：

- 实现 question graph 的第一层安全防护

#### `agent/nodes/clarifier.py`

澄清节点执行器。

需要完成的事：

- 消费 `effective_question` 或 `raw_question`
- 调用 clarifier agent
- 更新 `clarification_output`、`normalized_question`、`status`
- 记录 clarifier trace
- 在失败时做 fallback

作用：

- 驱动 backend 的问题评估阶段

#### `agent/nodes/draw_and_interpret.py`

抽牌与解释节点执行器。

需要完成的事：

- 消费已澄清的问题
- 调用 draw agent
- 写入 `cards` 和 `draw_output`
- 记录 draw trace
- 在失败时有限重试并回退

作用：

- 为 backend 的 reading 主流程产出卡牌结果

#### `agent/nodes/intermediate_security.py`

中间内容安全节点。

需要完成的事：

- 检查 draw 输出到 synthesis 之间传递的内容
- 识别可疑 agent-to-agent handoff
- 必要时提前中断流程
- 记录中间安全 trace

作用：

- 满足“安全检查不只在最后一步做”的要求

#### `agent/nodes/synthesis.py`

综合解读节点。

需要完成的事：

- 消费卡牌解释结果
- 产出综合总结、行动建议、反思问题
- 更新 `synthesis_output`
- 记录 synthesis trace

作用：

- 为 backend 最终返回内容提供结构化综合结果

当前状态：

- 这是后续应继续完善的节点文件

#### `agent/nodes/safety_guard.py`

最终安全审查节点与安全回退工具。

需要完成的事：

- 提供统一的安全 fallback 文案和元数据
- 后续实现最终输出的风险审查与改写
- 在必要时阻断或降级最终输出

作用：

- 实现最终输出层的安全保护
- 为 workflow 提供统一 fallback 语义

### `agent/workflows/`

这一层放工作流编排，不放具体业务细节。

它需要直接满足 backend 对 workflow 类的依赖。

#### `agent/workflows/__init__.py`

工作流导出入口。

需要完成的事：

- 暴露 `TarotReflectionWorkflow`
- 暴露 graph 构建函数

作用：

- 让 backend 通过稳定路径导入 workflow

#### `agent/workflows/orchestrator.py`

主工作流编排器。

需要完成的事：

- 提供 backend 依赖的统一入口方法
- 维护 LangGraph 图
- 组织 question graph 和 ready-state graph
- 决定节点顺序与条件分支
- 生成 `TarotWorkflowState`
- 写入 `trace_events`
- 在需要时提前结束流程

作用：

- 这是 `backend` 与 `agent` 之间最核心的桥梁

对 backend 的直接承诺：

- `run(...)`
- `evaluate_question(...)`
- `continue_from_ready_state(...)`

#### `agent/workflows/security_orchestrator.py`

安全流水线适配器。

需要完成的事：

- 封装输入前安全处理的标准流程
- 提供 `continue / rewrite / block` 的统一结果格式
- 支撑 node 或外部调用方复用同一套安全逻辑

作用：

- 不是主工作流编排器
- 是可复用的安全 pipeline helper

### `agent/tests/`

这一层放 agent 侧的单元测试和工作流回归测试。

#### `agent/tests/test_prompt_injection.py`

安全检测器测试。

需要完成的事：

- 验证 detectors 能识别典型 prompt injection 输入

作用：

- 保证输入安全规则不会悄悄失效

#### `agent/tests/test_workflow_stub.py`

工作流构造与占位测试。

需要完成的事：

- 后续补 workflow graph 层面的基础覆盖

作用：

- 为 agent 侧的工作流测试预留位置

## How Agent Satisfies Backend

为了满足 backend 当前实现，`agent/` 必须持续保证以下契约：

1. `agent.workflows.TarotReflectionWorkflow` 可被直接实例化。
2. workflow 方法返回 `TarotWorkflowState`，字段可供 backend repository 持久化。
3. 工作流状态中持续产出 `trace_events`，供 backend trace API 和日志使用。
4. question 阶段能够区分：
   - `CLARIFYING`
   - `READY_FOR_DRAW`
   - `SAFE_FALLBACK_RETURNED`
5. ready-state 阶段能够区分：
   - `COMPLETED`
   - `SAFE_FALLBACK_RETURNED`
6. 安全链路至少覆盖：
   - 输入前安全检查
   - agent 间中间内容安全检查
   - 最终输出安全审查

只要这些契约保持稳定，`agent` 内部各 node 的具体实现可以继续演进，而不需要频繁改动 backend。
