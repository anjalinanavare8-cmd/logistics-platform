from decimal import Decimal

import pytest

from app.core.errors import AppError, InvalidTransitionError
from app.domain.pricing import calculate_price, chargeable_weight
from app.domain.tracking import TERMINAL, TRANSITIONS, Status, validate_transition


def test_happy_path_lifecycle():
    path = [Status.CREATED, Status.PICKED_UP, Status.WAREHOUSE_RECEIVED, Status.IN_TRANSIT,
            Status.OUT_FOR_DELIVERY, Status.DELIVERED]
    for a, b in zip(path, path[1:]):
        validate_transition(a, b)


def test_cannot_skip_steps():
    with pytest.raises(InvalidTransitionError):
        validate_transition(Status.CREATED, Status.DELIVERED)


def test_terminal_states_are_final():
    for t in TERMINAL:
        assert TRANSITIONS[t] == set()


def test_failed_delivery_allows_reattempt_until_limit():
    validate_transition(Status.FAILED_DELIVERY, Status.OUT_FOR_DELIVERY, failed_attempts=2, max_attempts=3)
    with pytest.raises(InvalidTransitionError):
        validate_transition(Status.FAILED_DELIVERY, Status.OUT_FOR_DELIVERY, failed_attempts=3, max_attempts=3)
    validate_transition(Status.FAILED_DELIVERY, Status.RETURNED, failed_attempts=3, max_attempts=3)


def test_price_standard_parcel():
    q = calculate_price(10, 10, 10, 10, 100, "standard", tax_rate=0.18)
    # base 5 + weight 10*1.20=12 + distance 100*0.15=15 = 32.00; tax 5.76; total 37.76
    assert (q.subtotal, q.tax, q.total) == (Decimal("32.00"), Decimal("5.76"), Decimal("37.76"))


def test_volumetric_weight_wins_for_bulky_light_parcel():
    assert chargeable_weight(1, 50, 50, 50) == Decimal("25")  # 125000 / 5000


def test_priority_extras_and_discount():
    q = calculate_price(10, 10, 10, 10, 100, "express", ("insurance", "fragile"), discount_pct=10, tax_rate=0)
    # pre=32.00, express +50% = 16.00, extras 5.50 -> gross 53.50, 10% off = 5.35 -> 48.15
    assert q.priority_charge == Decimal("16.00") and q.extras == Decimal("5.50")
    assert q.discount == Decimal("5.35") and q.total == Decimal("48.15")


def test_invalid_inputs_rejected():
    with pytest.raises(AppError):
        calculate_price(1, 1, 1, 1, 1, "overnight")
    with pytest.raises(AppError):
        calculate_price(1, 1, 1, 1, 1, "standard", ("teleport",))
