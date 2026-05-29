# SandboxERP

> Generate realistic, reproducible Odoo environments from a YAML spec.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Odoo](https://img.shields.io/badge/Odoo-17%20%7C%2018-blueviolet)](https://www.odoo.com)
[![Status](https://img.shields.io/badge/status-early%20development-orange)]()

---

## The problem

Odoo's built-in demo data is generic, has no localization, and doesn't reflect how a real business operates.

When you need to demo Odoo to a Chilean retail client, test a module with 50,000 realistic records, or reproduce a QA bug with the exact same dataset every time — you're on your own.

**SandboxERP solves this.**

---

## What it does

Generates complete, coherent Odoo companies from a declarative YAML spec. Not isolated records — full ERP causality:

```
Customer → Lead → Quotation → SO → Delivery → Invoice → Payment → Accounting entry
```

With real LATAM localization and reproducible seeds.

---

## Quick start

```bash
pip install sandboxerp

sandbox generate \
  --country cl \
  --industry retail \
  --profile small \
  --seed 42
```

---

## YAML spec

```yaml
odoo_version: 18
country: CL
industry: retail
profile: small
seed: 42
```

```bash
sandbox generate sandbox.yaml
```

Same spec + seed → always the same environment.

---

## Country packs

| Pack | Tax ID | Status |
|---|---|---|
| Chile (CL) | RUT | 🚧 In progress |
| México (MX) | RFC | 🚧 In progress |

---

## Contributing

See [packs repository](https://github.com/getsandboxerp/packs) for the pack spec format.

---

## License

MIT © [getsandboxerp](https://github.com/getsandboxerp)

---

*Built for the Odoo community. Especially LATAM.*
