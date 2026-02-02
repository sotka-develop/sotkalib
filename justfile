sync:
	uv sync --locked --all-extras --dev

publish INDEX="pypi":
	uv publish --index={{INDEX}} --trusted-publishing=always

build:
	uv build -o dist/ --no-sources

lint:
	uv run ruff check --fix-only .
	uv run ruff format .

test-lima:
	DOCKER_HOST=unix://${HOME}/.lima/default/sock/docker.sock \
	TESTCONTAINERS_RYUK_DISABLED=true \
	uv run pytest tests/ -v --tb=short 2>&1 | tail -60
