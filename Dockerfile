FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ src/
COPY migrations/ migrations/
COPY alembic.ini .
RUN useradd -u 10001 -m app && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["uvicorn", "live150.main:app", "--host", "0.0.0.0", "--port", "8000"]
