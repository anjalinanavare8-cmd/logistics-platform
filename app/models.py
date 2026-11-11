import enum
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import (ForeignKey, String, Numeric, Integer, Boolean, DateTime,
                        Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .core.db import Base


def now():
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    ADMIN = "admin"
    OPS_MANAGER = "ops_manager"
    WAREHOUSE_MANAGER = "warehouse_manager"
    DISPATCHER = "dispatcher"
    DRIVER = "driver"


class Status(str, enum.Enum):
    CREATED = "created"
    PICKED_UP = "picked_up"
    WAREHOUSE_RECEIVED = "warehouse_received"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    DELAYED = "delayed"
    FAILED_DELIVERY = "failed_delivery"
    RETURNED = "returned"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default=Role.DRIVER.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    resource: Mapped[str] = mapped_column(String(64))
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Warehouse(Base):
    __tablename__ = "warehouses"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    city: Mapped[str] = mapped_column(String(80))
    capacity: Mapped[int] = mapped_column(Integer)
    current_load: Mapped[int] = mapped_column(Integer, default=0)


class Vehicle(Base):
    __tablename__ = "vehicles"
    id: Mapped[int] = mapped_column(primary_key=True)
    plate: Mapped[str] = mapped_column(String(20), unique=True)
    vehicle_type: Mapped[str] = mapped_column(String(40))
    capacity_kg: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="available")
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    insurance_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Shipment(Base):
    __tablename__ = "shipments"
    __table_args__ = (UniqueConstraint("idempotency_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    tracking_no: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sender_name: Mapped[str] = mapped_column(String(120))
    receiver_name: Mapped[str] = mapped_column(String(120))
    receiver_address: Mapped[str] = mapped_column(String(255))
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    priority: Mapped[str] = mapped_column(String(16), default="standard")
    category: Mapped[str] = mapped_column(String(40), default="general")
    distance_km: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    status: Mapped[str] = mapped_column(String(32), default=Status.CREATED.value, index=True)
    warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id"), nullable=True)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    delivery_attempts: Mapped[int] = mapped_column(Integer, default=0)
    sla_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    version: Mapped[int] = mapped_column(Integer, default=1)   # optimistic lock
    __mapper_args__ = {"version_id_col": version}

    events: Mapped[list["TrackingEvent"]] = relationship(
        back_populates="shipment", order_by="TrackingEvent.id")
    invoice: Mapped["Invoice | None"] = relationship(back_populates="shipment", uselist=False)


class TrackingEvent(Base):
    __tablename__ = "tracking_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id"), index=True)
    status: Mapped[str] = mapped_column(String(32))
    note: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    shipment: Mapped[Shipment] = relationship(back_populates="events")


class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id"), unique=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    discount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    tax: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    payment_status: Mapped[str] = mapped_column(String(16), default="pending")
    shipment: Mapped[Shipment] = relationship(back_populates="invoice")


class ShipmentException(Base):
    __tablename__ = "shipment_exceptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    escalation_level: Mapped[int] = mapped_column(Integer, default=1)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id"), index=True)
    event: Mapped[str] = mapped_column(String(40))
    channel: Mapped[str] = mapped_column(String(16), default="email")
    status: Mapped[str] = mapped_column(String(16), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
