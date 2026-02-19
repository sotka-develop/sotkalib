default:
    just --list

sync:
    uv sync --all-extras --dev --refresh

publish INDEX="pypi":
    uv publish --index="{{ INDEX }}" --trusted-publishing=always

build:
    uv build -o dist/ --no-sources

lint PATH=".":
    uv run ruff check --fix-only "{{ PATH }}"
    uv run ruff format "{{ PATH }}"

typecheck PATH="src":
    uv run pyrefly check "{{ PATH }}"

push-commit MSG: sync lint (typecheck 'src') (test '-q' 'no')
    git add .
    git commit -m "{{ MSG }}"
    git push

bump SEMVER:
    uv version "{{ SEMVER }}"

release-git SEMVER:
    git pull
    git add .
    git commit -m "release: {{ SEMVER }}"
    git push

tag-push SEMVER:
    git tag -a "{{ SEMVER }}" -m "release: {{ SEMVER }}"
    git push origin "{{ SEMVER }}"

release SEMVER: sync lint (typecheck 'src') (test '-q' 'no') (bump SEMVER) (release-git SEMVER) (tag-push SEMVER)

# let it be down here, it breaks syntax highlighting in Zed :D

[arg('q', long='quiet', short='q', value='-q')]
[arg('tb', long='tb')]
test q='' tb='short' DIR="tests/" *FLAGS:
    uv run pytest {{ FLAGS }} "{{ DIR }}" {{ q }} --tb={{ tb }}
