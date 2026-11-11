"""Tracking engine: a strict state machine + append-only event history."""
from sqlalchemy.orm import Session
from ..models import Shipment, Status as S, TrackingEvent

ALLOWED: dict[S, set[S]] = {
    S.CREATED: {S.PICKED_UP},
    S.PICKED_UP: {S.WAREHOUSE_RECEIVED, S.DELAYED},
    S.WAREHOUSE_RECEIVED: {S.IN_TRANSIT, S.DELAYED},
    S.IN_TRANSIT: {S.OUT_FOR_DELIVERY, S.DELAYED},
    S.OUT_FOR_DELIVERY: {S.DELIVERED, S.FAILED_DELIVERY, S.DELAYED},
    S.DELAYED: {S.IN_TRANSIT, S.OUT_FOR_DELIVERY, S.RETURNED},
    S.FAILED_DELIVERY: {S.OUT_FOR_DELIVERY, S.RETURNED},   # re-attempt or return
    S.DELIVERED: set(),
    S.RETURNED: set(),
}
MAX_ATTEMPTS = 3


class InvalidTransition(Exception):
    pass


def can_transition(cur: S, new: S) -> bool:
    return new in ALLOWED[cur]


def transition(db: Session, shipment: Shipment, new: S, note: str = "") -> TrackingEvent:
    cur = S(shipment.status)
    if not can_transition(cur, new):
        raise InvalidTransition(f"{cur.value} -> {new.value} is not allowed")
    if new == S.FAILED_DELIVERY:
        shipment.delivery_attempts += 1
    shipment.status = new.value
    ev = TrackingEvent(shipment=shipment, status=new.value, note=note)
    db.add(ev)
    # Auto-return after too many failed attempts
    if new == S.FAILED_DELIVERY and shipment.delivery_attempts >= MAX_ATTEMPTS:
        shipment.status = S.RETURNED.value
        db.add(TrackingEvent(shipment=shipment, status=S.RETURNED.value,
                             note="Max delivery attempts reached"))
    return ev
