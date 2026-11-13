.PHONY: install backend frontend dev check

install:
	cd backend && uv sync
	cd frontend && npm install

backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

# Both servers in one terminal; Ctrl+C stops both.
dev:
	$(MAKE) -j2 backend frontend

check:
	cd backend && uv run pytest && uv run ruff check . && uv run mypy app tests
	cd frontend && npm test && npm run lint && npm run build
