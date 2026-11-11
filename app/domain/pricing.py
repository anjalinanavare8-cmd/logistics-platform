"""Pricing engine (pure Python, Decimal money math)."""
from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.core.errors import AppError

BASE_FEE = Decimal("5.00")
PER_KG = Decimal("1.20")
PER_KM = Decimal("0.15")
VOLUMETRIC_DIVISOR = Decimal("5000")  # cm^3 per kg, industry standard
PRIORITY_MULTIPLIER = {"express": Decimal("0.50"), "standard": Decimal("0"), "economy": Decimal("-0.10")}
EXTRAS = {"insurance": Decimal("3.00"), "signature": Decimal("1.50"), "fragile": Decimal("2.50")}
SLA_HOURS = {"express": 24, "standard": 72, "economy": 120}


def _q(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Quote:
    chargeable_weight_kg: Decimal
    base: Decimal
    weight_charge: Decimal
    distance_charge: Decimal
    priority_charge: Decimal
    extras: Decimal
    discount: Decimal
    subtotal: Decimal
    tax: Decimal
    total: Decimal

    def as_dict(self) -> dict:
        return asdict(self)


def chargeable_weight(weight_kg, length_cm, width_cm, height_cm) -> Decimal:
    actual = Decimal(str(weight_kg))
    volumetric = Decimal(str(length_cm)) * Decimal(str(width_cm)) * Decimal(str(height_cm)) / VOLUMETRIC_DIVISOR
    return max(actual, volumetric)


def calculate_price(weight_kg, length_cm, width_cm, height_cm, distance_km, priority: str,
                    extras: tuple[str, ...] = (), discount_pct=0, tax_rate=0.18) -> Quote:
    if priority not in PRIORITY_MULTIPLIER:
        raise AppError(f"Unknown priority '{priority}'")
    unknown = [e for e in extras if e not in EXTRAS]
    if unknown:
        raise AppError(f"Unknown additional services: {unknown}")
    if not 0 <= Decimal(str(discount_pct)) <= 100:
        raise AppError("discount_pct must be between 0 and 100")

    cw = chargeable_weight(weight_kg, length_cm, width_cm, height_cm)
    weight_charge = _q(cw * PER_KG)
    distance_charge = _q(Decimal(str(distance_km)) * PER_KM)
    pre_priority = BASE_FEE + weight_charge + distance_charge
    priority_charge = _q(pre_priority * PRIORITY_MULTIPLIER[priority])
    extras_total = _q(sum((EXTRAS[e] for e in extras), Decimal("0")))
    gross = pre_priority + priority_charge + extras_total
    discount = _q(gross * Decimal(str(discount_pct)) / 100)
    subtotal = _q(gross - discount)
    tax = _q(subtotal * Decimal(str(tax_rate)))
    return Quote(_q(cw), BASE_FEE, weight_charge, distance_charge, priority_charge,
                 extras_total, discount, subtotal, tax, _q(subtotal + tax))
