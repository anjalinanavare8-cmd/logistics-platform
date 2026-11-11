from sqlalchemy.orm import Session

from app.models import AuditLog


def audit(db: Session, user_id: int | None, action: str, resource: str, resource_id=None, detail: str | None = None) -> None:
    """Adds an audit row to the CURRENT transaction, so it commits or rolls back with the business change."""
    db.add(AuditLog(user_id=user_id, action=action, resource=resource,
                    resource_id=str(resource_id) if resource_id is not None else None, detail=detail))
