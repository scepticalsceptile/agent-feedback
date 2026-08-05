# Project Boilerplate Plan

## Goal

Set up a standard modern PyPI library repository around the clean-room
`agent-feedback` package before writing implementation code.

The repo should be easy to build, test, lint, and publish, while keeping
runtime dependencies at zero.

Development commands should prefer `uv` over direct `pip` usage.

## Chosen defaults

- PyPI project name: `agent-feedback`
- import package name: `agent_feedback`
- Python support floor: `>=3.10`
- source layout: `src/`
- tests layout: `tests/`
- runtime dependencies: none
- build backend: `hatchling`
- dev tooling: `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy`,
  `build`, `twine`

## Proposed repo tree

```text
README.md
LICENSE
pyproject.toml
Makefile
.gitignore
src/
    agent_feedback/
        __init__.py
        py.typed
tests/
    conftest.py
    fakes.py
    test_public_api.py
    test_request_model.py
    test_callback_shapes.py
    test_loop_outcomes.py
    test_failures.py
    test_history_and_results.py
    test_helpers.py
design/
    ...
```

## `pyproject.toml` plan

Use one `pyproject.toml` as the single source of truth for:

- build system
- project metadata
- optional dev dependencies
- `pytest` config if needed
- `ruff` config
- `mypy` config

### Build-system section

Use `hatchling` for a small, modern build setup.

### Project metadata section

Include at least:

- name
- version
- description
- readme
- license
- authors
- requires-python
- classifiers
- urls

### Dependency policy

- `[project.dependencies]` should remain empty for v1 runtime.
- `[project.optional-dependencies].dev` should contain testing and release
  tooling only.

## Makefile plan

Keep the Makefile very small and boring.

Suggested targets:

- `install-dev`
- `test`
- `test-cov`
- `lint`
- `typecheck`
- `build`
- `check-dist`
- `clean`

Each target should call the standard Python tooling directly rather than adding
custom project logic.

Use `uv sync --extra dev` for environment setup and `uv run ...` for tool
execution.

## Packaging conventions

- Keep package code under `src/agent_feedback/`.
- Re-export only the stable public API from `src/agent_feedback/__init__.py`.
- Ship `py.typed` so the package is typed for downstream users.
- Keep helper implementation modules private unless they are intentionally part
  of the public surface.

## What not to add yet

- no runtime dependency manager lockfile requirement
- no pre-commit setup unless it proves necessary later
- no tox or nox unless the test matrix grows enough to justify it
- no docs site generator yet
- no release automation workflow yet

## Boilerplate acceptance criteria

- `uv build` succeeds locally.
- `pytest` can import the package through the `src/` layout.
- `ruff check` and `mypy` can be run through the Makefile.
- wheel and sdist both include `py.typed`.
- runtime dependency list remains empty.

## Suggested implementation order

1. create `pyproject.toml`
2. create `.gitignore`
3. create `Makefile`
4. create `src/agent_feedback/__init__.py` and `py.typed`
5. create empty `tests/` structure and shared fakes module
