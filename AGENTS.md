# Repository Guidelines

## Project Structure & Module Organization
Root `pyproject.toml` pins Python 3.11 and installs `xian-contracting` editable. Runtime code lives in `xian-contracting/src/contracting`, organised into `compilation`, `execution`, `storage`, `stdlib`, and `contracts`; extend existing subpackages instead of adding top-level modules. Tests sit in `xian-contracting/tests` with `unit`, `integration`, `security`, and `performance`; keep fixtures with the suite they exercise.

## Build, Test, and Development Commands
- `cd xian-contracting && poetry install` — sync Poetry environment and expose `contracting` in editable mode.
- `poetry run pytest tests/unit` — execute the fast regression suite; run this before pushing incremental changes.
- `poetry run pytest tests/integration -k <pattern>` — run slower suites when touching execution or storage code.
- `poetry run autopep8 --in-place --recursive src/contracting` — align formatting before review.

## Coding Style & Naming Conventions
Code follows PEP 8 via `autopep8` and `pycodestyle`; use four-space indentation, one statement per line, and docstrings on public APIs. Modules and functions stay `snake_case`, classes `PascalCase`, and exported constants `UPPER_SNAKE_CASE`. Add type hints to new paths and mirror signatures in `client.py` and executor modules.

## Testing Guidelines
Pytest is the unified runner; name files `test_*.py` and test functions `test_<subject>_<expectation>` so discovery works without extra configuration. Unit tests should stub storage through in-memory drivers, while integration tests may import real contracts from `contracts/`. Use `poetry run pytest --maxfail=1 --disable-warnings -q` for smoke checks and avoid cross-importing helpers between suites.

## Commit & Pull Request Guidelines
Recent history mixes concise imperatives (`deepcopy fix`) with scoped Conventional Commits (`fix(contracting): ...`); follow the latter for clarity, e.g. `feat(storage): add merkle proof builder`. Reference issue IDs in the body, list behavioural changes succinctly, and mention required migrations or scripts. Pull requests should describe impacted modules, call out new commands, attach logs when behaviour diverges from the README, and include the pytest command you ran.

## Release & Security Notes
The automated release flow uses `xian-contracting/release.sh`, which enforces a clean `master` branch, runs `poetry run pytest`, and generates release notes. When altering signing or execution logic, document new capabilities in `README.md` and flag breaking changes early so the release checks are not bypassed. Never commit private keys or API secrets; configuration artifacts belong in `.env.example` files tracked outside this repository.
