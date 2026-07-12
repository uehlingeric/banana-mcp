.PHONY: setup lint run clean

setup:
	uv sync

lint:
	uv run ruff check src/
	uv run ruff format --check src/

run:
	uv run banana-mcp

clean:
	rm -rf .venv __pycache__ src/banana_mcp/__pycache__
