set positional-arguments := true

default:
  just --list

sync:
	uv sync --all-extras --dev --refresh

publish INDEX="pypi":
	uv publish --index="{{INDEX}}" --trusted-publishing=always

build:
	uv build -o dist/ --no-sources

lint PATH=".":
	uv run ruff check --fix-only "{{PATH}}"
	uv run ruff format "{{PATH}}"

[arg('q', short='q', long='quiet', value='-q')]
[arg('tb', long='tb')]
test q='' tb='short' DIR="tests/" *FLAGS:
	uv run pytest {{FLAGS}} "{{DIR}}" {{q}} --tb={{tb}}

bump SEMVER:
	uv version "{{SEMVER}}"

release-git SEMVER:
	git add .
	git commit -m "release: {{SEMVER}}"
	git tag -a "{{SEMVER}}" -m "release: {{SEMVER}}"
	git push --tags

release SEMVER: sync lint (test '-q' 'no') (bump SEMVER) (release-git SEMVER)
