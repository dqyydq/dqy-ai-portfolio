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

- Status: in progress
- Scope: 两张表、外键、MessageRole 枚举
- Out of scope: 建表接入、API 路由、LLM 调用
- Acceptance criteria: ORM 元数据包含 conversations/messages；role 受枚举约束
- Evidence:
- Next task: 导入模型并创建 PostgreSQL 表

## Problem Log

