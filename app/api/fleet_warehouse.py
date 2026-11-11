from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.exceptions import ConflictError
from app.db.session import get_db
from app.models import User, Vehicle, Warehouse
from app.schemas import VehicleCreate, VehicleOut, WarehouseCreate, WarehouseOut
from app.services.audit import audit

router = APIRouter(tags=["warehouses & fleet"])


def _wh_out(w: Warehouse) -> WarehouseOut:
    util = round(100 * w.current_load / w.capacity, 2) if w.capacity else 0
    out = WarehouseOut.model_validate(w)
    out.utilization_pct, out.capacity_alert = util, util >= 90  # capacity alert threshold
    return out


@router.post("/warehouses", response_model=WarehouseOut, status_code=201)
def create_warehouse(body: WarehouseCreate, user: User = Depends(require_roles("admin", "ops_manager", "warehouse_manager")),
                     db: Session = Depends(get_db)):
    w = Warehouse(**body.model_dump())
    try:
        db.add(w)
        db.flush()
        audit(db, user.id, "create", "warehouse", w.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("Warehouse name already exists")
    return _wh_out(w)


@router.get("/warehouses", response_model=list[WarehouseOut])
def list_warehouses(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [_wh_out(w) for w in db.execute(select(Warehouse).order_by(Warehouse.id)).scalars()]


@router.post("/vehicles", response_model=VehicleOut, status_code=201)
def create_vehicle(body: VehicleCreate, user: User = Depends(require_roles("admin", "ops_manager")), db: Session = Depends(get_db)):
    v = Vehicle(**body.model_dump())
    try:
        db.add(v)
        db.flush()
        audit(db, user.id, "create", "vehicle", v.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("Plate already registered, or unknown driver")
    return v


@router.get("/vehicles", response_model=list[VehicleOut])
def list_vehicles(_: User = Depends(require_roles("admin", "ops_manager", "dispatcher")), db: Session = Depends(get_db)):
    return list(db.execute(select(Vehicle).order_by(Vehicle.id)).scalars())
