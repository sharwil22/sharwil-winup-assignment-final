FROM node:22-alpine AS frontend-build

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir uv
COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN uv sync --project /app/backend --frozen --no-dev --no-install-project
COPY backend/app ./backend/app
COPY --from=frontend-build /build/frontend/dist ./frontend/dist

ENV PATH="/app/backend/.venv/bin:$PATH"
ENV PYTHONPATH="/app/backend"
WORKDIR /app/backend

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]