# Live150 Agent Service

Monorepo: `server/` (Python FastAPI + Google ADK) and `web/` (React + Vite chat UI).

## Quick Start

```bash
# Backend
cd server && python -m venv .venv && .venv/bin/pip install -r requirements.txt
PYTHONPATH=src .venv/bin/uvicorn live150.main:app --reload --port 8000

# Frontend
cd web && bun install && bun dev
```

## Env — server/.env

```
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=live150-dev
GOOGLE_CLOUD_LOCATION=global
LIVE150_API_BASE=https://lifecloud.eng.sandbox.healthhustler.io
LIVE150_DEV_TOKEN=<dev-token>
```

## Auth flow (dev)

App sends `X-Phone-Number: +19084329987` header → service impersonates via Live150 API → gets access token → calls 5 user-scoped GETs.

Test users: Nigel (+19084329987), Murthy (+19083612019), Pragya (+12243347204)

## Streaming

`POST /api/chat` speaks the Vercel AI SDK data stream protocol. The React frontend uses `useChat` from `@ai-sdk/react`.

## Project Layout

- `server/src/live150/` — Python backend
- `server/src/live150/api/stream.py` — Vercel AI data stream endpoint
- `server/src/live150/tools/health_api.py` — 5 tools wired to real Live150 APIs
- `web/src/` — React frontend (Vite + Tailwind + shadcn patterns)
- `web/src/components/chat.tsx` — Main chat UI with useChat
- `docker-compose.yml` — at repo root, references `server/`

## Test

```bash
cd server && PYTHONPATH=src .venv/bin/pytest tests/unit -q
```
