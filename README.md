# AI Tarot Multi-Agent System

## 1.项目简介

**AI Tarot Multi-Agent System 是一个面向用户反思与自我探索场景的多智能体系统**

**系统通过前端 Web UI 与用户交互，围绕用户提出的问题，调用多个具有不同职责的 Agent 协同完成问题澄清、抽牌解读、综合建议生成与安全审查，最终输出结构化、可解释、具备安全约束的 Tarot Reflection 结果.**

**本项目重点不在“预测未来”，而在于通过多智能体协作提供一种结构化反思Structured Reflection体验。**

**系统同时纳入以下工程化考量:**

- **Multi-Agent System 设计**
- **Agent Cybersecurity**
- **MLOps / LLMOps（Langfuse 可观测性已集成）**
- **前端交互式 UI**
- **可观测性与 Traceability**
- **安全输出与风险控制**

> 快速启动与开发说明请参阅 [Developer-Guide.md](./Developer-Guide.md)。

## 2.项目目标

**本项目的目标包括:**

**1. 构建一个可运行的Multi-Agent System, 由多个具备明确职责边界的Agent协同工作, 完成用户问题处理流程**

**2. 构建一个前端UI, 使用户可以通过网页与Agent System交互, 而不是仅通过命令行演示**

**3. 提供可解释的推理过程, 输出结果中应该体现卡牌依据, 总结逻辑和安全处理痕迹.**

**4. 纳入Agent Cybersecurity 设计,考虑Prompt Injection, 越权输出,敏感建议等问题,并设计防护机制**

**5. 纳入MLOps/LLMOps实践, 包括Prompt Versioning, 模型配置管理,评测集,回归测试,日志监控等等**

## 3.项目范围

### 3.1 本期范围[In Scope]

- **Web 前端用户交互界面**
- **多 Agent 协作流程** 
- **用户问题输入与澄清**  
- **三张牌抽取与解读** 
- **综合建议与反思问题生成**  
- **安全审查与安全模式输出**   
- **基础评测与回归测试**  
- **Docker 化部署**  
- **GitHub Actions 基础 CI**

## 3.2 非本期范围[Out of Scope]

- **复杂多租户权限系统**  
- **大规模生产级高并发部署**  
- **自训练大模型**

## 4.系统核心能力

**本系统核心能力（✅ 已实现）:**

- ✅ **Clarification**：对用户模糊问题进行澄清（LLM 驱动，支持多轮）
- ✅ **Card Draw & Interpretation**：执行抽牌并生成牌义解释（含 keywords / caution_note / reflection_question）
- ✅ **Synthesis**：基于多张牌生成综合洞察与行动建议
- ✅ **Safety Review**：对输出进行安全审查与风险修正（LLM 语义评估，规则引擎兜底，三级风险）
- ✅ **Trace Logging**：结构化 JSON 日志 + Langfuse 全链路追踪
- ✅ **Frontend Interaction**：通过 Web UI 展示完整使用流程
- ✅ **Agent Cybersecurity**：LLM 驱动的三层安全检测（输入注入、Agent 间内容审查、输出安全审查），各层均有规则引擎兜底

## 5.系统角色划分

**当前系统规划包含以下主要角色:**

### 5.1 用户侧

* **End User: 提出问题,完成澄清,查看结果**

### 5.2 系统侧

* **Frontend UI: 负责用户输入,流程引导和结果展示**

* **Backend API: 负责前后端数据交互和会话管理**

* **Orchestrator: 负责Agent调度和流程控制**

* **Clarifier Agent: 负责问题澄清**

* **Draw & Interpret Agent: 负责抽牌和单牌解释**

* **Synthesis Agent: 负责综合分析与建议生成**

* **Safety Guard Agent: 负责风险识别,安全审查以及输出修正**

* **Model Gateway: 统一管理模型调用,参数和日志**

* **Storage: 负责存储结果**

## 6.技术栈推荐

### 前端

**TypeScript [AI 负责]**

### 后端

* **Language:  Python + FastAPI**

### Multi-Agent

* **LangGraph: 负责多Agent工作流编排**

* **OpenAI: 提供大预言模型能力**

* **自定义Model Gateway: 统一管理模型调用,封装不同模型提供商的调用方式,统一参数配置等等, 方便未来替换模型[次重要]**

### 数据存储

* **PostgreSQL: 存储用户对话、澄清结果、抽牌结果等**

### 测试

* **PyTest: 做后端的单元测试和集成测试**

* **Promptfoo: 做Prompt和LLM输出回归测试**

### 可观测性

* **Langfuse v2: 记录和观察LLM的调用过程（Trace → Span → Generation 三层追踪，本地 Docker 容器，访问 http://localhost:3000）**

* **结构化JSON Logs: 统一系统日志格式和Agent输出**

### 部署

* **Docker Compose**

* **Github Actions: 用来跑CI/CD**

## 7.仓库结构

```
project-root/
├── README.md
├── Developer-Guide.md      # 开发者指南（快速启动、架构说明、各模块开发规范）
├── frontend/               # React + TypeScript UI
├── backend/                # FastAPI + SQLAlchemy + Alembic
├── agent/                  # LangGraph 工作流 + LLM Agents
├── prompts/                # Prompt 模板文件（独立于代码管理）
├── evals/                  # Promptfoo eval 套件
├── docs/                   # 设计文档
├── Docker/
│   └── docker-compose.yml  # 全栈编排（postgres + backend + frontend + langfuse）
└── .github/workflows/      # GitHub Actions CI
```

### 7.1 Frontend/

**存放前端Web UI代码（React + TypeScript + Vite）**

**已实现页面：**

* **用户输入问题页面**
* **澄清问题交互页面**
* **抽牌与解读展示页面（含 caution_note / reflection_question / keywords）**
* **综合结果展示页面**

### 7.2 Backend/

**存放后端API和业务逻辑代码**

### 7.3 Agent/

**存放多 Agent 系统的核心逻辑**。 

**主要内容：**

- **Agent 定义**

- **Agent 的输入输出 Schema**

- **Orchestrator / Workflow 编排逻辑**

- **状态机或 LangGraph 流程**

- **安全策略触发逻辑**

- **Agent 间数据传递逻辑**

### 7.4 Prompts/

**存放 Prompt 模板和版本化管理内容,避免prompt写死在代码里**

**主要内容：**

- **各 Agent 使用的 Prompt 模板**

- **system prompt**

- **output format instructions**

- **安全重写 prompt**

- **prompt 版本说明文档**

### 7.5 Evals/

**存放评测数据和评测脚本。**  

**主要内容：**

- **测试样例集**

- **Prompt 回归测试**

- **安全测试样例**

- **输出质量检查脚本**

- **自动评测结果**

### 7.6 Docs/

**存放项目开发文档**。

### 7.7 Docker/

**存放与容器化相关的配置文件**

`docker-compose.yml` 编排了以下服务：`postgres`（业务数据库）、`backend`（FastAPI）、`frontend`（React）、`langfuse-db`（Langfuse 专用 PostgreSQL）、`langfuse-server`（LLM 可观测性面板）。

### 7.8 .github/workflows/

**存放 GitHub Actions 的 CI/CD 工作流配置**

CI 包含四个 job：

| Job | 内容 |
|-----|------|
| `lint` | ruff 代码风格检查 |
| `test-agent` | Agent 单元测试（无需数据库、无需 API key） |
| `test-backend-unit` | Backend 单元测试（SQLite 内存库） |
| `test-backend-integration` | Backend 集成测试，由 service container 提供 PostgreSQL |

集成测试通过 `DATABASE_URL` 环境变量连接数据库；本地运行时若未设置该变量，相关测试会自动 skip。
