import os

os.environ["DATABASE_URL"] = "sqlite:///./test_logistics.db"
os.environ["RATE_LIMIT_PER_MINUTE"] = "100000"

import pytest
from fastapi.testclient import TestClient

from app.core.cache import cache_clear
from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.main import app
from app.models import User


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    cache_clear()
    monkeypatch.setattr("app.services.notifications.dispatch", lambda n: None)  # no broker in tests
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def make_user(role: str, email: str | None = None) -> User:
    with SessionLocal() as db:
        u = User(email=email or f"{role}@t.io", full_name=role.title() + " User", role=role,
                 password_hash=hash_password("Passw0rd!"))
        db.add(u)
        db.commit()
        return u


def headers_for(client, role: str, email: str | None = None) -> dict:
    u = make_user(role, email)
    r = client.post("/auth/login", json={"email": u.email, "password": "Passw0rd!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


SHIPMENT = {
    "sender_name": "Acme Corp", "sender_address": "12 Industrial Rd, Mumbai",
    "receiver_name": "Jane Doe", "receiver_address": "44 Park Street, Delhi",
    "weight_kg": 5, "length_cm": 30, "width_cm": 20, "height_cm": 15, "distance_km": 1400, "priority": "standard",
}
