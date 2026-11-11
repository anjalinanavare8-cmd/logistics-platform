# Logistics Platform (FastAPI + SQLAlchemy)

    pip install -r requirements.txt
    cp .env.example .env
    uvicorn app.main:app --reload        # Swagger at /docs
    celery -A app.tasks worker -B        # SLA scan every 5 min
    pytest

Layers: api (routers) -> services (business rules) -> models (SQLAlchemy).
First admin: insert one User row with role "admin", then use /auth/users.
