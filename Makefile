.PHONY: check test lint types validate install

install:
	pip install -r requirements.txt

# Full quality gate — run before commit / in CI.
check: lint types test validate

test:
	python -m pytest tests/

lint:
	ruff check engine tests

types:
	mypy

# Content gate: fails loudly on any dangling load-bearing reference.
validate:
	python -m engine.validate data
