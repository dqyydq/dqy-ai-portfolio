# AI Agent Platform - Redis Learning Project

> 一个用于学习 Redis + PostgreSQL + JWT + AI Agent 后端工程实践的项目。

目标：

通过构建一个真实 AI Agent SaaS 后端系统，在业务场景中学习：

- Redis 缓存设计
- Redis Agent Memory
- Redis 消息队列
- Redis 限流
- Redis 状态管理
- PostgreSQL 数据建模
- JWT 用户认证
- LLM Agent 架构设计


---

# 1. 项目简介


本项目实现一个类似 ChatGPT Workspace 的 AI 助手平台。


核心能力：

- 用户注册登录
- JWT 身份认证
- AI 对话
- Conversation 管理
- Agent Memory
- LLM 调用
- Redis 缓存
- 异步任务
- RAG 知识库（后续）


整体架构：

```
                Client

                  |

                  |

              FastAPI


                  |

        ---------------------

        |                   |

   PostgreSQL            Redis

  持久化数据          高速状态数据


        |

        |

      Agent


        |

        |

   OpenAI Compatible API


        |

        |

     DeepSeek LLM

```


---

# 2. 技术栈


## Backend

- Python 3.12+
- FastAPI
- SQLAlchemy 2.0
- Alembic
- Pydantic v2


## Database

PostgreSQL

用途：

- 用户数据
- 会话数据
- 消息历史
- 业务数据


Redis

用途：

- Agent Memory
- Cache
- Session状态
- Rate Limit
- Task Queue


## AI

LLM：

OpenAI SDK Compatible API


当前：

DeepSeek API


## Environment

Python环境：

uv


基础服务：

Docker Compose



---

# 3. 项目目录结构


```
ai-agent-platform/

├── backend/
│
│   ├── app/
│   │
│   │   ├── main.py
│   │
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── chat.py
│   │   │
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │
│   │   ├── db/
│   │   │   ├── database.py
│   │   │
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── conversation.py
│   │   │
│   │   ├── schemas/
│   │   │
│   │   ├── services/
│   │   │
│   │   ├── agent/
│   │       ├── llm.py
│   │       ├── memory.py
│   │
│   ├── pyproject.toml
│
│
├── docker-compose.yml
│
├── .env
│
└── README.md

```


---

# 4. 环境管理


使用 uv。


安装：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```


创建项目：


```bash
uv init
```


创建虚拟环境：


```bash
uv venv
```


安装依赖：


```bash
uv add fastapi uvicorn
uv add sqlalchemy alembic
uv add psycopg2-binary
uv add redis
uv add python-jose
uv add passlib
uv add openai
```


运行：

```bash
uv run uvicorn app.main:app --reload
```


---

# 5. Docker 服务


## docker-compose.yml


```yaml
services:


  postgres:

    image: postgres:16

    container_name: ai-postgres

    restart: always

    environment:

      POSTGRES_USER: postgres

      POSTGRES_PASSWORD: postgres

      POSTGRES_DB: ai_agent

    ports:

      - "5432:5432"

    volumes:

      - postgres_data:/var/lib/postgresql/data



  redis:

    image: redis:7

    container_name: ai-redis

    restart: always

    ports:

      - "6379:6379"

    volumes:

      - redis_data:/data



volumes:

  postgres_data:

  redis_data:

```


启动：

```bash
docker compose up -d
```


查看：

```bash
docker ps
```


---

# 6. 环境变量


.env


```env

DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_agent


REDIS_URL=redis://localhost:6379/0


JWT_SECRET_KEY=change_me


DEEPSEEK_API_KEY=your_api_key


```


---

# 7. LLM 调用设计


采用 OpenAI SDK 格式。


原因：

- 兼容 OpenAI
- 可以切换模型
- 方便接入 DeepSeek / GPT / Claude


安装：

```bash
uv add openai
```


代码：


```python
import os

from openai import OpenAI



client = OpenAI(

    api_key=os.environ.get(
        "DEEPSEEK_API_KEY"
    ),

    base_url="https://api.deepseek.com"

)



response = client.chat.completions.create(

    model="deepseek-v4-flash",

    messages=[

        {
            "role":"system",
            "content":"You are a helpful assistant"
        },

        {
            "role":"user",
            "content":"Hello"
        }

    ],

    stream=False,

    reasoning_effort="high",

    extra_body={

        "thinking": {

            "type":"enabled"

        }

    }

)



print(
    response.choices[0].message.content
)

```


后续封装：

```
agent/
|
├── llm.py

```


统一接口：

```python
class LLMClient:

    def chat(messages):
        pass

```


未来可以替换：

```
DeepSeek

OpenAI

Local Model

```


---

# 8. 数据库设计


## User


users


字段：

```
id

email

username

password_hash

created_at

```



## Conversation


conversation


字段：

```
id

user_id

title

created_at

```



## Message


messages


字段：

```
id

conversation_id

role

content

created_at

```



PostgreSQL负责：

长期保存。


---

# 9. Redis设计


Redis不是替代数据库。


原则：

PostgreSQL：

```
可靠数据

长期保存

```


Redis：

```
高速数据

临时状态

计算数据

```



---

# Redis Module 1

## Agent Memory


保存最近聊天记录。


Key:


```
memory:user:{user_id}

```


结构：

List


例如：

```
[
 user message,

 assistant message

]

```


用途：

Agent上下文。


---

# Redis Module 2

## LLM Cache


Key:


```
llm_cache:{hash}

```


保存：

```
问题

答案

```


减少：

- token消耗
- API调用


---

# Redis Module 3

## Token Blacklist


JWT退出登录。


Key:


```
blacklist:{token}

```


TTL:

token剩余时间。



---

# Redis Module 4

## Agent Task Queue


长任务：

例如：

- PDF解析
- 文档总结
- 数据分析


流程：


```
FastAPI

   |

Redis Queue

   |

Worker

   |

Agent

```



---

# Redis Module 5

## API Rate Limit


限制：

用户请求次数。


例如：

一分钟：

10次。


Redis:

```
rate:user:{id}

```


使用：

```
INCR

EXPIRE

```


---

# 10. 开发计划


## Day 1

基础环境：

完成：

- FastAPI
- Docker Compose
- PostgreSQL连接
- Redis连接


---

## Day 2

用户系统：

完成：

- 注册
- 登录
- JWT


---

## Day 3

Chat系统：

完成：

- Conversation
- Message
- LLM调用


---

## Day 4

Redis Memory：

完成：

- Redis List
- Agent上下文


---

## Day 5

Redis Cache：

完成：

- LLM缓存
- Token优化


---

## Day 6

工程能力：

完成：

- Rate Limit
- Task Queue


---

## Day 7

完善：

- Docker部署
- 日志
- 项目总结



---

# 最终目标


完成后具备：

✅ FastAPI AI Backend能力

✅ PostgreSQL建模能力

✅ Redis工程应用能力

✅ JWT认证能力

✅ Agent系统设计能力


项目亮点：

> 基于 FastAPI + PostgreSQL + Redis + OpenAI Compatible API 构建 AI Agent 平台，实现 JWT认证、Agent Memory、LLM缓存、任务队列和接口限流。