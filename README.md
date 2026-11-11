# Enterprise Logistics, Shipment & Fleet Operations Platform

A Python backend for managing shipments, warehouses, fleet, tracking, pricing, notifications and operational analytics. Built with **FastAPI, SQLAlchemy, Pydantic and JWT**, with Celery/Redis for scheduled jobs.

**Project ID:** PY-DEV-W3-018 | **Domain:** Logistics / Supply Chain / Fleet Technology

---

## Features

| Module | What it does |
|---|---|
| **User & Access** | 5 roles (Admin, Ops Manager, Warehouse Manager, Dispatcher, Driver), JWT login, role-based permissions, audit log |
| **Shipments** | Create shipments with auto-generated tracking numbers, priority levels, pagination, filtering, sorting and search |
| **Warehouses** | Multiple warehouses, capacity tracking, receiving parcels, capacity alert at 90% |
| **Fleet** | Vehicle registration, type and capacity, driver assignment |
| **Tracking Engine** | State machine from Created to Delivered, plus Delayed, Failed Delivery and Returned; full timestamped history |
| **Pricing & Billing** | Base, weight, distance, priority and extra-service charges, 18% tax, discount support, invoice created per shipment |
| **Exceptions & SLA** | Automatic SLA-breach detection, exception records, escalation levels |
| **Notifications** | Saved first, sent in the background with 3 retries |
| **Analytics** | Delivery success rate, failed and return rates, delayed count, revenue by category |

## Tech Stack

Python 3.11+, FastAPI, SQLAlchemy 2, Pydantic 2, PyJWT, PostgreSQL (SQLite for local use), Celery + Redis, Pytest.

## Architecture

```
Request -> api/ (routers, JWT, RBAC) -> services/ (business rules) -> models.py (SQLAlchemy) -> Database
```

```
app/
  api/        auth.py, shipments.py, ops.py, deps.py
  core/       config, db session, security (JWT), logging, cache
  services/   tracking, pricing, sla, notifications, shipments
  models.py   database tables
  schemas.py  request validation
  tasks.py    Celery scheduled jobs
tests/        pricing, state machine, API tests
```

### Tracking state machine

```
Created -> Picked Up -> Warehouse Received -> In Transit -> Out for Delivery -> Delivered
                 any in-flight step -> Delayed
Out for Delivery -> Failed Delivery -> (re-attempt) or Returned
```

Skipping steps is rejected with HTTP 409. After 3 failed deliveries the shipment is returned automatically.

### How the advanced requirements are handled

| Requirement | Approach |
|---|---|
| Duplicate shipment prevention | `Idempotency-Key` header plus a unique database constraint |
| Concurrent updates | Version column (optimistic locking), conflict returns 409 |
| Warehouse over-capacity race | Row lock on the warehouse |
| Transaction rollback | One transaction per request, rollback on any error |
| SLA breach detection | Celery beat job every 5 minutes |
| Retry for failed jobs | Celery auto-retry with backoff, 3 notification retries |
| Unauthorized access | JWT, role checks, drivers see only their own shipments |
| Database failure | Returns 503 instead of crashing |
| Caching and rate limiting | TTL cache on analytics, per-IP rate limit |
| Audit trail | Logged on create, assign, status change and receive |

## Getting Started

```bash
git clone https://github.com/anjalinanavare8-cmd/logistics-platform.git
cd logistics-platform
python -m venv venv
venv\Scripts\activate          # Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env         # Mac/Linux: cp .env.example .env
```

For quick local use, delete the `DATABASE_URL` line in `.env` and the app uses a local SQLite file. For PostgreSQL, set:

```
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/logistics
```

### Run the server

```bash
uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000/docs** for the interactive Swagger documentation.

### Create the first admin and sample data

```bash
python create_admin.py     # admin@x.com / Admin@1234
python seed.py             # 30 demo shipments, warehouses, drivers (password: Pass@1234)
```

### Optional: scheduled jobs

```bash
redis-server
celery -A app.tasks worker -B
```

### Run tests

```bash
pytest -v
```

## API Overview

| Method | Path | Roles |
|---|---|---|
| POST | `/auth/login` | public |
| POST | `/auth/users` | admin |
| POST | `/shipments` | dispatcher, ops, warehouse |
| GET | `/shipments?status=&q=&sort=&page=&size=` | any logged-in user (drivers see only their own) |
| GET | `/shipments/{tracking_no}/events` | any logged-in user |
| POST | `/shipments/{tracking_no}/status` | any logged-in user (drivers: own shipments only) |
| POST | `/shipments/{tracking_no}/assign/{driver_id}` | dispatcher |
| POST | `/warehouses` | ops, warehouse |
| POST | `/warehouses/{id}/receive/{tracking_no}` | warehouse manager |
| POST | `/vehicles` | ops, dispatcher |
| GET | `/analytics/summary` | ops manager |

Admin can access every endpoint. Send the token as `Authorization: Bearer <token>`.

## Demo Walkthrough

1. Log in as `admin@x.com` and authorize in Swagger.
2. Log in as `disp@x.com` and create a shipment with `POST /shipments`.
3. Move it through `picked_up`, `warehouse_received`, `in_transit`, `out_for_delivery`, `delivered`.
4. Try skipping a step (for example `created` to `delivered`) and see the 409 error.
5. View the history with `GET /shipments/{tracking_no}/events`.
6. Log in as `ops@x.com` and open `GET /analytics/summary`.

## Pricing Formula

```
core     = 5.00 + weight_kg x 0.80 + distance_km x 0.12
priority = core x (standard 0, express 0.25, overnight 0.50)
extras   = insurance 3.00, signature 1.50, fragile 4.00
total    = (core + priority + extras - discount) x 1.18
```

## Project Status

**Done:** authentication and roles, shipment APIs, tracking engine, pricing and invoices, warehouse receiving, vehicle registration, notifications with retry, SLA detection, caching, rate limiting, audit log, summary analytics, Swagger docs.

**Planned:** route planning and delivery sequence, vehicle maintenance and utilization, remaining exception types, invoice payment API, daily volume and per-driver analytics, Alembic migrations, async database driver, Docker deployment, Postman collection.

## License

For learning and internship demonstration purposes.
