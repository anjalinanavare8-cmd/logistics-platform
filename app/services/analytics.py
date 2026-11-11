from datetime import timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.cache import cached
from app.core.config import get_settings
from app.models import Invoice, Shipment, Vehicle, Warehouse, utcnow

TTL = get_settings().cache_ttl_seconds


def _pct(n: int, d: int) -> float:
    return round(100 * n / d, 2) if d else 0.0


class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    @cached(TTL)
    def summary(self, days: int = 30) -> dict:
        since = utcnow() - timedelta(days=days)
        rows = self.db.execute(
            select(Shipment.status, func.count(), func.sum(case((Shipment.delivery_attempts > 0, 1), else_=0)))
            .where(Shipment.created_at >= since).group_by(Shipment.status)
        ).all()
        by_status = {r[0]: r[1] for r in rows}
        total = sum(by_status.values())
        with_failures = sum(int(r[2] or 0) for r in rows)
        delivered, returned = by_status.get("delivered", 0), by_status.get("returned", 0)
        failed_now = by_status.get("failed_delivery", 0)

        pairs = self.db.execute(
            select(Shipment.created_at, Shipment.delivered_at)
            .where(Shipment.created_at >= since, Shipment.delivered_at.is_not(None))
        ).all()
        avg_hours = round(sum((d - c).total_seconds() for c, d in pairs) / len(pairs) / 3600, 2) if pairs else 0.0

        return {
            "window_days": days,
            "total_shipments": total,
            "by_status": by_status,
            "delivery_success_rate_pct": _pct(delivered, delivered + returned + failed_now),
            "avg_delivery_hours": avg_hours,
            "delayed_shipments": by_status.get("delayed", 0),
            "failed_delivery_rate_pct": _pct(with_failures, total),
            "return_rate_pct": _pct(returned, total),
        }

    @cached(TTL)
    def daily_volume(self, days: int = 14) -> list[dict]:
        since = utcnow() - timedelta(days=days)
        day = func.date(Shipment.created_at)
        rows = self.db.execute(select(day, func.count()).where(Shipment.created_at >= since)
                               .group_by(day).order_by(day)).all()
        return [{"date": str(d), "shipments": n} for d, n in rows]

    @cached(TTL)
    def revenue_by_category(self) -> list[dict]:
        rows = self.db.execute(
            select(Shipment.priority, func.count(), func.coalesce(func.sum(Invoice.total), 0))
            .join(Invoice, Invoice.shipment_id == Shipment.id).group_by(Shipment.priority)
        ).all()
        return [{"category": p, "shipments": n, "revenue": float(r)} for p, n, r in rows]

    @cached(TTL)
    def driver_performance(self) -> list[dict]:
        rows = self.db.execute(
            select(Shipment.driver_id, func.count(),
                   func.sum(case((Shipment.status == "delivered", 1), else_=0)),
                   func.sum(Shipment.delivery_attempts))
            .where(Shipment.driver_id.is_not(None)).group_by(Shipment.driver_id)
        ).all()
        return [{"driver_id": d, "assigned": n, "delivered": int(dv or 0), "failed_attempts": int(f or 0),
                 "success_rate_pct": _pct(int(dv or 0), n)} for d, n, dv, f in rows]

    @cached(TTL)
    def warehouse_performance(self) -> list[dict]:
        rows = self.db.execute(
            select(Warehouse.id, Warehouse.name, Warehouse.capacity, Warehouse.current_load, func.count(Shipment.id),
                   func.sum(case((Shipment.status == "delivered", 1), else_=0)))
            .outerjoin(Shipment, Shipment.warehouse_id == Warehouse.id).group_by(Warehouse.id)
        ).all()
        return [{"warehouse_id": i, "name": n, "utilization_pct": _pct(load, cap), "shipments": c,
                 "delivered": int(dv or 0)} for i, n, cap, load, c, dv in rows]

    @cached(TTL)
    def vehicle_utilization(self) -> dict:
        total = self.db.execute(select(func.count()).select_from(Vehicle)).scalar_one()
        busy = self.db.execute(select(func.count()).select_from(Vehicle).where(Vehicle.available.is_(False))).scalar_one()
        return {"vehicles": total, "in_use": busy, "utilization_pct": _pct(busy, total)}
