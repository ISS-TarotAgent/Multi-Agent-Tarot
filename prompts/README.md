# Prompts
**这里存放Prompt模板和版本化管理内容**
## 通用模板
**下面是通用模板,可以根据Agent的需要进行调整,一般来说,Prompt需要包含以下几点内容**
* Role: 解释Agent的角色-你是谁,你在系统中的唯一职责是什么
* Objective: 解释Agent的任务-这一步必须完成什么任务
* Input: 解释Agent将要收到的输入-你将会收到哪些字段
* Boundaries: 解释Agent的边界-你不能做什么,哪些内容必须留给其他Agent
* Reasoning Rules: 解释Agent需要遵循的处理规则-你应该如何处理输入,如何组织分析
* Sataty Rules: 解释Agent需要遵循的安全约束-你必须遵循哪些安全约束
* Output Format: 定义Agent的输出格式-必须输出成什么JSON字段
* Failure Handling: 定义Agent的失败处理机制-如果信息不足,冲突,含糊,应该怎么返回
* Notes: 补充说明