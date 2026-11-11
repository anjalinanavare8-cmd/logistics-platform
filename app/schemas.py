from decimal import Decimal
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class Page(BaseModel):
    items: list
    total: int
    page: int
    size: int

class UserCreate(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8)
    role: Literal["admin", "ops_manager", "warehouse_manager", "dispatcher", "driver"] = "driver"

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class ShipmentCreate(BaseModel):
    sender_name: str = Field(min_length=1, max_length=120)
    receiver_name: str = Field(min_length=1, max_length=120)
    receiver_address: str = Field(min_length=5, max_length=255)
    weight_kg: Decimal = Field(gt=0, le=1000)
    distance_km: Decimal = Field(ge=0, le=20000)
    priority: Literal["standard", "express", "overnight"] = "standard"
    category: str = "general"
    services: list[Literal["insurance", "signature", "fragile"]] = []

class ShipmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tracking_no: str
    status: str
    priority: str
    category: str
    receiver_name: str
    sla_due_at: datetime

class StatusUpdate(BaseModel):
    status: str
    note: str = ""
    version: int | None = None

class WarehouseCreate(BaseModel):
    name: str
    city: str
    capacity: int = Field(gt=0)

class VehicleCreate(BaseModel):
    plate: str
    vehicle_type: str
    capacity_kg: int = Field(gt=0)
