# Development Guide

Welcome to SandboxERP! This guide covers everything you need to contribute to the project.

---

## Table of Contents

- [Requirements](#requirements)
- [Environment Setup](#environment-setup)
- [Running the Tests](#running-the-tests)
- [Writing Tests](#writing-tests)
- [Project Structure](#project-structure)
- [Adding a Country Pack](#adding-a-country-pack)
- [Adding an Industry Pack](#adding-an-industry-pack)
- [Branching and Commit Conventions](#branching-and-commit-conventions)
- [Submitting a Pull Request](#submitting-a-pull-request)

---

## Requirements

- Python 3.10 or higher
- Docker and Docker Compose v2
- Git

---

## Environment Setup

```bash
# Clone the repository
git clone https://github.com/getsandboxerp/sandboxerp.git
cd sandboxerp

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate       # Linux / macOS
.venv\Scripts\activate          # Windows

# Install the package in editable mode with dev dependencies
pip install -e ".[dev]"
```

Verify the CLI is available:

```bash
sandbox --help
```

---

## Running the Tests

The test suite uses `pytest`. All tests mock Docker and Odoo — no live services are required.

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_cli.py

# Run a specific test
pytest tests/test_cli.py::test_generate_command

# Run with coverage report
pytest --cov=sandboxerp --cov-report=term-missing
```

The full suite currently contains **304 tests**. All must pass before opening a PR.

---

## Writing Tests

### Overview

Tests live in `tests/`. Each module in `sandboxerp/` has a corresponding test file. Tests use `pytest` together with `unittest.mock` — no Docker daemon or live Odoo instance is required.

CLI tests use `typer.testing.CliRunner` to invoke commands in-process.

### Fixtures

Common fixtures are defined directly in each test file. There are no shared `conftest.py` fixtures at this time; if you find yourself repeating the same setup across multiple files, open a discussion before adding one.

### Mocking Conventions

| What you need to mock | How |
|---|---|
| Docker daemon calls | `unittest.mock.patch("sandboxerp.engine.docker.<method>")` |
| Odoo XML-RPC calls | `unittest.mock.patch("sandboxerp.engine.odoo.OdooClient.<method>")` |
| HTTP calls (httpx) | `unittest.mock.patch("httpx.post")` or `unittest.mock.patch("httpx.get")` |
| File system | `tmp_path` pytest fixture |

### Testing Against a Real Odoo Instance

The standard test suite never hits a real Odoo instance. If you want to run an integration test manually:

```bash
# Start a real sandbox first
sandbox generate --country cl --industry retail --profile small --seed 42

# Then run your integration script against http://localhost:8069
# user: admin  password: admin  db: sandbox
```

Do not commit integration tests that require a live Odoo — they belong in a separate `tests/integration/` directory and must be skipped by default:

```python
import pytest

@pytest.mark.integration
def test_real_odoo():
    ...
```

Run integration tests explicitly:

```bash
pytest -m integration
```

### Example: Testing a CLI Command

```python
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock
from sandboxerp.cli.main import app

runner = CliRunner()

def test_generate_invokes_docker():
    with patch("sandboxerp.engine.docker.start_containers") as mock_start:
        mock_start.return_value = MagicMock()
        result = runner.invoke(app, ["generate", "--country", "cl",
                                     "--industry", "retail",
                                     "--profile", "small",
                                     "--seed", "42"])
        assert result.exit_code == 0
        mock_start.assert_called_once()
```

### Naming Conventions

- Test files: `test_<module>.py`
- Test functions: `test_<what_it_does>()`
- Use descriptive names — `test_generate_requires_country_flag` is better than `test_generate_1`

---

## Project Structure

```
sandboxerp/
├── pyproject.toml
├── README.md
├── LICENSE
├── sandboxerp/
│   ├── cli/            # Typer commands (generate, start, stop, destroy)
│   ├── engine/         # Core logic (docker, odoo, installer, time, persona…)
│   ├── packs/          # Pack loader, registry, and built-in YAML packs
│   └── docker/         # Docker Compose template generation
└── tests/
```

Key conventions:

- Every module starts with a docstring including `:author: Hector Colina / Team360 <https://team360.cl>`
- CLI subcommands are registered via `app.add_typer()` and use `@app.callback()`
- Docstrings follow Sphinx / sphinx-autodoc-typehints style

---

## Adding a Country Pack

Country packs live in `sandboxerp/packs/builtin/` as YAML files.

A country pack covers **Layer 1 (country data)** and **Layer 2 (Odoo localization modules)**. It must be generic — no industry-specific data belongs here.

### Steps

1. Create `sandboxerp/packs/builtin/country_<iso>.yaml` using `country_cl.yaml` as reference.
2. Define at minimum:

```yaml
country:
  code: mx           # ISO 3166-1 alpha-2
  name: Mexico
  currency: MXN
  language: es_MX
  vat_prefix: MX

odoo_modules:
  - l10n_mx
  - l10n_mx_edi

regions:             # List of states/provinces
  - name: Ciudad de México
    code: CDMX
  # ...
```

3. Register the pack in `sandboxerp/packs/registry.py`.
4. Add a test file `tests/test_pack_<iso>.py` covering schema validation and field presence.
5. Run the full test suite — all 304+ tests must still pass.

---

## Adding an Industry Pack

Industry packs live in `sandboxerp/packs/builtin/` as YAML files.

An industry pack covers **Layer 3 (industry data)**. It must be generic — no country-specific data belongs here. Country-specific fields (tax rates, document types, etc.) are injected by the country pack at generation time.

### Steps

1. Create `sandboxerp/packs/builtin/<industry>.yaml` using `retail.yaml` as reference.
2. Define at minimum:

```yaml
industry: accounting   # unique slug

odoo_modules:
  - account
  - account_accountant

profiles:
  small:
    customers: 30
    suppliers: 5
    products: 20
    sale_orders: 30
  medium:
    customers: 200
    suppliers: 20
    products: 80
    sale_orders: 200

product_categories:
  - name: Services
    margin_min: 0.40
    margin_max: 0.80
```

3. Register the pack in `sandboxerp/packs/registry.py`.
4. Add a test file `tests/test_pack_<industry>.py`.
5. Run the full test suite.

---

## Branching and Commit Conventions

### Branches

| Branch | Purpose |
|---|---|
| `main` | Stable. Protected. Merge via PR only. |
| `feat/<name>` | One branch per feature or fix. |

Never mix features in the same branch.

### Commit Messages

This project follows [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | Use for |
|---|---|
| `feat:` | New functionality |
| `fix:` | Bug fixes |
| `docs:` | Documentation only |
| `test:` | Adding or fixing tests |
| `refactor:` | Refactoring without functional change |
| `chore:` | Maintenance (deps, config, tooling) |

Examples:

```
feat: add country pack for Mexico
fix: handle missing vat_prefix in partner creation
docs: add industry pack guide to DEVELOPMENT.md
test: cover persona_engine edge cases
```

---

## Submitting a Pull Request

1. Fork the repository and create a `feat/<name>` branch from `main`.
2. Make your changes following the conventions in this guide.
3. Ensure all tests pass: `pytest`
4. Open a PR against `main`. PR titles and descriptions should be in **English**.
5. Describe what the change does, why it's needed, and how it was tested.

PRs that break the test suite or lack tests for new code will not be merged.

---

## License

SandboxERP is released under the MIT License. See [LICENSE](LICENSE) for details.
Copyright © Team360 — [https://team360.cl](https://team360.cl)
