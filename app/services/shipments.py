import secrets
from datetime import timedelta
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..models import Shipment, Invoice, TrackingEvent, now
from . import pricing, notifications

SLA_HOURS = {"standard": 72, "express": 36, "overnight": 18}


def _tracking_no() -> str:
    return "SH" + secrets.token_hex(5).upper()


def create_shipment(db: Session, data: dict, user_id: int, idem_key: str | None):
    # Duplicate prevention: same idempotency key returns the original shipment
    if idem_key:
        existing = db.scalar(select(Shipment).where(Shipment.idempotency_key == idem_key))
        if existing:
            return existing, False
    sh = Shipment(tracking_no=_tracking_no(), idempotency_key=idem_key, created_by=user_id,
                  sla_due_at=now() + timedelta(hours=SLA_HOURS[data["priority"]]),
                  **{k: v for k, v in data.items() if k != "services"})
    db.add(sh)
    try:
        db.flush()   # DB unique constraint is the final guard against races
    except IntegrityError:
        db.rollback()
        return db.scalar(select(Shipment).where(Shipment.idempotency_key == idem_key)), False
    db.add(TrackingEvent(shipment_id=sh.id, status=sh.status, note="Shipment created"))
    p = pricing.calculate(sh.weight_kg, sh.distance_km, sh.priority, data.get("services", ()))
    db.add(Invoice(shipment_id=sh.id, subtotal=p["subtotal"], discount=p["discount"],
                   tax=p["tax"], total=p["total"]))
    notifications.queue(db, sh, "shipment_created")
    return sh, True
