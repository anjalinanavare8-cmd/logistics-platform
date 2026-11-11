"""SLA breach detection + exception escalation. Run on a schedule (Celery beat)."""
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import Shipment, ShipmentException, Status as S
from . import tracking, notifications

log = logging.getLogger(__name__)
OPEN = [S.CREATED, S.PICKED_UP, S.WAREHOUSE_RECEIVED, S.IN_TRANSIT, S.OUT_FOR_DELIVERY]


def detect_sla_breaches(db: Session, as_of: datetime | None = None) -> int:
    as_of = as_of or datetime.now(timezone.utc)
    rows = db.scalars(select(Shipment).where(
        Shipment.status.in_([s.value for s in OPEN]),
        Shipment.sla_due_at < as_of)).all()
    count = 0
    for sh in rows:
        # CREATED can't go to DELAYED in the state machine; log exception only
        if tracking.can_transition(S(sh.status), S.DELAYED):
            tracking.transition(db, sh, S.DELAYED, "SLA breached")
        db.add(ShipmentException(shipment_id=sh.id, kind="delivery_delay"))
        notifications.queue(db, sh, "sla_breach")
        count += 1
    log.info("sla scan complete", extra={"extra_data": {"breaches": count}})
    return count


def escalate(db: Session, exc: ShipmentException, max_level: int = 3):
    """Level 1 dispatcher -> 2 ops manager -> 3 admin."""
    if not exc.resolved and exc.escalation_level < max_level:
        exc.escalation_level += 1
