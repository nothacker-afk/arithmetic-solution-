.PHONY: help install test test-v cov run cli ai demo clean lint fmt ci

help:
	@echo "Arithmetic Super App — common tasks"
	@echo ""
	@echo "  make install     Install with dev + web extras"
	@echo "  make test        Run test suite"
	@echo "  make test-v      Run tests verbosely"
	@echo "  make cov         Run tests with coverage report"
	@echo "  make run         Start the Flask + WebSocket server"
	@echo "  make cli         Run the interactive CLI"
	@echo "  make ai          Run the AI natural-language CLI"
	@echo "  make demo        Run the AI batch demo"
	@echo "  make ci          Run CI equivalent locally"
	@echo "  make clean       Remove caches and build artifacts"

install:
	pip install -e ".[dev,web]"

test:
	pytest -q

test-v:
	pytest -v

cov:
	pytest --cov --cov-report=term-missing

run:
	python -m web.backend.main

cli:
	python -m cli.main

ai:
	python -m ai_engine.cli

demo:
	python -m ai_engine.demo

ci:
	python -m pip install --upgrade pip
	pip install -e ".[dev,web]"
	pytest -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
	rm -rf build dist .coverage coverage.xml 2>/dev/null || true
	@echo "Cleaned."
