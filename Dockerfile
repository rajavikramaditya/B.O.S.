# B.O.S. — single image: API + dashboard.

# ---------- 1. Build the dashboard ----------
FROM node:22-alpine AS dashboard
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- 2. Runtime ----------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    BOS_DATA_DIR=/data \
    BOS_FRONTEND_DIST=/app/frontend/dist \
    ENVIRONMENT=production

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend/ backend/
COPY --from=dashboard /build/dist frontend/dist

RUN groupadd -r bos && useradd -r -g bos -d /app bos \
    && mkdir -p /data && chown -R bos:bos /data
USER bos
VOLUME ["/data"]

WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"

# One worker: Autopilot's scheduler and the in-process rate limiter live in this process.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
