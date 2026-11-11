from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from ..core.db import get_db, SessionLocal
from ..models import Shipment, Role, Status, User, Notification
from ..schemas import ShipmentCreate, ShipmentOut, StatusUpdate
from ..services import shipments as svc, tracking, notifications
from .deps import current_user, require_roles, audit

router = APIRouter(prefix="/shipments", tags=["shipments"])
STAFF = (Role.OPS_MANAGER, Role.WAREHOUSE_MANAGER, Role.DISPATCHER)


def _deliver_pending():
    db = SessionLocal()
    try:
        for n in db.scalars(select(Notification).where(Notification.status == "pending")):
            notifications.deliver(db, n)
        db.commit()
    finally:
        db.close()


@router.post("", status_code=201)
def create(body: ShipmentCreate, bg: BackgroundTasks, db: Session = Depends(get_db),
           user: User = Depends(require_roles(*STAFF)),
           idempotency_key: str | None = Header(default=None)):
    sh, created = svc.create_shipment(db, body.model_dump(), user.id, idempotency_key)
    if created:
        audit(db, user, "create", "shipment", sh.tracking_no)
        bg.add_task(_deliver_pending)
    return {"id": sh.id, "tracking_no": sh.tracking_no, "duplicate": not created}


@router.get("")
def list_shipments(db: Session = Depends(get_db), user: User = Depends(current_user),
                   status: str | None = None, q: str | None = None,
                   sort: str = Query("-id", pattern="^-?(id|created_at|priority)$"),
                   page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
    stmt = select(Shipment)
    if user.role == Role.DRIVER.value:           # drivers only see their own
        stmt = stmt.where(Shipment.driver_id == user.id)
    if status:
        stmt = stmt.where(Shipment.status == status)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Shipment.tracking_no.ilike(like), Shipment.receiver_name.ilike(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    col = getattr(Shipment, sort.lstrip("-"))
    stmt = stmt.order_by(col.desc() if sort.startswith("-") else col.asc())
    rows = db.scalars(stmt.offset((page - 1) * size).limit(size)).all()
    return {"items": [ShipmentOut.model_validate(r) for r in rows],
            "total": total, "page": page, "size": size}


@router.get("/{tracking_no}/events")
def history(tracking_no: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    sh = db.scalar(select(Shipment).where(Shipment.tracking_no == tracking_no))
    if not sh or (user.role == Role.DRIVER.value and sh.driver_id != user.id):
        raise HTTPException(404, "Shipment not found")     # 404, don't leak existence
    return [{"status": e.status, "note": e.note, "at": e.created_at} for e in sh.events]


@router.post("/{tracking_no}/status")
def update_status(tracking_no: str, body: StatusUpdate, bg: BackgroundTasks,
                  db: Session = Depends(get_db), user: User = Depends(current_user)):
    sh = db.scalar(select(Shipment).where(Shipment.tracking_no == tracking_no))
    if not sh or (user.role == Role.DRIVER.value and sh.driver_id != user.id):
        raise HTTPException(404, "Shipment not found")
    if body.version is not None and body.version != sh.version:
        raise HTTPException(409, "Shipment was modified by someone else; reload")
    try:
        new = Status(body.status)
        tracking.transition(db, sh, new, body.note)
        notifications.queue(db, sh, new.value)
        db.flush()                                          # triggers version check
    except ValueError:
        raise HTTPException(422, "Unknown status")
    except tracking.InvalidTransition as e:
        raise HTTPException(409, str(e))
    except StaleDataError:
        raise HTTPException(409, "Concurrent update detected; retry")
    audit(db, user, "status", "shipment", f"{sh.tracking_no}->{sh.status}")
    bg.add_task(_deliver_pending)
    return {"tracking_no": sh.tracking_no, "status": sh.status, "version": sh.version}
