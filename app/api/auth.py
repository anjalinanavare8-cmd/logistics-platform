from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..core.db import get_db
from ..core.security import hash_password, verify_password, create_token
from ..models import User, Role
from ..schemas import UserCreate, Token
from .deps import require_roles, audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/users", status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db),
                admin: User = Depends(require_roles(Role.ADMIN))):
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(409, "Email already registered")
    u = User(email=body.email, hashed_password=hash_password(body.password), role=body.role)
    db.add(u); db.flush()
    audit(db, admin, "create", "user", f"id={u.id} role={u.role}")
    return {"id": u.id, "email": u.email, "role": u.role}


@router.post("/login", response_model=Token)
def login(body: dict, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.get("email")))
    if not u or not verify_password(body.get("password", ""), u.hashed_password):
        raise HTTPException(401, "Invalid credentials")
    return Token(access_token=create_token(u.id, u.role))
