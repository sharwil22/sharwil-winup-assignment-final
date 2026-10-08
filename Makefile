.PHONY: install dev backend frontend test test-backend test-frontend lint eval

install:
	cd backend && uv sync
	cd backend && [ -f .env ] || cp .env.example .env
	cd frontend && npm install

# Runs backend (:8000) and frontend (:5173) together; Ctrl+C stops both.
dev:
	@trap 'kill 0' INT TERM EXIT; \
	(cd backend && uv run uvicorn app.main:app --reload --port 8000) & \
	(cd frontend && npm run dev) & \
	wait

backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test: test-backend test-frontend

test-backend:
	cd backend && uv run pytest -q

test-frontend:
	cd frontend && npm test -- --run

lint:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app tests scripts
	cd frontend && npm run lint && npm run typecheck

eval:
	@if [ -f backend/scripts/eval.py ]; then cd backend && uv run python -m scripts.eval; \
	else echo "Live eval not implemented yet (Phase 7, step 7.1)."; fi
