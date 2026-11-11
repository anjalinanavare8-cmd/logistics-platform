"""End-to-end API tests (needs requirements installed). Uses an in-memory SQLite DB."""
import os
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
from fastapi.testclient import TestClient
from app.main import app
from app.core.db import SessionLocal
from app.models import User
from app.core.security import hash_password

client = TestClient(app)


def _login(email, role):
    db = SessionLocal()
    if not db.query(User).filter_by(email=email).first():
        db.add(User(email=email, hashed_password=hash_password("password1"), role=role)); db.commit()
    db.close()
    t = client.post("/auth/login", json={"email": email, "password": "password1"}).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}


BODY = {"sender_name": "A", "receiver_name": "B", "receiver_address": "12 Main St",
        "weight_kg": "5", "distance_km": "50"}


def test_rbac_blocks_driver_from_creating():
    h = _login("d1@x.com", "driver")
    assert client.post("/shipments", json=BODY, headers=h).status_code == 403


def test_idempotent_create_and_lifecycle():
    h = _login("disp@x.com", "dispatcher")
    h2 = {**h, "Idempotency-Key": "abc-1"}
    a = client.post("/shipments", json=BODY, headers=h2).json()
    b = client.post("/shipments", json=BODY, headers=h2).json()
    assert a["id"] == b["id"] and b["duplicate"] is True
    tn = a["tracking_no"]
    assert client.post(f"/shipments/{tn}/status", json={"status": "delivered"}, headers=h).status_code == 409
    assert client.post(f"/shipments/{tn}/status", json={"status": "picked_up"}, headers=h).status_code == 200
    assert len(client.get(f"/shipments/{tn}/events", headers=h).json()) == 2
