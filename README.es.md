# SandboxERP

**Genera entornos Odoo completos y coherentes desde una spec YAML.**

SandboxERP es una herramienta CLI open source pensada para Odoo partners, developers y equipos de QA. Levanta una instancia Odoo 17 completamente poblada en minutos, con datos realistas, localización correcta y comportamiento de negocio consistente.

> Desarrollado por [Team360](https://team360.cl)

---

## ¿Por qué SandboxERP?

Armar un entorno de demo o testing realista en Odoo es tedioso. Necesitas clientes con aspecto real, productos, órdenes de venta, fechas que tengan sentido y datos que se comporten como datos ERP reales — leads que se convierten en pedidos, pedidos en facturas, facturas que se pagan (o no).

SandboxERP hace todo eso con un solo comando.

---

## Características

- **Un comando** para generar un entorno Odoo 17 completamente poblado
- **Country packs** — datos localizados: RUT/RFC/BTW/NIF, moneda, idioma, regiones, bancos
- **Industry packs** — categorías de productos, módulos y volúmenes de transacción según la industria
- **Profiles** — escala desde `small` (50 clientes) hasta `enterprise` (2.000+)
- **Reproducible** — flag `--seed` para generación determinista de datos
- **Comportamiento causal** — las órdenes de venta fluyen por entrega, factura y pago
- **Coherencia temporal** — fechas, estacionalidad y mora que tienen sentido
- **Persona engine** — comportamiento consistente por partner (pagadores puntuales, clientes de alto valor, etc.)
- **Basado en Docker** — sin configuración manual de Odoo

---

## Requisitos

### Python 3.10+

Verifica tu versión:

```bash
python --version
```

Si necesitas instalar o actualizar Python, descárgalo desde [python.org](https://www.python.org/downloads/).

### pip

pip viene incluido con Python 3.10+. Verifica que esté disponible:

```bash
pip --version
```

Si no está instalado:

**macOS / Linux:**
```bash
curl -sS https://bootstrap.pypa.io/get-pip.py | python
```

**Windows:**
```bash
python -m ensurepip --upgrade
```

### Docker y Docker Compose v2

SandboxERP usa Docker para correr Odoo y PostgreSQL — no se requiere instalar ninguno de los dos manualmente.

**macOS / Windows:** Instala [Docker Desktop](https://www.docker.com/products/docker-desktop/), que incluye Docker Compose v2.

**Linux (Ubuntu/Debian):**

```bash
# Instalar Docker Engine
curl -fsSL https://get.docker.com | sh

# Agregar tu usuario al grupo docker (evita usar sudo)
sudo usermod -aG docker $USER
newgrp docker
```

Docker Compose v2 viene incluido como plugin de Docker desde Docker Engine 23.0. Verifica:

```bash
docker compose version   # debe mostrar v2.x.x o superior
```

> **Nota:** SandboxERP requiere `docker compose` (v2 plugin). El comando `docker-compose` legacy (v1, binario independiente) no está soportado.

---

## Instalación

```bash
# Clonar el repositorio
git clone https://github.com/getsandboxerp/sandboxerp.git
cd sandboxerp

# Crear y activar un entorno virtual
python -m venv .venv
source .venv/bin/activate       # Linux / macOS
.venv\Scripts\activate          # Windows

# Instalar
pip install -e .
```

Si el comando `sandbox` no se encuentra después de la instalación, es probable que el entorno virtual no esté activado. Asegúrate de ejecutar:

```bash
source .venv/bin/activate       # Linux / macOS
.venv\Scripts\activate          # Windows
```

Debes activar el entorno virtual cada vez que abras una nueva sesión de terminal. Verifica que el CLI esté disponible con:

```bash
sandbox --help
```

---

## Inicio rápido

```bash
# Generar un entorno retail chileno (perfil small)
sandbox generate --country cl --industry retail --profile small --seed 42

# Generar un entorno retail holandés
sandbox generate --country nl --industry retail --profile small --seed 42

# Acceder a Odoo en http://localhost:8069
# usuario: admin  |  contraseña: admin  |  base de datos: sandbox
```

Para exponer Odoo en todas las interfaces de red (por ejemplo, para acceso de equipo):

```bash
sandbox generate --country cl --industry retail --profile small --seed 42 --bind 0.0.0.0 --port 8069
```

> **Nota:** `--bind 0.0.0.0` requiere confirmación explícita.

---

## Referencia de comandos

```bash
sandbox generate --country <código> --industry <nombre> --profile <tamaño> [--seed N] [--bind HOST] [--port N]
sandbox start
sandbox stop
sandbox destroy
sandbox destroy --force
sandbox --help
sandbox generate --help
```

---

## Packs disponibles

### Países

| Código | País | Moneda | Idioma | Tax ID |
|--------|------|--------|--------|--------|
| `cl` | Chile | CLP | es_CL | RUT |
| `mx` | México | MXN | es_MX | RFC |
| `nl` | Países Bajos | EUR | nl_NL | BTW-nummer |
| `pt` | Portugal | EUR | pt_PT | NIF |

### Industrias

| Nombre | Módulos Odoo |
|--------|-------------|
| `retail` | sale_management, stock, account, purchase |

### Perfiles

| Perfil | Clientes | Proveedores | Productos | Órdenes de venta |
|--------|----------|-------------|-----------|------------------|
| `small` | 50 | 8 | 30 | 50 |
| `medium` | 300 | 30 | 120 | 300 |
| `enterprise` | 2.000 | 100 | 500 | 2.000 |
| `benchmark` | 10.000 | 400 | 2.000 | 10.000 |

---

## Qué se genera

Al ejecutar `sandbox generate --country nl --industry retail --profile small --seed 42`:

- ✓ Instancia Odoo 17 con localización holandesa (`l10n_nl`)
- ✓ Idioma configurado en `nl_NL`, moneda EUR
- ✓ Empresa configurada con datos de Países Bajos
- ✓ 50 clientes + 8 proveedores con BTW-nummers válidos
- ✓ 30 productos con SKUs, precios y márgenes por categoría
- ✓ 50 órdenes de venta distribuidas en 12 meses con estacionalidad retail
- ✓ Personas por partner (puntual, frecuente, alto valor, etc.)
- ✓ Fechas coherentes vía Time Engine + mora por persona

---

## Otros comandos

```bash
# Detener los containers (los datos se conservan)
sandbox stop

# Iniciar containers previamente detenidos
sandbox start

# Eliminar containers y volúmenes
sandbox destroy

# Eliminar sin confirmación
sandbox destroy --force
```

---

## Contribuciones

¡Las contribuciones son bienvenidas! Por favor lee [DEVELOPMENT.md](DEVELOPMENT.md) antes de abrir un PR.

---

## Licencia

MIT License — Copyright © [Team360](https://team360.cl)
