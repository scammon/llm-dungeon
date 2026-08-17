# ---- Stage 1: build the React/TS frontend ----
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python backend that serves the built SPA ----
FROM python:3.12-slim
WORKDIR /app

# Backend deps
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Root game modules (single source of truth, imported as top-level)
COPY combat.py config.py data.py gen.py player.py meta.py ./

# Backend package
COPY backend/ ./backend/

# Built frontend (served by backend.main)
COPY --from=frontend /build/dist ./frontend/dist/

# Listen on the platform-assigned host/port (Dailey injects HOST + PORT).
# Falls back to 0.0.0.0:8000 for local runs.
EXPOSE 8000
CMD uvicorn backend.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}
