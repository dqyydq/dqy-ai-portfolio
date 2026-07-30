# Day 1 学习记录：服务基础与连接生命周期

## Task Log

### Task 1.1: FastAPI lifespan 与连接池生命周期

- Status: completed
- Scope: 理解应用启动、请求处理、应用关闭与数据库/Redis连接池的关系
- Out of scope: 用户认证、聊天模型、Redis缓存策略
- Acceptance criteria: 能解释为什么连接池不能在每个请求中重复创建，并能指出当前项目的释放位置
- Evidence: 学员能说明连接池应按 worker 进程复用，并指出 lifespan 关闭阶段；补充了 AsyncSession 不可并发共享。
- Next task: SQLAlchemy flush/commit 与事务边界

### Diagnostic 1: Day 1 基础摸底

- Status: completed
- Evidence: 能识别每请求创建连接池的资源开销、全局连接池和 lifespan 释放位置；需要继续强化“每 worker 一个池”和 AsyncSession 并发边界。

### Scope Correction

- Day 1 原始范围只包含 FastAPI、Docker Compose、PostgreSQL 连接和 Redis 连接。
- `flush/commit` 与 service 事务边界属于后续数据库主题，本日不作为必修任务。

## Problem Log
