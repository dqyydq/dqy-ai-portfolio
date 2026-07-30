# AgentLab 后端知识与场景题总复习

> 这份文档汇总 Day 1–19 已学习内容，并用小林 Coding 的“基础 -> 原理 -> 高频题 -> 实战”结构对照 PostgreSQL、FastAPI 和 Agent 工程。数据库实验以 PostgreSQL 为准，不把 MySQL 语法直接搬进项目。

## 1. 当前结论

- 已完成学习范围：Day 1–19；Day 20 正在进入“同一 Conversation 只能有一个活跃 Run”的并发约束。
- 已形成的主线：FastAPI 请求 -> Schema 校验 -> Service 事务 -> Repository 查询 -> SQLAlchemy ORM/Core -> PostgreSQL 持久化 -> Worker/Provider/Tool 状态机。
- 已有较强证据的部分：事务边界、MVCC 快照、`FOR UPDATE SKIP LOCKED`、Worker 重试/恢复、ToolCall 幂等、审批门禁、Provider Adapter、B-Tree 执行计划、Alembic 升降级。
- 仍需补齐的部分：数据库执行器/存储内部、WAL 与恢复、角色权限、备份复制、全文检索、HTTP 认证授权、可观测性，以及整个 Redis 阶段。

## 2. 分层与请求链路

### 已掌握

| 层 | 职责 | AgentLab 落点 |
| --- | --- | --- |
| Router | 接收 HTTP、调用应用服务、映射状态码 | `app/api/runs.py`、Agent/Conversation API |
| Schema | 定义请求体/响应体，做边界校验 | `app/schemas/` 的 `RunCreate`、`RunResponse` |
| Service | 业务规则、事务边界、状态流转 | Run 完成、ToolRequest 持久化、审批决策 |
| Repository | 封装查询、锁定、批量读写；默认不 `commit` | Run/ToolCall/上下文查询 |
| ORM Model | 表、列、关系、约束和索引的 Python 描述 | `app/models.py` |
| PostgreSQL | 真正的数据约束、MVCC、锁、执行计划和持久化 | `agent_runs`、`tool_calls` 等表 |

### 必须能口述

一次 `POST /conversations/{id}/runs` 不应把 SQL 和事务细节堆在 Router。Router 只负责 HTTP 边界；Service 决定“一个请求是否允许创建 Run”并拥有事务；Repository 负责可复用的查询和锁；数据库约束负责在并发下兜底。这样测试可以分别替换 Fake Provider、验证 Service 状态机，并避免 HTTP 层直接承担并发正确性。

### 基础八股

- 同步函数会占住当前线程；异步函数在等待数据库/HTTP I/O 时把控制权交回事件循环。
- `AsyncSession` 不是并发安全对象；一个并发 Task 使用一个独立 Session。
- `engine` 管理连接池，`connect`/`AsyncSession` 使用池中的连接；请求结束应归还资源。
- FastAPI `lifespan` 适合创建和关闭 Engine、Provider client 等进程级资源。
- Docker image 是静态模板，container 是运行实例，Compose 负责多容器编排；PostgreSQL 是项目依赖服务，不是 FastAPI 自己实现的数据库。

## 3. SQL、关系模型与 PostgreSQL 基础

### 已掌握的知识

- 参数化 SQL 防止把用户输入当成 SQL 语法；Psycopg/SQLAlchemy 会把参数作为值绑定。
- `INSERT ... RETURNING` 在一次写入后直接取得数据库生成的 id、默认值。
- 主键保证实体身份；`UNIQUE` 防重复；`NOT NULL` 保证必填；外键保证父记录存在。
- 外键约束解决数据正确性，不自动解决性能；高频父子查询仍需针对子表外键列建索引。
- `ON DELETE CASCADE`、`SET NULL`、`RESTRICT` 是不同的生命周期语义，不能只看 ORM cascade。
- `INNER JOIN` 只保留两边都匹配的行；`LEFT JOIN` 保留左表，即使右表没有匹配。
- CTE 先定义可读的中间结果；窗口函数在保留明细行的同时计算排名、计数等聚合。
- `COUNT(*)` 不是“免费操作”，大表上仍需要扫描可见行；分页优先考虑稳定排序和 keyset pagination。
- Core 适合 Worker 热路径和不需要完整 ORM 对象的查询；ORM 适合领域对象和关系操作。

### Agent 场景题

1. 查询“至少有一条 Conversation 的 Agent”应使用 `INNER JOIN`；如果要求所有 Agent，即使没有 Conversation，也要用 `LEFT JOIN` 并在条件中谨慎放置过滤器。
2. 创建 Agent 后立即创建默认 Conversation，为什么需要 `flush()`？因为同一事务中要先获得 Agent 的数据库 id；`flush` 执行 SQL 但仍可回滚，`commit` 才让事务对外提交。
3. 删除 Conversation 时是否级联删除 Message/Run，要由产品生命周期决定；不能因为数据库支持 cascade 就默认开启。
4. 为什么查询上下文要 `ORDER BY created_at, id`？时间相同需要 id 作为稳定 tie-breaker，否则模型上下文顺序可能不稳定。

### 代码/实验证据

- Day 2：Psycopg 参数绑定、JOIN、外键和 `RETURNING`。
- Day 3：SQLAlchemy Core、CTE、窗口函数、失败事务集成测试。
- Day 4：ORM 关系、Identity Map、N+1、lazy loading、Session 生命周期。
- `app/repositories/context.py`：Conversation Message 的稳定顺序查询。

## 4. ORM、Session 与事务

### 关键机制

- `flush()` 把当前 Session 的 INSERT/UPDATE/DELETE 发给数据库，但事务仍可回滚，其他事务通常不可见。
- `commit()` 提交事务；提交后 SQLAlchemy 默认可能让对象属性过期，需要 `refresh()` 或重新查询。
- `refresh(obj)` 是显式从数据库取最终值，适合数据库默认值、触发器和提交后响应序列化。
- Identity Map 让同一 Session 对同一主键复用同一个 Python 对象；因此第二次 `get()` 不等于重新读取数据库。
- Session 关闭后，未预加载的 lazy relationship 不能再偷偷查库；API 返回前应明确加载需要的数据。
- Service 拥有事务，Repository 不应自行提交，否则一个业务用例无法整体回滚。
- 外部模型/工具网络 I/O 不应放在持有数据库行锁的长事务中；应拆成“短事务领取 -> 事务外执行 -> 短事务保存结果”。

### 场景题

- 模型响应包含多个 ToolRequest：同一事务创建 RunStep、pending ToolCall，并把 Run 改为 `waiting_tools`；任何一步失败都回滚，避免留下半完成计划。
- Worker 完成模型输出：Message、最终 RunStep 和 Run completed 必须在一个事务中写入，否则可能出现 Run 已完成但结果缺失。
- 两个 Task 共用一个 AsyncSession 会造成 flush/identity map/事务状态互相污染；必须按 Task 隔离 Session。

### 容易遗漏的基础边界

- `Depends` 配合 `yield` 的依赖函数会在请求结束时执行清理逻辑，适合交给 FastAPI 管理 Session；它和进程级 `lifespan` 不是同一层级。
- Psycopg cursor/connection 应使用上下文管理器，确保异常时 rollback、连接归还和 cursor 关闭。
- PostgreSQL 事务一旦出现 SQL 异常，当前事务会进入 failed 状态；必须 `rollback()` 后才能继续使用这个 Session。
- SQLAlchemy `default` 是 Python/ORM 侧默认值，`server_default` 是数据库侧默认值；需要数据库独立保证时，应在 migration 中声明 `server_default`。
- `flush` 失败和 `commit` 失败都要回滚；不能捕获异常后继续在同一个 failed transaction 中执行下一条 SQL。

### 代码/测试证据

- `app/services/runs.py::complete_run_with_output()`：Service 事务边界。
- `persist_model_tool_requests(...)`：ToolRequest 原子持久化和重放幂等。
- `tests/concurrency/test_worker_claim.py::test_session_get_uses_identity_map_until_refresh`：验证 Identity Map 到 `refresh()` 前的旧值行为。
- Day 19 并发测试结果：`20 passed`。

### 数据库幂等与错误映射

- `INSERT ... ON CONFLICT DO NOTHING RETURNING` 可以让并发 Worker 中只有一个请求创建本地 ToolCall；没有返回行时要查询并校验请求内容，而不是盲目当成成功。
- 数据库唯一约束保证的是本地记录唯一，不等于外部邮件、支付或 HTTP 请求只发生一次。
- 外键、唯一约束、CHECK 约束是数据库最终防线；API 应把可预期的 `IntegrityError` 映射为明确的 404/409/422，而不是返回 500。

## 5. Alembic 与数据库演进

### 已掌握

- `create_all()` 不能替代生产迁移；迁移文件记录版本、可审查、可回滚和发布顺序。
- 新增 `NOT NULL` 列不能直接在已有大表上上线：先加 nullable/default，回填并验证，再切换为 `NOT NULL`。
- `downgrade` 可能丢数据，生产回滚应先确认兼容性和备份；更可靠的是 expand -> backfill -> contract。
- autogenerate 不能可靠判断列重命名，必须人工审查 migration diff。
- 多个 Alembic head 表示迁移分叉，需要 merge revision，而不是随意删除历史。

### 证据

- Day 5 完成基础迁移链、upgrade/downgrade。
- Day 18 新增 `idx_messages_conversation_created_id`，并实际执行 downgrade -> upgrade。
- 当前 migration：`migrations/versions/e8a048cc11a0_add_message_context_index.py`。

## 6. MVCC、隔离级别与锁

### 已掌握

- PostgreSQL UPDATE 通常生成新 tuple 版本，旧版本成为 dead tuple；VACUUM 负责回收可回收版本，长事务会阻碍回收。
- Read Committed 通常按语句获取快照；同一事务的第二条 SELECT 可能看到别的事务已提交的更新。
- Repeatable Read 使用事务级快照；同一事务后续 SELECT 仍可能看到第一次读取的旧版本，并在写冲突时失败。
- Serializable 在 PostgreSQL 使用 SSI 检测危险依赖，失败时可能抛 serialization failure，需要有限重试。
- `SELECT ... FOR UPDATE` 锁住具体行直到 commit/rollback；`SKIP LOCKED` 跳过已锁行，适合多个 Worker 领取队列。
- 普通 `FOR UPDATE` 会等待，适合同一 Run 的顺序分配、终态写入和父 Run 聚合；队列领取才使用 `SKIP LOCKED`。
- 死锁来自不同事务以不同顺序持有多把锁；固定锁顺序、短事务和有限重试是主要治理手段。
- 只做“先 SELECT queued，再单独 UPDATE running”会发生重复领取；应在同一事务中锁定并更新，或使用条件 UPDATE 检查影响行数。

### Agent 场景题

1. 两个 Worker 同时领取 Run：`FOR UPDATE SKIP LOCKED` 让一个 Worker 获得行锁，另一个跳过它，不会重复执行。
2. 两个 Tool Worker 分别完成 A/B：只锁各自 ToolCall 不够；完成后都必须锁父 Run，再聚合本轮是否全部完成，避免两个 Worker 重复恢复父 Run。
3. Worker 取消时不能立即把 Run 写成 failed；`CancelledError` 是控制流，外部模型调用结果不确定，应保留 running 并交给 stale recovery。
4. Recovery 与原 Worker 同时写 ToolCall 终态：双方锁同一 ToolCall、验证当前状态和合法转换，先成功者生效，后者拒绝覆盖。

### 证据

- Day 6–7 双会话 MVCC、死锁、VACUUM 实验。
- Day 17：Read Committed/Repeatable Read 对 `AgentRun.status` 的真实双会话实验；并集成为 PostgreSQL 测试。
- `tests/concurrency/test_worker_claim.py`：Worker 领取、隔离级别和 Identity Map。

## 7. 索引、执行计划与维护

### 已掌握

- B-Tree 适合等值、范围和有序扫描；联合索引要根据过滤列、排序列和选择性安排列顺序。
- 部分索引只收录满足谓词的行，适合 `status = 'queued'` 这类高频小集合。
- 表达式索引把 `input_data->>'response_id'` 的计算结果索引化，查询必须使用等价表达式才能命中。
- JSONB 不是“自动快”；高频字段应抽成列、建立表达式索引或使用合适的 GIN。
- `EXPLAIN (ANALYZE, BUFFERS)` 要看实际行数、计划行数、Scan 类型、Sort、shared hit/read 和执行时间。
- Bitmap Heap Scan 可能先用索引找到页，再批量回表；即使索引提供了顺序，Bitmap 也可能需要额外 Sort。
- 小表或低选择性查询使用 Seq Scan 可能更快，不能见索引就强制使用。
- 索引增加写放大、存储和维护成本；应由真实执行计划证明，而不是盲目建全表索引。

### 证据

- Day 8：queued Run 部分索引对比全表扫描。
- Day 18：10k `agent_runs` 队列计划，以及 Message 上下文索引前后对比。
- 迁移后 Message 查询观察到 `Bitmap Index Scan -> Bitmap Heap Scan -> Sort`，强制 Index Scan 仅用于解释，不作为生产配置。

## 8. Agent 可靠性主线

### Run 状态机

```text
queued -> running -> completed
                  -> failed
                  -> waiting_tools -> queued / failed
                  -> waiting_approval -> queued / failed
```

- Worker 领取时增加 `retry_count`，表示已开始的执行尝试。
- 长模型调用期间 heartbeat 持续更新；恢复器按 heartbeat 超时判断 stale，而不是只看 started_at。
- 正常异常按 retryable/non-retryable 分类；协议错误、非法参数通常不盲目重试。
- Provider SDK 自动重试关闭，由 AgentRun 统一控制重试预算，避免“SDK 重试 + Worker 重试”放大调用次数。
- ToolCall 先持久化为 pending，再受控领取；外部副作用工具需要审批、幂等键或对账。
- `response_id + tool_call_id` 用于 Provider 响应重放幂等；本地唯一约束不能保证邮件、支付等外部副作用 exactly-once。
- 敏感 ToolCall 使用独立 Approval 记录，拒绝后不能简单把父 Run requeue，否则可能形成无限重新规划循环。
- Provider Adapter/Registry 隔离厂商 SDK；未知 Provider 或缺少密钥必须 fail-closed，密钥只来自环境变量或本地 `.env`。
- 优雅关闭停止领取新任务，给当前任务有限宽限期；超时取消后保留不确定状态交给 recovery。

### 已完成的可靠性场景题

- 为什么 ToolCall 不能直接执行：进程崩溃、并发重复和审批状态都无法审计。
- 为什么父 Run 要作为聚合锁：多个 ToolCall Worker 必须在同一父行上做“全部完成”的唯一判断。
- 为什么取消不等于失败：取消是控制流，失败是业务结果，恢复路径不同。
- 为什么不能把 API key 写入数据库/日志：泄漏面和审计风险不可接受。
- 为什么非法工具参数不自动重试：同一错误输入通常不会因为重试变合法，应让模型重新规划或失败。

### 主要代码/测试证据

- `app/workers/runner.py`：Run 生命周期、heartbeat、取消和失败分类。
- `app/services/tools.py`、`app/agents/tools/runner.py`：ToolCall 领取、执行、结果持久化。
- `app/services/approvals.py`：审批状态和父 Run 聚合。
- `app/agents/openai_compatible.py`：Provider Adapter 和错误映射。
- Day 13–16：ToolRequest、恢复、审批、Provider 可靠性；Day 16 全量测试 `216 passed`。

### 工具安全与执行边界

- ToolRegistry 遇到未注册工具或 Agent 未授权工具必须 fail-closed，不能“找不到就放行”。
- Tool 参数即使是合法 JSON，也必须经过 Pydantic/JSON Schema 的类型、范围和字段校验；非法参数通常不应无限重试。
- Calculator 不能直接对模型字符串调用 Python `eval()`；表达式解析必须限制语法、函数和资源消耗，避免代码注入。
- ToolCall 的 `tool_call_id`、Provider `response_id` 和参数摘要用于恢复 Provider 消息上下文；缺少原始 id 时，模型可能无法关联 ToolResult。
- 审批记录应保留 decision、decided_by、decided_at 等审计信息；这些字段不能由客户端任意伪造。
- `asyncio.TaskGroup`/Supervisor 中，一个 Worker 未处理的系统异常通常应取消兄弟任务并让进程失败退出；单个 Run 的预期业务异常则由 Worker 自己分类和持久化。
- 可变 Runner 不能跨 Worker 共享；共享连接池和不可变 Provider 配置可以共享，但当前 Run、上下文、取消标记等状态必须归属于单个执行者。

## 9. 小林 Coding 对照表

小林 Coding 原路线主要是 MySQL/InnoDB 与 Redis 高频题。本项目把同一问题换成 PostgreSQL 机制，并绑定 Agent 场景：

| 小林 Coding 主题 | 本项目对应内容 | 当前状态 |
| --- | --- | --- |
| SQL、JOIN、分页、COUNT | Agent/Conversation/Message/Run 查询、稳定排序、COUNT 成本 | 已掌握，需补 keyset 实测 |
| B+Tree、联合索引、索引失效 | PostgreSQL B-Tree、部分/表达式索引、`EXPLAIN` | 已掌握基础，覆盖索引与统计信息待补 |
| MVCC、快照、幻读 | PostgreSQL tuple、Read Committed、Repeatable Read、Serializable SSI | 已掌握核心；Serializable 实验待补齐 |
| 行锁、死锁 | `FOR UPDATE`、`SKIP LOCKED`、Tool/Run 聚合锁 | 已掌握并有并发测试 |
| redo/undo、Buffer Pool | PostgreSQL WAL、Shared Buffers、checkpoint、VACUUM | 未完整实战 |
| 数据库设计与约束 | 外键、唯一约束、级联删除、状态机不变量 | 已掌握；Day 20 partial unique index 待实现 |
| Alembic/DDL 发布 | migration、回滚、expand/backfill/contract | 已掌握基础，线上无锁迁移待补 |
| Redis 数据结构 | 计划用于 Agent memory、限流、事件镜像 | 未开始 |
| Redis 缓存 | cache-aside、TTL、穿透/击穿/雪崩 | 未开始 |
| Redis 分布式锁 | `SET NX PX`、token、Lua 释放 | 未开始 |
| Redis Stream | PEL、ack、pending recovery、幂等消费 | 未开始 |
| RDB/AOF/主从/哨兵/集群 | Redis 运维和恢复实验 | 未开始 |

## 10. 当前缺口与优先级

### P0：下一阶段必须补齐

1. **Day 20 并发不变量**：为 `conversation_id + active status` 建 PostgreSQL partial unique index，捕获 `IntegrityError` 映射 409，并写两个独立 Session 的并发测试。
2. **执行器基础**：Parser、Planner、Executor、Heap/Index Scan、Nested Loop/Hash/Merge Join、统计信息和估算误差。
3. **事务高级题**：Serializable SSI、serialization failure 重试、写偏差和谓词锁边界。
4. **WAL/VACUUM/checkpoint**：观察 WAL、dead tuple、autovacuum、长事务阻塞和崩溃恢复含义。

### P1：PostgreSQL 生产能力

- 最小权限 role/GRANT、连接认证和应用账号隔离。
- `pg_dump`/`pg_restore`、备份恢复演练、复制槽、物理/逻辑复制。
- 分区表适用边界、冷热数据、归档和维护成本。
- `tsvector`、`tsquery`、GIN，构建 Agent 知识库搜索。
- HTTP 认证/授权、JWT、cookie/CSRF/CORS、幂等 HTTP API 和错误契约。
- 连接池容量、超时、N+1、慢查询、结构化日志、metrics、tracing/correlation ID。

### P2：Redis 必修实战

- Docker Redis + 独立测试库和客户端。
- String/Hash/List/Set/ZSet/Bitmap/HyperLogLog/GEO/Stream 的场景选择。
- Agent 配置 cache-aside、TTL、失效、空值缓存、随机 TTL、热点 key 和大 key。
- Pub/Sub 失效通知与丢消息边界；再用 outbox/retry 讨论可靠通知。
- Redis 锁安全释放、续租、过期和与 PostgreSQL 行锁的职责边界。
- Streams Consumer Group、PEL、ACK、pending recovery 和幂等消费。
- RDB/AOF、复制、Sentinel/Cluster；明确演示拓扑不等于生产 SLA。

## 11. 推荐的面试复习方式

每个主题都按下面六句组织，避免只背定义：

```text
结论：我选择什么机制。
机制：PostgreSQL/FastAPI/Redis 为什么这样工作。
AgentLab 场景：哪一个 Run、ToolCall、Approval 或 Worker 会遇到它。
代码/SQL：指出函数、索引、事务或测试证据。
边界：这个方案不能解决什么，成本是什么。
替代方案：什么时候用条件 UPDATE、乐观锁、Serializable、Redis 或 outbox。
```

当前最值得重新口述的五道题：

1. 为什么“先 SELECT 再 INSERT”不能防止同一 Conversation 重复 Run？
2. 为什么 `FOR UPDATE SKIP LOCKED` 必须和状态更新处于同一短事务？
3. 为什么 flush 后失败仍然能整体回滚，而 commit 后不能？
4. 为什么 ToolCall 的数据库幂等不能证明邮件只发送一次？
5. 为什么 PostgreSQL partial unique index 比应用层 active Run 预检查可靠？

## 12. 复习状态判定

- **已掌握并有证据**：FastAPI 分层、Psycopg 参数化 SQL、JOIN/约束、Core/ORM、Session/事务、Alembic 基础、MVCC 快照、行锁与队列领取、Worker 生命周期、ToolCall 状态机、审批、Provider 适配、B-Tree/部分索引/执行计划基础。
- **理解但需要再做实验**：Serializable SSI、执行器和统计信息、WAL/checkpoint、VACUUM 深入、权限、备份恢复、复制、分区、HTTP 安全和可观测性。
- **尚未学习**：Redis 全部阶段，以及 PostgreSQL 知识库全文检索和 WebSocket 持久化事件。

这份总结不能替代每日证据；每日 SQL 输出、测试结果和具体错误仍以 `docs/dayNN.md` 为准。

## 13. Day 1–19 覆盖审计

| Day | 核心内容 | 审计结论 |
| --- | --- | --- |
| 1 | Docker、psql、数据库/Schema/Table/Role、约束、`pg_isready`、lifespan | 已覆盖；健康检查和对象层级已显式补入 |
| 2 | Psycopg 参数化、RETURNING、JOIN、外键、级联、上下文管理器、连接故障排查 | 已覆盖；`Depends/yield` 和上下文管理器已补入 |
| 3 | Core、Engine/Connection、CTE、窗口函数、事务、失败测试 | 已覆盖 |
| 4 | ORM、关系、Identity Map、N+1、lazy loading、AsyncSession、flush/commit/refresh | 已覆盖 |
| 5 | Alembic、版本链、upgrade/downgrade、NOT NULL 发布、merge head | 已覆盖 |
| 6–7 | 双会话、隔离级别、丢失更新、死锁、MVCC、dead tuple、VACUUM、Run API | 已覆盖；WAL/checkpoint 仍待实战 |
| 8–9 | PostgreSQL 队列、`SKIP LOCKED`、Worker 领取、heartbeat、stale recovery、重试预算 | 已覆盖 |
| 10 | 优雅关闭、Supervisor、TaskGroup、Runner 所有权 | 已覆盖；已补入工具安全章节 |
| 11–12 | ToolCall 状态机、条件领取、Registry、Schema、计算器安全、Adapter、Provider 密钥 | 已覆盖；已补入工具安全章节 |
| 13–15 | ToolRequest 原子持久化、RunStep 顺序、重放幂等、上下文恢复、审批和审计 | 已覆盖；已补入数据库幂等和审批边界 |
| 16 | Provider/Tool 失败矩阵、统一重试、取消、HTTP 408、dotenv、真实 Provider 请求 | 已覆盖；认证授权 API 仍待后续 Day |
| 17–19 | 快照、条件 UPDATE、执行计划、B-Tree、部分索引、迁移可逆性、Identity Map | 已覆盖；Planner 深入和 Serializable 实验仍列为缺口 |

审计结论：已完成 Day 1–19 的核心主题没有发现完全遗漏；此前只存在于每日笔记中的基础资源边界、事务失败状态、工具安全、上下文重建和 Supervisor 所有权，已补入本总纲。仍未完成的内容保持在“当前缺口与优先级”中，没有把计划误记为已掌握。
