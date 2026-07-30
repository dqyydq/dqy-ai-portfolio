# 项目学习边界

本项目严格按照 `AI-Agent-Platform-Redis-Learning.md` 的 Day 计划推进。

## 学习规则

1. 当前 Day 的项目目标优先，未进入后续 Day 时不得把后续主题作为必修任务。
2. 每次只推进一个明确的小任务：先讲与当前任务直接相关的原理，再给练习或代码改动。
3. 面试题只围绕当前任务。通用八股、事务、并发、分布式等内容只有在当前功能直接涉及时才提问。
4. 如果需要补充前置知识，必须说明它与当前任务的直接关系，并控制在完成当前任务所需的最小范围内。
5. 用户已经掌握的 Day 内容先做摸底，不重复讲解；根据回答调整难度。

## Day 范围

- Day 1：FastAPI、Docker Compose、PostgreSQL 连接、Redis 连接。
- Day 2：用户注册、登录、密码哈希、JWT 身份认证。
- Day 3：Conversation、Message、LLM 调用。
- Day 4：Redis Agent Memory。
- Day 5：LLM Cache。
- Day 6：Rate Limit、Task Queue、Worker。
- Day 7：日志、部署、项目总结。

## 当前状态

Day 1 已完成，当前进入 Day 2。除非用户主动要求，不提前讲解后续 Day 的实现内容。

## Day 2 命名约定

- 用户名字段统一使用 `user_name`，用于 API 请求、响应、数据库模型和后续业务代码。
