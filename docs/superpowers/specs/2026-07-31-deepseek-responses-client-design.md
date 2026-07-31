# DeepSeek Responses 客户端设计

## 目标

为 Day 3 的对话功能提供一个可测试的异步 LLM 调用边界。当前只支持一次文本生成；不发起真实 API 请求作为测试的一部分。

## 架构

```text
Conversation Service
    -> LLMClient.generate(history)
    -> AsyncOpenAI.responses.create(...)
    -> str
```

`LLMClient` 是唯一依赖 OpenAI SDK 的业务模块。调用方只传入按 `user` / `assistant` 角色规范化的历史消息，并只获得最终文本。

## 配置

`Settings` 声明以下环境变量：

- `DEEPSEEK_API_KEY`：密钥；只由客户端读取，禁止日志输出。
- `DEEPSEEK_BASE_URL`：默认 `https://api.deepseek.com/v1`。
- `DEEPSEEK_MODEL`：默认 `deepseek-v4-flash`。
- `LLM_TIMEOUT_SECONDS`：默认 `30`。

## 错误边界

- 未配置密钥：启动或首次调用时给出明确的服务端配置错误，绝不回显密钥。
- 上游网络、超时或响应格式错误：转换为应用层 LLM 调用失败异常；本任务不决定 HTTP 状态码映射。
- 空输出：视为调用失败，不保存空 assistant 消息。

## 测试

单元测试注入 fake / mock SDK client，并断言：

1. 调用使用了配置中的模型和超时。
2. 历史消息以 Responses 输入格式传入。
3. 从 `response.output_text` 返回文本。
4. 不访问真实网络，也不读取或打印密钥。

## 非目标

- 不在本任务接入 FastAPI 路由或数据库写入。
- 不实现流式响应、工具调用、重试、Redis Memory 或多 Provider。

## 后续优化目标

在基础调用与对话链路验证完成后，按项目 Day 的范围逐步评估：

1. 流式 Responses 事件到 SSE，改善长回答的首字延迟。
2. 明确的超时、可重试错误分类与指数退避；不对非幂等外部副作用盲目重试。
3. 调用耗时、模型、token 用量和失败类型的结构化观测，日志中不记录密钥或完整敏感内容。
4. 工具调用与结构化输出；届时再扩展 `LLMClient` 返回值，而不是让路由解析 SDK 原始对象。
5. 多 Provider 或模型降级策略；由当前客户端边界隔离供应商差异。
