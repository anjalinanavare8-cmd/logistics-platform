"""python -m scripts.seed  -> creates tables, one user per role, 2 warehouses, a few vehicles."""
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models import User, Vehicle, Warehouse
import app.models  # noqa

USERS = [("admin@demo.io", "Ada Admin", "admin"), ("ops@demo.io", "Omar Ops", "ops_manager"),
         ("wh@demo.io", "Wendy Warehouse", "warehouse_manager"), ("dispatch@demo.io", "Dee Dispatcher", "dispatcher"),
         ("driver1@demo.io", "Dan Driver", "driver"), ("driver2@demo.io", "Dora Driver", "driver")]

Base.metadata.create_all(engine)
with SessionLocal() as db:
    if not db.execute(select(User)).first():
        for email, name, role in USERS:
            db.add(User(email=email, full_name=name, role=role, password_hash=hash_password("Passw0rd!")))
        db.add_all([Warehouse(name="Central Hub", city="Mumbai", capacity=5000, current_load=1200),
                    Warehouse(name="North Depot", city="Delhi", capacity=2000, current_load=1900)])
        db.flush()
        db.add_all([Vehicle(plate="MH01AB1234", vehicle_type="van", capacity_kg=1200),
                    Vehicle(plate="DL02CD5678", vehicle_type="truck", capacity_kg=8000)])
        db.commit()
        print("seeded (password for all demo users: Passw0rd!)")
    else:
        print("already seeded")
