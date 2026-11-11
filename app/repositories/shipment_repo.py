from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Shipment

SORTABLE = {"created_at", "sla_due_at", "status", "priority", "weight_kg"}


class ShipmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, shipment: Shipment) -> Shipment:
        self.db.add(shipment)
        self.db.flush()  # assigns PK, keeps transaction open
        return shipment

    def get(self, shipment_id: int, for_update: bool = False) -> Shipment | None:
        stmt = select(Shipment).where(Shipment.id == shipment_id)
        if for_update:
            stmt = stmt.with_for_update()  # row lock on PostgreSQL/MySQL; no-op on SQLite
        return self.db.execute(stmt).scalar_one_or_none()

    def get_detail(self, shipment_id: int) -> Shipment | None:
        stmt = (select(Shipment).where(Shipment.id == shipment_id)
                .options(selectinload(Shipment.events), selectinload(Shipment.invoice)))
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_tracking(self, tracking_number: str) -> Shipment | None:
        stmt = (select(Shipment).where(Shipment.tracking_number == tracking_number)
                .options(selectinload(Shipment.events), selectinload(Shipment.invoice)))
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_fingerprint(self, fp: str) -> Shipment | None:
        return self.db.execute(select(Shipment).where(Shipment.fingerprint == fp)).scalar_one_or_none()

    def search(self, *, page: int, size: int, status: str | None = None, priority: str | None = None,
               q: str | None = None, driver_id: int | None = None, created_from: datetime | None = None,
               created_to: datetime | None = None, sort: str = "-created_at") -> tuple[list[Shipment], int]:
        stmt = select(Shipment)
        if status:
            stmt = stmt.where(Shipment.status == status)
        if priority:
            stmt = stmt.where(Shipment.priority == priority)
        if driver_id is not None:
            stmt = stmt.where(Shipment.driver_id == driver_id)
        if created_from:
            stmt = stmt.where(Shipment.created_at >= created_from)
        if created_to:
            stmt = stmt.where(Shipment.created_at <= created_to)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(Shipment.tracking_number.ilike(like), Shipment.receiver_name.ilike(like),
                                  Shipment.receiver_address.ilike(like)))
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        field = sort.lstrip("-")
        if field not in SORTABLE:
            field = "created_at"
        col = getattr(Shipment, field)
        stmt = stmt.order_by(col.desc() if sort.startswith("-") else col.asc(), Shipment.id)
        rows = self.db.execute(stmt.offset((page - 1) * size).limit(size)).scalars().all()
        return list(rows), total
