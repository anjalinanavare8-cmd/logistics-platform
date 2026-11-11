from decimal import Decimal as D
from app.services import pricing
from app.services.tracking import can_transition
from app.models import Status as S


def test_pricing_standard():
    p = pricing.calculate(10, 100)          # 5 + 8 + 12 = 25 ; tax 4.50
    assert p["subtotal"] == D("25.00") and p["tax"] == D("4.50") and p["total"] == D("29.50")


def test_pricing_priority_services_discount():
    p = pricing.calculate(10, 100, "express", ["insurance"], discount_pct=10)
    assert p["priority_charge"] == D("6.25")
    assert p["subtotal"] == D("34.25")
    assert p["discount"] == D("3.43")


def test_happy_path_transitions():
    path = [S.CREATED, S.PICKED_UP, S.WAREHOUSE_RECEIVED, S.IN_TRANSIT,
            S.OUT_FOR_DELIVERY, S.DELIVERED]
    assert all(can_transition(a, b) for a, b in zip(path, path[1:]))


def test_illegal_transitions():
    assert not can_transition(S.CREATED, S.DELIVERED)
    assert not can_transition(S.DELIVERED, S.IN_TRANSIT)
    assert can_transition(S.FAILED_DELIVERY, S.OUT_FOR_DELIVERY)   # re-attempt
