# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:0.5.7-python3.12-bookworm-slim AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev || \
    uv sync --no-install-project --no-dev

COPY backend/ ./backend/
COPY backend/prompts/ ./backend/prompts/
COPY evals/ ./evals/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev || uv sync --no-dev


FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/backend

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl libpq5 ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/backend /app/backend
COPY --from=builder /app/evals /app/evals

RUN useradd --system --uid 1001 --create-home --shell /usr/sbin/nologin docsrag && \
    chown -R docsrag:docsrag /app
USER docsrag

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "docs_rag.main:app", "--host", "0.0.0.0", "--port", "8000"]
