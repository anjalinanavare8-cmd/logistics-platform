import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from ..core.db import get_db
from ..core.security import decode_token
from ..models import User, AuditLog, Role

bearer = HTTPBearer(auto_error=False)


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer),
                 db: Session = Depends(get_db)) -> User:
    if not cred:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = decode_token(cred.credentials)
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(401, "User inactive")
    return user


def require_roles(*roles: Role):
    allowed = {r.value for r in roles} | {Role.ADMIN.value}
    def checker(user: User = Depends(current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(403, "Insufficient permissions")
        return user
    return checker


def audit(db: Session, user: User | None, action: str, resource: str, detail: str = ""):
    db.add(AuditLog(user_id=user.id if user else None, action=action,
                    resource=resource, detail=detail))
