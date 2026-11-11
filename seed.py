import random
from app.main import app          # makes sure tables exist
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import User, Warehouse, Vehicle, Status as S
from app.services import shipments as svc, tracking

db = SessionLocal()

def get_user(email, role):
    u = db.query(User).filter_by(email=email).first()
    if not u:
        u = User(email=email, hashed_password=hash_password("Pass@1234"), role=role)
        db.add(u); db.flush()
    return u

get_user("admin@x.com", "admin")
disp = get_user("disp@x.com", "dispatcher")
get_user("wm@x.com", "warehouse_manager")
get_user("ops@x.com", "ops_manager")
drivers = [get_user(f"driver{i}@x.com", "driver") for i in (1, 2, 3)]

warehouses = []
for name, city in [("Pune Hub", "Pune"), ("Mumbai Hub", "Mumbai")]:
    w = db.query(Warehouse).filter_by(name=name).first()
    if not w:
        w = Warehouse(name=name, city=city, capacity=100); db.add(w); db.flush()
    warehouses.append(w)

for plate, typ, cap in [("MH12AB1001", "van", 800), ("MH12AB1002", "truck", 5000)]:
    if not db.query(Vehicle).filter_by(plate=plate).first():
        db.add(Vehicle(plate=plate, vehicle_type=typ, capacity_kg=cap))

path = [S.PICKED_UP, S.WAREHOUSE_RECEIVED, S.IN_TRANSIT, S.OUT_FOR_DELIVERY, S.DELIVERED]
for i in range(30):
    sh, created = svc.create_shipment(db, {
        "sender_name": f"Sender {i}", "receiver_name": f"Receiver {i}",
        "receiver_address": f"{i+1} MG Road, Pune",
        "weight_kg": random.randint(1, 40), "distance_km": random.randint(5, 600),
        "priority": random.choice(["standard", "express", "overnight"]),
        "category": random.choice(["general", "electronics", "fragile", "documents"]),
        "services": []}, disp.id, f"seed-{i}")
    if not created:
        continue
    sh.driver_id = random.choice(drivers).id
    sh.warehouse_id = random.choice(warehouses).id
    for st in path[:random.randint(0, 5)]:
        tracking.transition(db, sh, st)
    if sh.status == S.OUT_FOR_DELIVERY.value and random.random() < 0.3:
        tracking.transition(db, sh, S.FAILED_DELIVERY, "Customer not available")

db.commit()
print("Sample data ready. All users have password Pass@1234")