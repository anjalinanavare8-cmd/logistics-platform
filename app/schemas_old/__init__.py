from datetime import datetime
from decimal import Decimal
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.tracking import Status

T = TypeVar("T")
Role = Literal["admin", "ops_manager", "warehouse_manager", "dispatcher", "driver"]
Priority = Literal["express", "standard", "economy"]


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int


class UserCreate(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    role: Role


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ShipmentCreate(BaseModel):
    sender_name: str = Field(min_length=2, max_length=120)
    sender_address: str = Field(min_length=5, max_length=255)
    receiver_name: str = Field(min_length=2, max_length=120)
    receiver_address: str = Field(min_length=5, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    weight_kg: float = Field(gt=0, le=2000)
    length_cm: float = Field(gt=0, le=500)
    width_cm: float = Field(gt=0, le=500)
    height_cm: float = Field(gt=0, le=500)
    distance_km: float = Field(ge=0, le=20000)
    priority: Priority = "standard"
    extras: list[Literal["insurance", "signature", "fragile"]] = []
    discount_pct: float = Field(default=0, ge=0, le=100)
    client_reference: str | None = Field(default=None, max_length=64)

    @field_validator("sender_address", "receiver_address")
    @classmethod
    def address_has_letters(cls, v: str) -> str:
        if not any(c.isalpha() for c in v):  # cheap address-validation stand-in
            raise ValueError("address must contain letters")
        return v.strip()


class TrackingEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str
    note: str | None
    created_at: datetime


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    base: Decimal
    weight_charge: Decimal
    distance_charge: Decimal
    priority_charge: Decimal
    extras: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal
    payment_status: str


class ShipmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tracking_number: str
    sender_name: str
    receiver_name: str
    receiver_address: str
    weight_kg: float
    priority: str
    status: str
    delivery_attempts: int
    sla_due_at: datetime
    created_at: datetime
    delivered_at: datetime | None
    driver_id: int | None
    warehouse_id: int | None


class ShipmentDetail(ShipmentOut):
    events: list[TrackingEventOut]
    invoice: InvoiceOut | None


class StatusUpdate(BaseModel):
    status: Status
    note: str | None = Field(default=None, max_length=255)


class AssignIn(BaseModel):
    driver_id: int | None = None
    warehouse_id: int | None = None


class WarehouseCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    city: str
    capacity: int = Field(gt=0)


class WarehouseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    city: str
    capacity: int
    current_load: int
    utilization_pct: float = 0
    capacity_alert: bool = False


class VehicleCreate(BaseModel):
    plate: str = Field(min_length=3, max_length=20)
    vehicle_type: str
    capacity_kg: float = Field(gt=0)
    driver_id: int | None = None


class VehicleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    plate: str
    vehicle_type: str
    capacity_kg: float
    driver_id: int | None
    available: bool
