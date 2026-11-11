"""Shipment lifecycle as an explicit state machine (pure Python, no DB)."""
from enum import Enum

from app.core.errors import InvalidTransitionError


class Status(str, Enum):
    CREATED = "created"
    PICKED_UP = "picked_up"
    WAREHOUSE_RECEIVED = "warehouse_received"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    DELAYED = "delayed"
    FAILED_DELIVERY = "failed_delivery"
    RETURNED = "returned"


S = Status
TRANSITIONS: dict[Status, set[Status]] = {
    S.CREATED: {S.PICKED_UP},
    S.PICKED_UP: {S.WAREHOUSE_RECEIVED, S.DELAYED},
    S.WAREHOUSE_RECEIVED: {S.IN_TRANSIT, S.DELAYED},
    S.IN_TRANSIT: {S.OUT_FOR_DELIVERY, S.DELAYED},
    S.OUT_FOR_DELIVERY: {S.DELIVERED, S.FAILED_DELIVERY, S.DELAYED},
    S.DELAYED: {S.WAREHOUSE_RECEIVED, S.IN_TRANSIT, S.OUT_FOR_DELIVERY, S.RETURNED},
    S.FAILED_DELIVERY: {S.OUT_FOR_DELIVERY, S.RETURNED},  # re-attempt or return
    S.DELIVERED: set(),
    S.RETURNED: set(),
}
TERMINAL = {S.DELIVERED, S.RETURNED}
ACTIVE = [s for s in Status if s not in TERMINAL]


def validate_transition(current: Status, new: Status, failed_attempts: int = 0, max_attempts: int = 3) -> None:
    if new not in TRANSITIONS[current]:
        raise InvalidTransitionError(f"Cannot move shipment from '{current.value}' to '{new.value}'")
    # After max failed attempts the only way out of FAILED_DELIVERY is a return.
    if current == S.FAILED_DELIVERY and failed_attempts >= max_attempts and new != S.RETURNED:
        raise InvalidTransitionError(f"{failed_attempts} failed attempts reached: shipment must be returned")
