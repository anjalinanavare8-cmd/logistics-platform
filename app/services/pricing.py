"""Pricing engine. Pure functions + Decimal => deterministic and easy to test."""
from decimal import Decimal as D, ROUND_HALF_UP

BASE = D("5.00")
PER_KG = D("0.80")
PER_KM = D("0.12")
PRIORITY_MULT = {"standard": D("0"), "express": D("0.25"), "overnight": D("0.50")}
SERVICES = {"insurance": D("3.00"), "signature": D("1.50"), "fragile": D("4.00")}
TAX_RATE = D("0.18")


def q(x: D) -> D:
    return x.quantize(D("0.01"), rounding=ROUND_HALF_UP)


def calculate(weight_kg, distance_km, priority="standard", services=(), discount_pct=0):
    weight_kg, distance_km = D(str(weight_kg)), D(str(distance_km))
    core = BASE + weight_kg * PER_KG + distance_km * PER_KM
    priority_fee = core * PRIORITY_MULT[priority]
    extras = sum((SERVICES[s] for s in services), D("0"))
    subtotal = core + priority_fee + extras
    discount = subtotal * D(str(discount_pct)) / 100
    taxable = subtotal - discount
    tax = taxable * TAX_RATE
    return {k: q(v) for k, v in {
        "base": BASE, "weight_charge": weight_kg * PER_KG,
        "distance_charge": distance_km * PER_KM, "priority_charge": priority_fee,
        "additional_services": extras, "subtotal": subtotal,
        "discount": discount, "tax": tax, "total": taxable + tax}.items()}
