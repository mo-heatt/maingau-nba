# MAINGAU NBA — single container serving API + compiled frontend.
# Build context is the repository root:
#   docker build -t maingau-nba:local .
# The image mirrors the repository layout under /opt/app
# (backend/app, frontend/dist) so the app's ROOT-relative paths
# (data/, frontend/dist) resolve unchanged. The mock dataset is NOT
# baked in: mount /opt/app/data read-only with maingau_nba_mockdata.xlsx
# and event_stream_2026-10-01.jsonl, and give the container a writable
# directory for NBA_DB_PATH (see deploy/docker-compose.yml).

# ---------- frontend build ----------
FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- backend runtime ----------
FROM python:3.12-slim
WORKDIR /opt/app
ENV PYTHONPATH=/opt/app/backend \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend/app ./backend/app
COPY --from=frontend /build/dist ./frontend/dist

# data/ (mock workbook + event stream) must be mounted read-only at /opt/app/data.
# NBA_DB_PATH must point into a writable volume, e.g. /opt/app/db/nba.sqlite.
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/api/health', timeout=4)" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
