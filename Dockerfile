# syntax=docker/dockerfile:1

FROM node:22.14-bookworm-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DIBBLE_DEPLOYMENT_MODE=household_container
ENV DIBBLE_DATABASE_PATH=/data/dibble.db
ENV DIBBLE_FRONTEND_DIST_PATH=/app/frontend/dist
ENV DIBBLE_TELEMETRY_LEVEL=normal

WORKDIR /app

RUN python -m pip install --no-cache-dir uv==0.8.14

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY scripts/container_healthcheck.py ./scripts/container_healthcheck.py
COPY scripts/ingest_curriculum.py ./scripts/ingest_curriculum.py
COPY data/curriculum ./data/curriculum
RUN uv sync --frozen --no-dev --no-cache

COPY --from=frontend-build /app/frontend/dist ./frontend/dist

RUN useradd --create-home --shell /usr/sbin/nologin dibble \
    && mkdir -p /data \
    && chown -R dibble:dibble /app /data

USER dibble

EXPOSE 8000
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD /app/.venv/bin/python scripts/container_healthcheck.py

CMD ["/app/.venv/bin/python", "-m", "uvicorn", "--app-dir", "src", "dibble.main:app", "--host", "0.0.0.0", "--port", "8000"]
