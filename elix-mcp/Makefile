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

start-elix-mcp: stop-elix-mcp
	docker build -t elix-mcp . && \
	docker run -it -p 9090:9090 --name elix-mcp --env-file .env -v ./notebooks/data:/app/videos -v ./.pixeltable:/root/.pixeltable -v ./.records:/app/.records -v ~/.cache/huggingface:/root/.cache/huggingface elix-mcp

inspect-elix-mcp:
	curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash && \
	. ~/.nvm/nvm.sh && \
	nvm install node; \
	npx @modelcontextprotocol/inspector

stop-elix-mcp:
	docker stop elix-mcp || true && \
	docker rm elix-mcp || true && \
	rm -rf .pixeltable && \
	rm -rf .records

# --- FFmpeg ---

fix-video:
	ffmpeg -i $(input) -c:v libx264 -c:a copy $(output)
