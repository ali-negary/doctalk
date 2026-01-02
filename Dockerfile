# ==================================
# Stage 1: Builder
# ==================================
FROM python:3.11.9-slim as builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=2.2.1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install "poetry==$POETRY_VERSION"

WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main

# ==================================
# Stage 2: Runtime
# ==================================
FROM python:3.11.9-slim as runtime

# 1. Create user FIRST (so we can use it for COPY)
RUN addgroup --system appgroup && \
    adduser --system --group --home /app appuser

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app \
    HOME=/app

WORKDIR /app

# 2. COPY with ownership change built-in (INSTANT vs. Slow chown)
COPY --chown=appuser:appgroup --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}
COPY --chown=appuser:appgroup src/ src/

# Healthcheck tools
USER root
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Switch to user
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.api.chat:app", "--host", "0.0.0.0", "--port", "8000"]
