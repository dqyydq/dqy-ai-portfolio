# Day 2 学习记录：用户注册、登录与 JWT

## Task Log

### Task 2.1: 注册 API 契约与数据模型

- Status: completed
- Scope: 注册请求/响应字段、密码边界、公开用户字段
- Out of scope: 数据库表、JWT 签发、登录接口
- Acceptance criteria: 请求模型接收 email/user_name/password；响应模型只暴露 id/email/user_name/created_at；密码长度被校验
- Evidence: `RegisterRequest(email='a@example.com', password='12345678')` 已成功实例化；项目按用户要求统一使用 `user_name`。
- Next task: 用户表与注册持久化

### Task 2.2: User 数据表设计

- Status: completed
- Scope: users 表的字段、唯一性与空值约束
- Out of scope: 注册路由、JWT 签发、登录接口
- Acceptance criteria: 能解释每个字段的用途，并给出 email 和 user_name 的唯一性边界
- Evidence: 确认 email 和 user_name 为唯一非空；password_hash 非空但不唯一；conversation 在 Day 3 通过 `conversations.user_id -> users.id` 外键关联。
- Next task: SQLAlchemy User ORM 模型

### Task 2.3: User ORM 模型

- Status: completed
- Scope: SQLAlchemy 2.0 的 users 表映射
- Out of scope: 实际建表、注册路由、JWT
- Acceptance criteria: UUID 主键；email/user_name 唯一索引；无明文密码字段；带时区的创建时间
- Evidence: ORM 元数据包含 `id,email,user_name,password_hash,created_at`；`ix_users_email` 和 `ix_users_user_name` 均为 unique=True。
- Next task: 在 PostgreSQL 中初始化 users 表

### Task 2.4: PostgreSQL users 表初始化

- Status: completed
- Scope: 注册 User 元数据，并在 FastAPI 启动时创建 users 表
- Out of scope: Alembic 迁移、注册路由、JWT
- Acceptance criteria: `init_db()` 能执行 create_all，且在应用接受请求前执行
- Evidence: `database.py` 已定义 `init_db()`，使用 `engine.begin()` 和 `connection.run_sync(Base.metadata.create_all)`；FastAPI TestClient 生命周期返回 `/health` 正常；PostgreSQL 实测 `\dt users` 列出 public.users。
- Next task: 密码哈希工具

### Task 2.5: 密码哈希工具

- Status: completed
- Scope: Argon2 密码哈希与校验
- Out of scope: Token 签发、登录、密码找回
- Acceptance criteria: 不保存明文；正确密码可校验；错误密码被拒绝
- Evidence: `uv run pytest -q tests/test_security.py` 结果为 `1 passed in 0.25s`。
- Next task: 创建用户并持久化到 PostgreSQL

### Task 2.6: 创建用户并持久化

- Status: completed
- Scope: 注册数据转换为 User ORM 对象并写入 PostgreSQL
- Out of scope: HTTP 路由、重复用户错误映射、JWT
- Acceptance criteria: 密码只存储哈希；提交后返回含 id 的用户；集成测试清理临时数据
- Evidence: `uv run pytest -q tests/test_auth_service.py` 结果为 `1 passed in 0.68s`；测试实测写入和清理了 PostgreSQL 临时用户。
- Next task: ORM User 到安全响应模型的转换

### Task 2.7: ORM User 安全响应转换

- Status: completed
- Scope: 仅公开 User 的安全字段
- Out of scope: 注册 HTTP 路由、重复用户错误处理
- Acceptance criteria: User ORM 对象可转换为 UserResponse；password_hash 不会被返回
- Evidence: `uv run pytest -q tests/test_auth_schemas.py` 结果为 `1 passed in 0.35s`。
- Next task: POST /auth/register 路由

### Task 2.8: POST /auth/register 路由

- Status: completed
- Scope: 注册请求、异步 Session 注入、创建用户和安全响应
- Out of scope: 重复注册异常映射、JWT
- Acceptance criteria: HTTP 201；返回公开用户字段；密码字段不会泄露
- Evidence: `uv run pytest -q tests/test_auth_api.py` 的注册用例通过，实测 201 和无密码字段。
- Next task: 重复注册返回 HTTP 409

### Problem 2.1: 重复注册未映射为 HTTP 409

- Observed at: Task 2.9 测试前
- Symptom: 第二次提交相同注册请求返回 HTTP 500，而不是 409。
- Reproduction or command: `uv run pytest -q tests/test_auth_api.py::test_duplicate_registration_returns_conflict`
- Root cause: PostgreSQL 唯一索引触发 SQLAlchemy `IntegrityError`，路由未捕获且未回滚 Session。
- Impact: 客户端无法区分服务器错误与用户名/邮箱冲突；失败 Session 不应继续使用。
- Resolution or next action: 已捕获 `IntegrityError`，执行 rollback，并映射 HTTP 409；注册 API 测试结果为 `2 passed`。
- Knowledge point: 应用层预查询有并发竞争；数据库唯一约束是最终防线。

### Task 2.9: 重复注册返回 HTTP 409

- Status: completed
- Scope: 唯一索引冲突的 HTTP 语义和失败 Session 清理
- Out of scope: 登录、JWT、Token 黑名单
- Acceptance criteria: 重复注册返回 409；Session 回滚；测试不跨关闭事件循环复用连接池
- Evidence: 先观察到 HTTP 500；捕获 `IntegrityError` 并 rollback 后，`uv run pytest -q tests/test_auth_api.py` 结果为 `2 passed in 0.85s`。
- Next task: 登录 API 契约与 JWT

### Task 2.10: 登录 API 契约

- Status: completed
- Scope: 登录输入、Token 成功响应、统一认证失败语义
- Out of scope: JWT 签名和解析、当前用户依赖
- Acceptance criteria: LoginRequest 校验 email/password；TokenResponse 返回 bearer Token；邮箱不存在与密码错误同为 401
- Evidence: 已定义 LoginRequest(email,password) 和 TokenResponse(access_token, token_type='bearer')。
- Next task: JWT 配置与签发

### Task 2.11: JWT 配置与签发

- Status: completed
- Scope: HS256 签名、sub/exp claims、环境变量密钥
- Out of scope: Token 解析、刷新 Token、Token 黑名单
- Acceptance criteria: Token 含 sub/exp；正确密钥可验证；错误密钥不可验证；密钥长度至少 32 字节
- Evidence: 本地 JWT_SECRET_KEY 长度为 43；`uv run pytest -q tests/test_jwt_security.py` 结果为 `1 passed in 0.15s`，无密钥长度警告。
- Next task: 登录凭证校验

### Task 2.12: 登录凭证校验

- Status: completed
- Scope: 按 email 查询用户并校验 Argon2 哈希
- Out of scope: 登录 HTTP 路由、JWT 解析
- Acceptance criteria: 正确凭证返回 User；错误密码和未知邮箱均返回 None
- Evidence: `uv run pytest -q tests/test_auth_service.py` 结果为 `2 passed in 0.66s`。
- Next task: POST /auth/login 路由

### Task 2.13: POST /auth/login 路由

- Status: completed
- Scope: 凭证登录、JWT 签发、统一 401
- Out of scope: 当前用户解析、Token 刷新/注销
- Acceptance criteria: 正确凭证返回 bearer Token；Token sub 为用户 id；未知邮箱和错误密码同为 401
- Evidence: `uv run pytest -q tests/test_auth_api.py` 结果为 `4 passed in 1.10s`。
- Next task: 从 Bearer JWT 获取当前用户

### Task 2.14: 当前用户 JWT 依赖

- Status: completed
- Scope: Bearer Token 提取、JWT 验签/过期检查、sub 到 User 的查询
- Out of scope: 角色授权、Token 刷新和注销
- Acceptance criteria: 无效/过期/伪造 Token 与不存在用户均为 401；有效 Token 返回对应 User
- Evidence: `deps.py` 已用 HTTPBearer 提取 Token、PyJWT 验签、UUID(sub) 查询 User，并统一返回 401。
- Next task: GET /auth/me 受保护接口

### Task 2.15: GET /auth/me 受保护接口

- Status: completed
- Scope: 用 get_current_user 保护当前用户查询接口
- Out of scope: 角色权限、Token 刷新/注销
- Acceptance criteria: 有效 Bearer Token 返回当前用户；缺失或伪造 Token 返回 401；不泄露 password_hash
- Evidence: `uv run pytest -q tests/test_auth_api.py` 结果为 `6 passed in 1.22s`；有效、缺失、伪造 Token 路径均已验证。
- Next task: Day 2 全量回归验证

## Day 2 Completion

- 完成内容：注册、Argon2 密码哈希、PostgreSQL User 持久化、重复注册 409、登录、JWT 签发、Bearer JWT 当前用户依赖和 `/auth/me`。
- Full verification: `uv run pytest -q`，结果为 `13 passed, 1 warning in 1.62s`。
- Known limitation: TestClient 对当前 httpx 的弃用警告不影响功能，后续依赖升级时处理。
- Next Day: Day 3 Conversation、Message 与 LLM 调用。

### Problem 2.2: 测试跨事件循环复用 asyncpg 连接

- Observed at: 重复注册测试首次复跑
- Symptom: `RuntimeError: Event loop is closed`，以及 asyncpg 写入错误。
- Reproduction or command: `uv run pytest -q tests/test_auth_api.py`
- Root cause: 测试清理通过新的 `asyncio.run()` 使用全局 AsyncEngine，却没有 dispose 连接池；后续 TestClient 使用新的事件循环复用旧连接。
- Impact: 测试无法稳定验证 API 错误路径。
- Resolution or next action: 测试清理 finally 中调用 `close_database()`；全量注册 API 测试通过。
- Knowledge point: AsyncEngine/asyncpg 连接池不应跨已关闭的 event loop 复用。

### Problem 2.3: Docker daemon 未运行导致认证测试无法连接 PostgreSQL

- Observed at: Task 2.15 鉴权 API 测试
- Symptom: 全部 API 测试在应用启动阶段报 `ConnectionRefusedError`，目标为 localhost:55432。
- Reproduction or command: `uv run pytest -q tests/test_auth_api.py`；随后 `docker ps` 无法连接 dockerDesktopLinuxEngine。
- Root cause: Docker Desktop daemon 未运行，PostgreSQL/Redis 容器不可用。
- Impact: 需要真实 PostgreSQL 的注册、登录和当前用户集成测试无法运行。
- Resolution or next action: 用户启动 Docker Desktop；随后运行 `docker compose up -d` 并重跑测试。
- Knowledge point: 应用健康依赖和集成测试依赖外部基础设施可用；代码错误与运行环境错误必须分开诊断。

## Problem Log
