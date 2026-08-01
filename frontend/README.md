# Agent Workspace Frontend

React + TypeScript + Vite frontend for the AI Agent Platform. It connects to the existing FastAPI endpoints for registration, login, conversations, messages, and the DeepSeek-backed reply flow.

## Run locally

Start PostgreSQL and Redis from the project root:

```powershell
docker compose up -d
```

Start the FastAPI backend from the project root:

```powershell
.venv\Scripts\activate
$env:PYTHONPATH = "backend"
uvicorn app.main:app --reload --port 8000
```

In a second terminal, start the frontend:

```powershell
cd frontend
npm run dev
```

Open `http://127.0.0.1:5173`. Vite proxies `/auth`, `/conversations`, and `/health` to `http://127.0.0.1:8000`, so no development CORS configuration is required.

## Verify

```powershell
npm run lint
npm run build
```
