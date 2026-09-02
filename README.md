# Price watcher

Pet backend for shop price subscriptions. A user sets a target price; a worker checks the shop on a schedule and emails them when the price drops.

Wildberries is the only shop wired up so far (`shop: wb`).

# How it works


user
    │ HTTP
    ▼
 FastAPI (api)  ──publish──►  queue db  ──►  checker_db
    │ cron every 60s                         (copy of subscriptions)
    └──publish──► queue crone ──► checker_worker
                                        │ Playwright / WB API
                                        └── queue mail_queue ──► sendler (Gmail SMTP)


 Service - Role :

 `api` - Sign-up, JWT cookie, subscription CRUD, cron trigger 
 `checker_db` - Consumes `db`, keeps its own items table 
 `checker_worker` - On `crone`, reads the checker DB and compares price vs threshold 
 `sendler` - Sends mail from `mail_queue`; ~15 min cooldown per item 

Infrastructure: PostgreSQL, RabbitMQ, Docker Compose. Python packages live in a uv workspace.

# Stack

FastAPI, FastStream, SQLAlchemy + Alembic, PostgreSQL, RabbitMQ, Playwright, aiosmtplib, JWT RS256, pytest + Testcontainers.

# Quick start (Docker)

You need Docker and [uv](https://docs.astral.sh/uv/) (uv is for tests and local runs).

1. Copy env files. Names must match `docker-compose.yml`:

```bash
cp .env.example .env
cp api/api.env.example api/api.env
cp checker/checker_worker/checker.env.example checker/checker_worker/checker_worker.env
cp checker/checker_worker/checker.env.example checker/checker_db/checker_db.env
cp sendler/sendler.env.example sendler/sendler.env
```

2. Fill in values. Notes:
   - Root `.env` `DATABASE_USER` is the Postgres user Compose creates.
   - `sql-scripts/init.sql` also creates databases `checker` and `sendler`.
   - `DATABASE_NAME` in `api/api.env` must match `DATABASE_NAME` in `.env` (the API example uses `API`, the root example uses `database` — pick one).
   - Checker services use the `checker` database.
   - `SENDLER_EMAIL` / `SENDLER_PASS` — Gmail plus an [app password]
   - JWT: put `private_key.pem` and `public_key.pem` in `api/` (the private key is gitignored).

```bash
openssl genrsa -out api/private_key.pem 2048
openssl rsa -in api/private_key.pem -pubout -out api/public_key.pem
```

3. Run:

```bash
docker compose up --build
```

API: http://localhost:8000  
Swagger: http://localhost:8000/docs  
RabbitMQ UI (if the port is mapped): http://localhost:15672

Migrations run inside the containers (`alembic upgrade head` before start).

# API

Session cookie: `web-app-session-id` (JWT).

 Method - Path - What it does :

 GET - `/health` - Liveness 
 POST - `/create_user` - Register 
 POST - `/authentication` - Login 
 POST - `/logout` - Logout 
 GET - `/` - List your items 
 POST - `/create_item` - Subscribe (`art`, `name`, `need_price`, `shop`) 
 PATCH - `/patch_item?id=` - Update threshold / fields 
 DELETE - `/delete_item?id=` - Delete 

Create / patch / delete also fan out to checker over the `db` queue.

# Local run (without full Compose)

Start at least Postgres and Rabbit (`docker compose up db rabbit`). Point service env at the host via `*_HOST_DEV` / `localhost`.

Migrations from each service directory:

```bash
cd api && uv run alembic upgrade head
cd checker/checker_db && uv run alembic upgrade head
cd sendler && uv run alembic upgrade head
```

`alembic.ini` / `mig/env.py` take the URL from service settings (`database_url` in Docker; `database_url_to_host` in config for host-side work).

API:

```bash
cd api && uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Workers:

```bash
cd checker/checker_db && uv run faststream run db_worker:app
cd checker/checker_worker && uv run faststream run check:app
cd sendler && uv run faststream run sendler:app
```

# Tests

From the repo root:

```bash
uv sync
uv run pytest tests/apies_test.py
```

The integration test (`tests/integration_test.py`) starts RabbitMQ with Testcontainers: API publishes a create, `checker_db` writes a row. Docker is required.

```bash
uv run pytest tests/integration_test.py -m integration
```

# Layout

```
api/                    FastAPI + Alembic
checker/checker_db/     FastStream consumer for queue db
checker/checker_worker/ parser; queues crone / mail_queue
sendler/                SMTP
sql-scripts/            Postgres init (checker, sendler)
tests/
docker-compose.yml
```

# RabbitMQ queues

 Queue - Publisher - Consumer :

 `db` - api - checker_db -
 `crone` - api (scheduler) - checker_worker 
 `mail_queue` - checker_worker - sendler 
