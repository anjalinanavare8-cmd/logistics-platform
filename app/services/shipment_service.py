import hashlib
import logging
import uuid
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.config import get_settings
from app.core.exceptions import AppError, ConflictError, ForbiddenError, NotFoundError
from app.domain.pricing import SLA_HOURS, calculate_price
from app.domain.tracking import Status, validate_transition
from app.models import Invoice, Shipment, TrackingEvent, User, utcnow
from app.repositories.shipment_repo import ShipmentRepository
from app.schemas import AssignIn, ShipmentCreate
from app.services import notifications
from app.services.audit import audit

log = logging.getLogger("app.shipments")

NOTIFY_ON = {Status.PICKED_UP: "dispatched", Status.DELIVERED: "delivered", Status.DELAYED: "delayed",
             Status.FAILED_DELIVERY: "failed_delivery", Status.RETURNED: "return_initiated"}


def make_fingerprint(d: ShipmentCreate) -> str:
    """Same parties + package + day + client reference => same shipment (duplicate prevention)."""
    raw = "|".join([d.sender_name.lower().strip(), d.sender_address.lower().strip(), d.receiver_name.lower().strip(),
                    d.receiver_address.lower().strip(), str(d.weight_kg), d.priority, d.client_reference or "",
                    utcnow().date().isoformat()])
    return hashlib.sha256(raw.encode()).hexdigest()


def new_tracking_number() -> str:
    return f"SHP-{utcnow():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


class ShipmentService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ShipmentRepository(db)

    # ---- create -------------------------------------------------------
    def create(self, data: ShipmentCreate, actor: User) -> Shipment:
        fp = make_fingerprint(data)
        if (dup := self.repo.get_by_fingerprint(fp)):
            raise ConflictError(f"Duplicate shipment, already exists as {dup.tracking_number}")
        q = calculate_price(data.weight_kg, data.length_cm, data.width_cm, data.height_cm, data.distance_km,
                            data.priority, tuple(data.extras), data.discount_pct, get_settings().tax_rate)
        try:
            s = Shipment(
                tracking_number=new_tracking_number(), fingerprint=fp, created_by=actor.id,
                sla_due_at=utcnow() + timedelta(hours=SLA_HOURS[data.priority]),
                **data.model_dump(exclude={"extras", "discount_pct", "client_reference"}),
            )
            self.repo.add(s)
            self.db.add(TrackingEvent(shipment_id=s.id, status=Status.CREATED.value, actor_id=actor.id, note="Shipment created"))
            self.db.add(Invoice(shipment_id=s.id, base=q.base, weight_charge=q.weight_charge, distance_charge=q.distance_charge,
                                priority_charge=q.priority_charge, extras=q.extras, discount=q.discount, tax=q.tax, total=q.total))
            audit(self.db, actor.id, "create", "shipment", s.id)
            self.db.commit()  # shipment + event + invoice + audit: all or nothing
        except IntegrityError:
            self.db.rollback()  # unique(fingerprint) caught a concurrent duplicate that slipped past the check
            raise ConflictError("Duplicate shipment")
        except Exception:
            self.db.rollback()
            log.exception("shipment creation failed")
            raise
        notifications.dispatch(notifications.build("shipment_created", s.tracking_number, s.receiver_name))
        return s

    def create_bulk(self, items: list[ShipmentCreate], actor: User) -> dict:
        """Each item has its own transaction: one bad row never poisons the batch."""
        created, failed = [], []
        for i, item in enumerate(items):
            try:
                created.append(self.create(item, actor).tracking_number)
            except AppError as e:
                failed.append({"index": i, "error": e.message})
        return {"created": created, "failed": failed}

    # ---- access control ----------------------------------------------
    @staticmethod
    def assert_can_access(s: Shipment, actor: User) -> None:
        if actor.role == "driver" and s.driver_id != actor.id:
            raise ForbiddenError("You can only access shipments assigned to you")

    def get(self, shipment_id: int, actor: User) -> Shipment:
        s = self.repo.get_detail(shipment_id)
        if not s:
            raise NotFoundError("Shipment not found")
        self.assert_can_access(s, actor)
        return s

    # ---- lifecycle -----------------------------------------------------
    def transition(self, shipment_id: int, new: Status, actor: User, note: str | None = None) -> Shipment:
        s = self.repo.get(shipment_id, for_update=True)  # pessimistic lock + optimistic version check
        if not s:
            raise NotFoundError("Shipment not found")
        self.assert_can_access(s, actor)
        validate_transition(Status(s.status), new, s.delivery_attempts, get_settings().max_delivery_attempts)
        try:
            s.status = new.value
            if new == Status.FAILED_DELIVERY:
                s.delivery_attempts += 1
            if new == Status.DELIVERED:
                s.delivered_at = utcnow()
            self.db.add(TrackingEvent(shipment_id=s.id, status=new.value, note=note, actor_id=actor.id))
            audit(self.db, actor.id, f"status:{new.value}", "shipment", s.id, note)
            self.db.commit()
        except StaleDataError:
            self.db.rollback()
            raise ConflictError("Shipment was modified by another request, please retry")
        except Exception:
            self.db.rollback()
            raise
        if new in NOTIFY_ON:
            notifications.dispatch(notifications.build(NOTIFY_ON[new], s.tracking_number, s.receiver_name))
        return s

    def assign(self, shipment_id: int, data: AssignIn, actor: User) -> Shipment:
        s = self.repo.get(shipment_id, for_update=True)
        if not s:
            raise NotFoundError("Shipment not found")
        try:
            if data.driver_id is not None:
                s.driver_id = data.driver_id
            if data.warehouse_id is not None:
                s.warehouse_id = data.warehouse_id
            audit(self.db, actor.id, "assign", "shipment", s.id, data.model_dump_json())
            self.db.commit()
        except StaleDataError:
            self.db.rollback()
            raise ConflictError("Shipment was modified by another request, please retry")
        except IntegrityError:
            self.db.rollback()
            raise AppError("Unknown driver or warehouse")
        return s
