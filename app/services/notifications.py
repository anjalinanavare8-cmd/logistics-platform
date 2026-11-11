"""Notification architecture: persist first (outbox), deliver in background with retry."""
import logging
from sqlalchemy.orm import Session
from ..models import Notification, Shipment

log = logging.getLogger(__name__)
MAX_RETRIES = 3


def queue(db: Session, shipment: Shipment, event: str, channel="email") -> Notification:
    n = Notification(shipment_id=shipment.id, event=event, channel=channel)
    db.add(n)
    return n


def _send(n: Notification):
    """Replace with SMTP / webhook call. Raises on failure."""
    log.info("notification sent", extra={"extra_data": {"id": n.id, "event": n.event}})


def deliver(db: Session, n: Notification, sender=_send) -> bool:
    while n.attempts < MAX_RETRIES:
        n.attempts += 1
        try:
            sender(n)
            n.status = "sent"
            return True
        except Exception:
            log.warning("notification failed", extra={"extra_data": {"id": n.id}})
    n.status = "failed"
    return False
