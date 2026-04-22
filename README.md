# Maya — Personal Health Assistant

Chat-based personal health assistant. FastAPI + Google ADK agent on the backend, React + Vite chat UI on the frontend, Postgres (pgvector) for storage, and an APScheduler worker for reminders.

## Layout

- `server/` — Python backend (FastAPI, ADK agent, tools, migrations)
- `web/` — React frontend (Vite + Tailwind)
- `docker-compose.yml` — base stack; `docker-compose.local.yml` — local overrides

## Local setup

### 1. Prereqs

- Docker + Docker Compose
- Python 3.11+ and [`bun`](https://bun.sh) if running services natively
- `gcloud auth application-default login` (Vertex AI uses ADC)

### 2. Env

Create `server/.env`:

```
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=live150-dev
GOOGLE_CLOUD_LOCATION=global
LIVE150_API_BASE=https://lifecloud.eng.sandbox.healthhustler.io
LIVE150_DEV_TOKEN=<dev-token>
```

## Run

### Option A — Docker (full stack)

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d
```

- Web: http://localhost:3000
- API: http://localhost:8000
- Postgres: localhost:5432

### Option B — Native dev

Backend:

```bash
cd server
python -m venv .venv && .venv/bin/pip install -r requirements.txt
PYTHONPATH=src .venv/bin/uvicorn live150.main:app --reload --port 8000
```

Frontend:

```bash
cd web && bun install && bun dev
```

## Test

```bash
cd server && PYTHONPATH=src .venv/bin/pytest tests/unit -q
```
