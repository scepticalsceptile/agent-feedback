.PHONY: install-dev test test-cov lint typecheck build check-dist clean

install-dev:
	uv sync --extra dev

test:
	uv run pytest

test-cov:
	uv run pytest --cov=agent_feedback --cov-report=term-missing

lint:
	uv run ruff check .

typecheck:
	uv run mypy src tests

build:
	uv build

check-dist: build
	uv run twine check dist/*

clean:
	python -c "from pathlib import Path; import shutil; targets = ['build', 'dist', '.mypy_cache', '.pytest_cache', '.ruff_cache']; [shutil.rmtree(target, ignore_errors=True) for target in targets if Path(target).exists()]; [shutil.rmtree(str(path), ignore_errors=True) for path in Path('.').glob('*.egg-info')]; [shutil.rmtree(str(path), ignore_errors=True) for path in Path('src').glob('*.egg-info')]"
