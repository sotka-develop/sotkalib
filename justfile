sync:
	uv sync --locked --all-extras --dev

publish-test:
	uv publish --index=testpypi --trusted-publishing=always

publish:
	uv publish --index=pypi --trusted-publishing=always

build:
	uv build -o dist/ --no-sources

lint:
	uv run ruff check --fix-only .
	uv run ruff format .