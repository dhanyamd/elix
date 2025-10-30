CHECK_DIRS := .

# --- Ruff ---

format-fix:
	uv run ruff format $(CHECK_DIRS) 
	uv run ruff check --select I --fix

lint-fix:
	uv run ruff check --fix

format-check:
	uv run ruff format --check $(CHECK_DIRS) 
	uv run ruff check -e
	uv run ruff check --select I -e

lint-check:
	uv run ruff check $(CHECK_DIRS)

# --- MCP Server ---

start-elix-api: stop-elix-api
	docker build -t elix-api . && \
	docker run -d -p 8000:8080 --name elix-api --env-file .env elix-api

stop-elix-api:
	docker stop elix-api || true && \
	docker rm elix-api || true