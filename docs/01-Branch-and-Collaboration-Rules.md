# 分支管理说明

**为了避免团队开发中陷入分支管理混乱,接下来的部分是对在Github上进行开发的分支管理说明,在开发期间应该严格遵循该要求,避免出现分支冲突的问题**

## 1.长期分支

**在长期分支上的代码都需要经过审核且是验证后可使用的版本,所有的长期分支都需要进行严格的控制**

### Main分支

**main分支上的代码永远是可演示和相对稳定的版本,只存放已经通过测试,适合展示或提交的代码**

**规则:**

* **不允许直接Push**

* **只能提供PR进行合并**

* **合并前需要经过基本检查[需要Code Reviewer]**

### Develop分支

**Develop分支上主要是日常开发的主分支,所有的功能分支合并到这里,也是所有Sprint的集成分支**

**规则:**

* **不允许直接Push**

* **所有的开发分支先合并到develop分支**

* **每个Sprint结束后,从develop整理后合并到main分支**

### Release分支

**存放开发过程中的某阶段的稳定分支,专门做bugfix等工作**

**规则:**

* **只允许修复问题,不允许在代码中加大功能**

* **完成后合并到main分支**

## 2.短期分支

**所有的开发分支应该从develop上拉分支,以分支类型/任务编号-简短描述来命名**

**规则:**

* **短期分支可以直接push**

* **短期分支合并到长期分支时需要提PR**

* **每个PR都需要经过审核[Code Reviewer],审核通过后才可以合并分支**

### 2.1 功能分支

**开发中的每个功能单独一个分支:**

```bash
feature/JIRA编号-功能简述
eg:
feature/AIT-10-clarifier-agent-build
feature/AIT-12-result-page-ui
```

### 2.2 缺陷修复分支

**用于修复已有的功能问题,修复bug**

```bash
bugfix/JIRA编号-问题简述
eg:
bugfix/AIT-30-card-render-bug
```

### 2.3 文档分支

**对文档进行补充,修改时的分支**

```bash
docs/JIRA编号-文档简述
eg:
docs/AIT-15-readme-update
```

## 3.工作流程概述

**以下是日常会需要的开发流程,建议按照这个流程来进行日常开发:**

### 3.1 任务创建-JIRA

**每个开发项需要先在JIRA上建ISSUE,如:**

* **AIT-12-ClarifierAgent基础实现**

* **AIT-18-结果页UI**

**通过JIRA会自动在绑定的仓库创建对应的分支,接下来要做的就是拉取分支来进行开发**

### 3.2 从develop分支拉取功能分支

**Git命令参考如下:**

```bash
git checkout develop
git pull origin develop
git checkout -b feature/AIT-10-clarifier-agent-build
```

**通过这些命令,可以将在本地创建基于develop分支的feature分支,然后要做的就是在本地进行开发编码**

### 3.3 开发并提交

**在本地开发完成后需要进行提交,此过程会用到的Git命令大致如下:**

```bash
git add [开发代码的相对路径]
git commit -m "提交内容"
```

#### 3.3.1 commit内容推荐

**为了确保每次commit的内容对团队成员来说清晰明了,以下是建议的commit格式**

```bash
"feat: 新功能"
eg: git commit -m "feat: add clarifier agent basic workflow"
"fix: 修bug"
eg: git commit -m "fix: resolve trace logging null error"
"docs: 文档修改"
eg: git commit -m "docs: add project overview markdown file"
"refactor: 重构"
eg: git commit -m "refactor: simplify orchestrator state handling"
"test: 测试相关"
eg: git commit -m "test: add safety guard regression cases"
"chore: 配置,依赖更新等杂项"
eg: git commit -m "chore: add docker compose for local dev"
```

### 3.4 推送远程分支

**开发完成后,推送到远程对应分支上**

```bash
git push origin feature/AIT-10-clarifier-agent-build
```

### 3.5 发起PR到develop

**当该feature分支编写完,需要合并到develop分支时,提PR来进行合并**

```bash

```

**PR里简单描述做了什么,然后由对应的code reviewer审核后合并到develop分支**

### 3.6 Code Review

**每个提交到长期分支的PR都需要至少1一个人看过再合并**

### 3.7 合并到develop 分支

**通过PR并合并分支**

### 3.8 Sprint结束后整理出release

**这点如果一个Sprint结束后版本合适且稳定,则拉出release分支**

```bash
git checkout develop
git pull origin develop
git checkout -b release/sprint-1-demo
```

## 4. 重要规则强调

* **禁止直接push到长期分支**

* **一个分支专注于一件事,不要在一个分支上做多件事,如:**
  
  * **Agent改动**
  
  * **UI改动**
  
  * **数据库改动**

* **绑定JIRA后,一个JIRA ISSUE对应一个分支**

* **PR不要太大,多提PR,尽量隔一两天部分code完成后就提PR**

* **对于测试,后期PR需要写明该PR已经通过什么测试,如:**
  
  * **Postman测试**
  
  * **UI测试**
  
  * **Promptfoo测试**

* **任何影响接口或者数据结构的改动,同步到开发文档,接口文档等**
