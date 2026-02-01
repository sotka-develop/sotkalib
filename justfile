sync:
	uv sync --locked --all-extras --dev

publish INDEX="pypi":
	uv publish --index={{INDEX}} --trusted-publishing=always

build:
	uv build -o dist/ --no-sources

lint:
	uv run ruff check --fix-only .
	uv run ruff format .
