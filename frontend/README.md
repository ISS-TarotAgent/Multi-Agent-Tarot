# Frontend

本目录实现项目 README 中定义的前端模块，覆盖以下页面与流程：

- 问题输入页
- 澄清页
- 抽牌展示页
- 结果页
- 历史记录页

当前实现使用 `React + TypeScript + Vite`，并通过本地 mock service 串起完整演示流程，后续可以平滑替换为真实的 FastAPI 接口。

## 启动方式

```bash
npm install
npm run dev
```

## 构建

```bash
npm run build
```

## 对接说明

- 将 `src/services/mockApi.ts` 替换为真实 API 调用
- 保留 `src/types.ts` 作为前后端联调时的数据契约参考
- 如果后端补充会话和历史接口，当前页面流程可以直接复用
