# Day 3 学习记录：Conversation、Message 与 LLM 调用

## Task Log

### Task 3.1: Conversation 与 Message 数据建模

- Status: completed
- Scope: User -> Conversation -> Message 的一对多关系、字段和 role 枚举边界
- Out of scope: API 路由、LLM 调用、Redis Memory
- Acceptance criteria: 明确外键、UUID 主键、UTC 时间和受限 role 值
- Evidence: 学员确定 `conversations.user_id -> users.id` 与 `messages.conversation_id -> conversations.id`；role 限定为 user/assistant。
- Next task: SQLAlchemy Conversation 与 Message ORM 模型

### Task 3.2: Conversation 与 Message ORM 模型

- Status: completed
- Scope: 两张表、外键、MessageRole 枚举
- Out of scope: 建表接入、API 路由、LLM 调用
- Acceptance criteria: ORM 元数据包含 conversations/messages；role 受枚举约束
- Evidence: ORM 元数据包含 conversations/messages；MessageRole 数据库枚举值验证为 `['user', 'assistant']`。
- Next task: 导入模型并创建 PostgreSQL 表

### Task 3.3: Conversation 与 Message PostgreSQL 建表

- Status: completed
- Scope: 启动时导入 Day 3 模型并创建 PostgreSQL 表/枚举
- Out of scope: 会话 API、Message API、LLM 调用
- Acceptance criteria: conversations/messages 表存在；message_role 保存 user/assistant
- Evidence: 应用生命周期启动成功；PostgreSQL `\dt conversations`、`\dt messages` 均存在；`enum_range(NULL::message_role)` 输出 user、assistant。
- Next task: POST /conversations API 契约

### Task 3.4: POST /conversations API 契约与 Schema

- Status: completed
- Scope: title 输入校验、会话安全响应、用户归属来自 JWT 依赖
- Out of scope: 会话持久化、Message API、LLM 调用
- Acceptance criteria: 客户端只提交 title；响应包含会话 UUID/归属/时间；user_id 不来自客户端
- Evidence: ConversationCreate 与 ConversationResponse 已创建，title 限制为 1-255，响应启用 from_attributes。
- Next task: 创建会话持久化服务

### Task 3.5: 创建会话持久化服务

- Status: completed
- Scope: 用 current_user.id 创建 Conversation 并提交数据库
- Out of scope: HTTP 路由、Message 创建、LLM 调用
- Acceptance criteria: 会话写入 PostgreSQL，title 与创建者 UUID 正确
- Evidence: `uv run pytest -q tests/test_conversation_service.py` 结果为 `1 passed in 0.46s`。
- Next task: POST /conversations 路由

### Task 3.6: POST /conversations 路由

- Status: completed
- Scope: 认证用户创建会话和安全归属
- Out of scope: 会话列表、Message API、LLM 调用
- Acceptance criteria: 有效 JWT 返回 201 且 user_id 为当前用户；无 Token 返回 401
- Evidence: `uv run pytest -q tests/test_conversation_api.py` 结果为 `2 passed in 0.81s`。
- Next task: GET /conversations 当前用户列表

### Task 3.7: 会话列表服务与路由

- Status: completed
- Scope: 只返回 current_user.id 的会话，按创建时间倒序
- Out of scope: 会话详情、Message API、LLM 调用
- Acceptance criteria: 用户 A 的列表不能出现用户 B 的会话；无 Token 返回 401
- Evidence: `uv run pytest -q tests/test_conversation_api.py` 结果为 `3 passed in 1.08s`，包含跨用户列表隔离测试。
- Next task: Message 发送 API 契约与会话归属校验

### Task 3.9: Message 输入、归属校验与持久化

- Status: completed
- Scope: Message Schema、会话归属校验、服务端固定 user role、发送消息路由
- Out of scope: 消息历史读取、LLM 调用、Redis Memory
- Acceptance criteria: 所有者可写消息；他人返回 404；客户端不能伪造 assistant role
- Evidence: `uv run pytest -q tests/test_conversation_api.py` 结果为 `4 passed in 1.35s`，覆盖归属隔离和 user role 固定。
- Next task: GET /conversations/{conversation_id}/messages 消息历史

### Task 3.13: Message 历史读取

- Status: completed
- Scope: 时间升序 Message 查询、会话归属校验和历史 API
- Out of scope: LLM 调用、Redis Memory
- Acceptance criteria: 所有者按历史顺序读取消息；其他用户得到 404
- Evidence: `uv run pytest -q tests/test_conversation_api.py` 结果为 `4 passed in 1.38s`，覆盖两条消息顺序与跨用户历史读取。
- Next task: OpenAI-compatible LLM 客户端设计

### Task 3.15: DeepSeek Responses LLM 客户端

- Status: completed
- Scope: 通过可配置的 DeepSeek Responses API 封装一次异步文本生成调用；密钥仅从环境读取；以 mock 测试验证调用契约。
- Out of scope: 把调用接入消息路由、流式响应、工具调用、Redis Memory 和真实 API 扣费测试。
- Acceptance criteria: 地址、模型和超时可配置；业务代码不直接访问环境变量；客户端可从 Responses 结果提取文本；单元测试不访问网络。
- Evidence: 待实现。
- Evidence: `Settings` 已加载 `https://api.deepseek.com/v1`、`deepseek-v4-flash`、`30.0`；`uv pip install "openai>=1.0,<2.0"` 安装 `openai==1.109.1`；`uv lock` 成功更新锁文件。`uv run pytest -q tests/test_llm_client.py` 输出 `3 passed in 0.46s`，mock 验证模型、输入、超时和文本返回值；验证空白 `output_text` 会抛出 `LLMResponseError`；验证 SDK `APIError` 被转换为 `LLMCallError` 且通过 `raise ... from exc` 保留原始异常链。一次真实 Responses API 调用已成功获得模型文本；本地 `print(answer)` 因 Windows GBK 无法编码回复中的 emoji 报 `UnicodeEncodeError`，不影响 API 调用本身。
- Next task: 将 LLM 客户端接入“创建用户消息 -> 生成 assistant 消息 -> 一并持久化”的对话用例。

### Task 3.16: 对话消息生成与 assistant 持久化

- Status: completed
- Scope: 在会话归属校验后持久化用户消息；构造历史并调用 `LLMClient`；成功时持久化 assistant 消息。
- Out of scope: 流式响应、自动重试、工具调用、Redis Memory、消息幂等键和后台任务。
- Acceptance criteria: 不在数据库事务中等待外部 LLM；LLM 成功时历史中包含刚提交的用户消息；LLM 失败时用户消息保留且不创建空 assistant 消息；所有权校验仍在调用前完成。
- Evidence: `uv run pytest -q tests/test_conversation_service.py` 输出 `7 passed in 1.32s`；纯函数 `build_llm_history` 将 user 映射为 `input_text`、assistant 映射为 `output_text`，并保持持久化消息顺序。fake LLM 集成测试验证：成功路径保存 user + assistant；LLM 失败时 user 消息仍被持久化且没有 assistant；跨用户请求在调用 LLM 前抛出 `ConversationNotFoundError`。API 测试使用 FastAPI dependency override 注入 fake LLM，验证 POST 成功返回 assistant 的 201、LLM 失败的 502 与跨用户 404。全量回归 `uv run pytest -q` 输出 `28 passed, 1 warning in 4.23s`。
- Next task: Day 3 收尾完成；等待开始 Day 4 Redis Agent Memory。

## Problem Log

### Problem 3.15.1: Windows 控制台无法输出模型 emoji

- Observed at: 真实 DeepSeek Responses API 最小调用验证。
- Symptom: `print(answer)` 报 `UnicodeEncodeError: 'gbk' codec can't encode character`。
- Reproduction or command: PowerShell 中以默认 GBK stdout 运行异步调用脚本，模型文本含 emoji。
- Root cause: Windows 控制台输出编码与模型返回 Unicode 字符不兼容；请求、响应解析和 `LLMClient.generate` 已先成功完成。
- Impact: 仅影响终端展示，不能据此判断 API 调用失败；本次调用已产生费用。
- Resolution or next action: 生产服务应使用 UTF-8 日志/响应；本学习任务不为展示目的重复发起付费调用。
- Knowledge point: 外部 API 成功、应用处理成功与终端输出成功是三个独立边界，应从 traceback 发生位置定位失败阶段。

## Problem Log
