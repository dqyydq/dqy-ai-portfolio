# 对话生成与 assistant 持久化设计

## 目标

在已认证且归属当前用户的会话中，接收一条用户消息、请求 LLM 生成回复，并保存 assistant 消息。

## 调用流程

```text
POST /conversations/{conversation_id}/messages
    -> 当前用户与会话归属校验
    -> 事务 A：保存并提交 user Message
    -> 查询完整历史（包含刚提交的 user Message）
    -> LLMClient.generate(history)     # 不持有数据库事务等待网络
    -> 事务 B：保存并提交 assistant Message
    -> 返回 assistant Message
```

## 职责边界

- API 路由：认证、请求/响应契约，以及异常到 HTTP 状态码的映射。
- Conversation Service：归属校验、两次短数据库写入、历史构造和 LLM 调用编排。
- LLMClient：仅处理供应商 Responses API 调用与供应商异常转换。

## 失败语义

- 会话不存在或不属于当前用户：调用 LLM 前返回 404，不产生消息。
- LLM 调用失败或空输出：返回 502；已提交的 user Message 保留；不创建 assistant Message。
- assistant 持久化失败：返回服务端错误；本任务不做自动重试或幂等恢复。

## 数据与事务边界

- 事务 A 在 `create_user_message` 提交处结束，确保用户输入不会因网络请求失败而丢失。
- LLM 网络等待发生在事务外，避免长时间占用事务/连接。
- 事务 B 只保存已经生成的有效 assistant 文本。

## 测试

使用 fake LLMClient，不访问网络，验证：

1. 成功路径依次保存 user 和 assistant，assistant role 固定为 `assistant`。
2. LLM 获得的历史包含刚保存的 user 消息，且按时间升序。
3. LLM 失败时 user 消息保留，没有 assistant 消息。
4. 跨用户会话在 LLM 调用前即被拒绝。

## 非目标

- 流式 SSE、自动重试、幂等键、后台任务、工具调用、Redis Memory。
