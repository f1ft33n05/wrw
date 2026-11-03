# WRW Business Management System

WRW is a FastAPI and SQLAlchemy business management application with server-rendered Jinja pages and JavaScript interactions.

## Features

- Dashboard metrics and sales trends
- Inventory, categories, discounts, and stock adjustments
- Customers, suppliers, resellers, and account statements
- Sales, POS, receipts, payments, purchases, and reseller reconciliation
- Events with event-linked sales reporting
- Printable quotations and invoices
- Sales, inventory, trend, purchase, and combined reports
- Excel, CSV, and PDF exports
- Database-backed roles and module permissions
- User management and JWT authentication

## Technology

- FastAPI and Uvicorn
- SQLAlchemy and PostgreSQL
- Jinja2 templates
- Pydantic
- Python-JOSE and Passlib
- OpenPyXL and ReportLab
- HTML, CSS, and vanilla JavaScript

## Setup

1. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Copy the example environment file:

   ```powershell
   Copy-Item .env.example .env
   ```

4. Update the PostgreSQL connection and security settings in `.env`. Use a strong value for `SECRET_KEY` and a secure initial admin password.

5. Start the application:

   ```powershell
   uvicorn main:app --reload
   ```

6. Open `http://127.0.0.1:8000`.

API documentation is available at `http://127.0.0.1:8000/docs`.

## Database

SQLAlchemy creates the application tables when the application starts. Startup initialization also applies supported schema updates and seeds roles and initial records when they do not already exist.

Ensure PostgreSQL is running and that `DATABASE_URL` grants access to the configured database.

## Configuration

Environment variables and example values are documented in [.env.example](.env.example). This includes the database URL, JWT settings, session lifetime, timezone, currency, initial administrator, and initial walk-in customer.

Do not commit `.env` or real credentials.

## Enterprise Operations

- Apply database migrations with `alembic upgrade head`.
- Run automated tests with `python -m pytest -q`.
- Liveness: `GET /health/live`
- Readiness: `GET /health/ready`
- Sale creation requires an `Idempotency-Key` header.
- Create PostgreSQL backups with PowerShell:

  ```powershell
  $env:DATABASE_URL="postgresql+psycopg://..."
  $env:BACKUP_DIRECTORY="C:\backups"
  .\scripts\backup_postgres.ps1
  ```

## Deployment

This application is a stateful FastAPI monolith. It requires persistent PostgreSQL storage and server-side execution for Jinja templates, authentication, reports, exports, and scheduled-style startup initialization.

### Render (recommended)

1. Provision a managed PostgreSQL database.
2. Add this repository as a Render Blueprint or create a Docker Web Service.
3. Set `ENVIRONMENT=production`, a PostgreSQL `DATABASE_URL`, a generated `SECRET_KEY`, and initial administrator credentials.
4. Apply migrations before the application is routed to traffic:

   ```sh
   alembic upgrade head
   ```

5. The included `render.yaml` configures the Docker service, generated signing secret, and `/health/live` health check.

Render deployments must use the external PostgreSQL connection URL, not an in-memory or ephemeral database URL.

### Vercel

The `api/index.py` adapter and `vercel.json` expose FastAPI as a Python serverless function:

```sh
vercel
```

Configure the same production environment variables in the Vercel project settings and use a persistent managed PostgreSQL service. Function instances are ephemeral, so generated files, local SQLite databases, and filesystem exports are not durable. Vercel serverless limits also make the Docker/Render deployment preferable for large reports and concurrent use.

### Netlify

The `netlify/functions/api.py` adapter and `netlify.toml` expose FastAPI through a Netlify Function. Deploy the repository through Netlify and configure the production environment variables and managed PostgreSQL connection in the Netlify dashboard.

Netlify Functions are best suited to low-traffic and event-style workloads. Use Render or another long-running container platform for steady POS/reporting workloads.

### Required production configuration

At minimum, configure:

- `DATABASE_URL`
- `SECRET_KEY`
- `ENVIRONMENT=production`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `APP_TIMEZONE`
- `CURRENCY_CODE`

Generate a signing key locally:

```sh
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Never use a committed `.env`, SQLite, or the default development credentials in production. Configure cookies, database backups, and migrations separately according to the platform's deployment lifecycle.
