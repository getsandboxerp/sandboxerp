# SandboxERP

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/getsandboxerp/sandboxerp/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Odoo](https://img.shields.io/badge/Odoo-17%20%7C%2018-875A7B.svg)](https://www.odoo.com/)

> Generate complete, coherent Odoo environments from a single command.

SandboxERP is an open source CLI that spins up fully populated Odoo instances with synthetic but realistic data — correct RUTs, IVA, regional addresses, causal ERP flows (Lead → SO → Delivery → Invoice → Payment) — in minutes, not days.

Built for Odoo partners, developers, and QA teams. Especially in LATAM.

The CLI is free and open source. Always.

---

## Why SandboxERP

Setting up a realistic Odoo demo or test environment is painful:

- Demo data is too generic and never matches your country's tax rules
- Real client data can't be used for testing or training
- Recreating a specific scenario manually takes hours
- Bugs are hard to reproduce without the exact same dataset

SandboxERP solves this with a reproducible, seed-based generator that understands ERP causality and local regulations.

```bash
# A complete Chilean retail company, always the same, in minutes
sandbox generate --country cl --industry retail --profile small --seed 42
```

---

## Features

- **Reproducible** — same seed always produces the same environment
- **Causal data** — documents follow real ERP flows, not random records
- **Country-aware** — RUT, IVA, regions, currency out of the box (CL, MX)
- **Industry packs** — retail, accounting, manufacturing
- **Docker-based** — zero Odoo installation required
- **100% synthetic** — never uses real data, safe for demos and training

---

## Quickstart

**Requirements:** Python 3.10+, Docker

```bash
pip install sandboxerp

sandbox generate --country cl --industry retail --profile small --seed 42
# ✓ Odoo ready at http://localhost:8069 — admin/admin
```

---

## CLI Reference

```bash
# Generate a new environment
sandbox generate --country cl --industry retail --profile small --seed 42

# Expose on all interfaces (requires confirmation)
sandbox generate --country cl --industry retail --profile small \
    --bind 0.0.0.0 --port 8069

# Lifecycle
sandbox start      # resume a stopped environment
sandbox stop       # stop without losing data
sandbox destroy    # remove everything
sandbox destroy --force  # skip confirmation (CI / scripts)

# Help
sandbox --help
sandbox generate --help
```

### Options for `generate`

| Flag | Default | Description |
|---|---|---|
| `--country` | required | ISO country code (`cl`, `mx`) |
| `--industry` | required | Industry vertical (`retail`, `accounting`, `manufacturing`) |
| `--profile` | `small` | Data volume (`small`, `medium`, `enterprise`, `benchmark`) |
| `--seed` | `42` | Random seed for reproducibility |
| `--bind` | `127.0.0.1` | Network interface (use `0.0.0.0` with care) |
| `--port` | `8069` | Host port for Odoo |

---

## Development

### Setup

```bash
git clone https://github.com/getsandboxerp/sandboxerp.git
cd sandboxerp
pip install -e ".[dev]"
```

### Run tests

```bash
pytest
```

### Project structure

```
sandboxerp/
├── sandboxerp/
│   ├── cli/          ← Typer commands (main, generate, start, stop, destroy)
│   ├── engine/       ← orchestration, docker, data generation
│   ├── packs/        ← country and industry pack loader
│   └── docker/       ← compose templates
└── tests/
```

---

## Branching model

| Branch | Purpose |
|---|---|
| `main` | Stable. Every commit here is a versioned release. |
| `dev` | Integration. Day-to-day work merges here first. |
| `feat/xxx` | One branch per feature (e.g. `feat/docker-engine`). |

**Flow:** `feat/xxx` → PR → `dev` → PR → `main`

Never push directly to `main`.

### Contributing code step by step

```bash
# 1. Clone the repo
git clone https://github.com/getsandboxerp/sandboxerp.git
cd sandboxerp

# 2. Create your feature branch off dev
git checkout dev
git checkout -b feat/your-feature

# 3. Install in editable mode with dev dependencies
pip install -e ".[dev]"

# 4. Make your changes, then verify
pytest

# 5. Commit and push
git add .
git commit -m "feat: describe your change"
git push origin feat/your-feature
```

Then open a PR from `feat/your-feature` → `dev` on GitHub.

---

## Contributing

Contributions are welcome. Please open an issue before submitting a PR so we can discuss the approach first.

By contributing you agree your code will be released under the MIT license.

---

## License

MIT — see [LICENSE](LICENSE).

Built by [Team360](https://team360.cl) · [sandboxerp.team360.cl](https://sandboxerp.team360.cl)
