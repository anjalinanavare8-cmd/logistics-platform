from app.main import app
from app.core.db import SessionLocal
from app.models import User
from app.core.security import hash_password

db = SessionLocal()
db.add(User(email="admin@x.com", hashed_password=hash_password("Admin@1234"), role="admin"))
db.commit()
print("Admin created")