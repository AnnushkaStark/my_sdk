.PHONY: ruff  docs-install docs-serve docs-build docs-deploy

ruff:
	uv run ruff format
	uv run ruff check --fix



docs-install:
	uv add --dev mkdocs mkdocs-material "mkdocstrings[python]"

docs-serve:
	uv run mkdocs serve -a 127.0.0.1:8001

docs-build:
	uv run mkdocs build --clean --strict

docs-deploy:
	uv run mkdocs gh-deploy --force
