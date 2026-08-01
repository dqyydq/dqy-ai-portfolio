# Day 4 学习记录：Redis Agent Memory

## Day Checklist

## Completion evidence (2026-08-01)

- Redis Memory is integrated into the LLM history path with cache-hit, PostgreSQL preheat, and Redis-error fallback behavior.
- FastAPI lifespan owns the Redis client; routes receive it through dependency injection and services do not import a global client.
- Real Redis List integration test verifies order, a 12-message window, and the 24-hour TTL.
- Redis degradation test injects an unavailable client and verifies PostgreSQL history, LLM generation, and message persistence still succeed.
- Verification: `python -m pytest -q` -> `30 passed`.

- [x] Redis List 与短期记忆边界
- [x] Memory Key、消息格式、窗口长度与 TTL
- [ ] Memory Service 与 LLM 上下文接入
- [ ] Redis 与降级路径测试
- [ ] 面试复盘与学习记录

## Task Log

### Task 4.1: Redis List 与短期记忆边界

- Status: completed
- Scope: 明确 Redis List 在当前对话 Agent 中保存什么、为什么不替代 PostgreSQL 消息历史，以及 Memory 的最小读写契约。
- Out of scope: LLM Cache、限流、队列、分布式锁、长期向量记忆。
- Acceptance criteria: 能说明 PostgreSQL 与 Redis 各自的数据职责，并为后续 Key 与消息结构确定约束。
- Evidence: 明确 PostgreSQL 保存完整、可审计的消息事实；Redis 保存当前 Conversation 的可重建短期上下文。Redis 故障时回退 PostgreSQL，不阻断消息主链路。
- Next task: 设计 Memory Key、消息格式、窗口长度与 TTL。

### Task 4.2: Memory 数据契约

- Status: completed
- Scope: 为当前 Conversation 设计 Redis Key、List 元素 JSON、消息窗口与 TTL，并定义读取缓存未命中时的回退行为。
- Out of scope: 用户长期偏好、摘要记忆、向量检索、LLM Cache。
- Acceptance criteria: 每个字段和参数均有明确用途，且不会混淆不同 Conversation 的上下文。
- Evidence: 实现 `build_memory_key()`、`append_memory_message()` 与 `get_memory_messages()`。真实 Redis 集成测试执行 13 次 `RPUSH`，验证 `LTRIM` 后仅保留 message-2 至 message-13，并验证 TTL 位于 1 至 86400 秒。命令：`python -m pytest -q tests/test_memory_service.py`，结果：`1 passed in 0.53s`。
- Next task: 实现 Memory Service。

### Task 4.3: Redis Memory 回退与预热设计

- Status: completed
- Scope: 在消息已提交至 PostgreSQL 后，优先读取 Redis；Redis 未命中时查询最近 PostgreSQL 消息并预热 Redis；Redis 不可用时回退 PostgreSQL。
- Out of scope: 会话摘要、Token 精确预算、流式输出、后台异步预热。
- Acceptance criteria: 缓存命中不读取完整消息历史；缓存未命中不遗漏刚写入的用户消息；Redis 错误不阻断聊天主链路。
- Evidence: 已发现顺序风险：对空 Redis 先写当前消息再读取，会遗漏 PostgreSQL 中的历史上下文。
- Next task: 实现 `get_llm_history_with_memory()`。

## Problem Log

### Problem 4.1: 学习进度文档与 CLAUDE.md 不一致

- Observed at: 2026-08-01
-
- Related problem (2026-08-01): full pytest raised `RuntimeError: Event loop is closed` in a later service test after the real Redis integration test. The global async Redis client retained a socket created by a prior pytest event loop. This is a resource-lifecycle bug, not a Redis outage; do not hide it by broadening `except RedisError`. The test now calls `close_redis()` during cleanup so the next loop gets a fresh connection. FastAPI already performs the equivalent cleanup in lifespan shutdown.
- Symptom: `docs/progress.md` 记录 Day 3 已完成、下一步 Day 4；根目录 `CLAUDE.md` 仍写当前进入 Day 2。
- Reproduction or command: 读取两个文件即可复现。
- Root cause: 后续 Day 的进度没有同步回 `CLAUDE.md`。
- Impact: 自动化学习流程可能错误地把 Day 2 当作当前任务。
- Resolution or next action: 本次以用户明确开始 Day 4、`docs/progress.md` 与实际已完成的 Day 3 代码为准；Day 4 收尾时同步更新路线状态。
- Knowledge point: 项目运行状态与文档状态都属于工程事实；文档漂移会导致错误决策。
