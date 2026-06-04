# SandboxERP

**Generate complete, coherent Odoo environments from a YAML spec.**

SandboxERP is an open source CLI tool built for Odoo partners, developers, and QA teams — especially across LATAM. Spin up a fully populated Odoo 17 instance in minutes, with realistic data, proper localization, and consistent business behaviour.

> Built by [Team360](https://team360.cl)

---

## Why SandboxERP?

Setting up a realistic Odoo demo or test environment is tedious. You need real-looking customers, products, sale orders, dates that make sense, and data that behaves the way actual ERP data does — leads that become orders, orders that become invoices, invoices that get paid (or don't).

SandboxERP does all of that from a single command.

---

## Features

- **One command** to generate a fully populated Odoo 17 environment
- **Country packs** — localized data: tax IDs, currency, language, regions, banks
- **Industry packs** — relevant product categories, modules, and transaction volumes
- **Profiles** — scale from `small` (50 customers) to `enterprise` (2,000+)
- **Reproducible** — `--seed` flag for deterministic data generation
- **Causal behaviour** — sale orders flow through delivery, invoice, and payment stages
- **Temporal coherence** — dates, seasonality, and payment delays that make sense
- **Persona engine** — consistent per-partner behaviour (punctual payers, high-value clients, etc.)
- **Docker-based** — no manual Odoo setup required

---

## Requirements

### Python 3.10+

Verify your version:

```bash
python --version
```

If you need to install or upgrade Python, download it from [python.org](https://www.python.org/downloads/).

### pip

pip is included with Python 3.10+. Verify it is available:

```bash
pip --version
```

If it is missing:

**macOS / Linux:**
```bash
curl -sS https://bootstrap.pypa.io/get-pip.py | python
```

**Windows:**
```bash
python -m ensurepip --upgrade
```

### Docker and Docker Compose v2

SandboxERP uses Docker to run Odoo and PostgreSQL — no manual installation of either is required.

**macOS / Windows:** Install [Docker Desktop](https://www.docker.com/products/docker-desktop/), which includes Docker Compose v2.

**Linux (Ubuntu/Debian):**

```bash
# Install Docker Engine
curl -fsSL https://get.docker.com | sh

# Add your user to the docker group (avoids sudo)
sudo usermod -aG docker $USER
newgrp docker
```

Docker Compose v2 is included as a Docker plugin since Docker Engine 23.0. Verify:

```bash
docker compose version   # should print v2.x.x or higher
```

> **Note:** SandboxERP requires `docker compose` (v2 plugin). The legacy `docker-compose` (v1, standalone binary) is not supported.

---

## Installation

```bash
# Clone the repository
git clone https://github.com/getsandboxerp/sandboxerp.git
cd sandboxerp

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate       # Linux / macOS
.venv\Scripts\activate          # Windows

# Install
pip install -e .
```

If the `sandbox` command is not found after installation, your virtual environment is likely not activated. Make sure you run:

```bash
source .venv/bin/activate       # Linux / macOS
.venv\Scripts\activate          # Windows
```

You need to activate the virtual environment every time you open a new terminal session. Verify the CLI is available with:

```bash
sandbox --help
```

---

## Quick Start

```bash
# Generate a Chilean retail environment (small profile)
sandbox generate --country cl --industry retail --profile small --seed 42

# Access Odoo at http://localhost:8069
# user: admin  |  password: admin  |  db: sandbox
```

To expose Odoo on all network interfaces (e.g. for team access):

```bash
sandbox generate --country cl --industry retail --profile small --seed 42 --bind 0.0.0.0 --port 8069
```

> **Note:** `--bind 0.0.0.0` requires explicit confirmation.

---

## CLI Reference

```bash
sandbox generate --country <code> --industry <name> --profile <size> [--seed N] [--bind HOST] [--port N]
sandbox start
sandbox stop
sandbox destroy
sandbox destroy --force
sandbox --help
sandbox generate --help
```

---

## Available Packs

### Countries

| Code | Country | Currency | Language |
|------|---------|----------|----------|
| `cl` | Chile | CLP | es_CL |

### Industries

| Name | Odoo Modules |
|------|-------------|
| `retail` | l10n_cl, l10n_cl_edi, sale_management, stock, … |

### Profiles

| Profile | Customers | Suppliers | Products | Sale Orders |
|---------|-----------|-----------|----------|-------------|
| `small` | 50 | 8 | 30 | 50 |
| `medium` | 300 | 30 | 120 | 300 |
| `enterprise` | 2,000 | 100 | 500 | 2,000 |
| `benchmark` | 10,000 | 400 | 2,000 | 10,000 |

---

## What Gets Generated

Running `sandbox generate --country cl --industry retail --profile small --seed 42` produces:

- ✓ Odoo 17 instance with Chilean localization (`l10n_cl`, `l10n_cl_edi`)
- ✓ Language set to `es_CL`
- ✓ Company configured with CLP currency and Chile defaults
- ✓ 50 customers + 8 suppliers (Faker `es_CL`, valid RUTs)
- ✓ 30 products with SKUs, prices, and category margins
- ✓ 50 sale orders distributed across 12 months with retail seasonality
- ✓ Per-partner personas (punctual, frequent, high-value, etc.)
- ✓ Coherent dates via Time Engine + payment delay per persona

---

## Other Commands

```bash
# Stop the running containers (data preserved)
sandbox stop

# Start previously stopped containers
sandbox start

# Remove containers and volumes
sandbox destroy

# Remove without confirmation prompt
sandbox destroy --force
```

---

## Contributing

Contributions are welcome! Please read [DEVELOPMENT.md](DEVELOPMENT.md) before opening a PR.

---

## License

MIT License — Copyright © [Team360](https://team360.cl)
