from sqlalchemy.exc import OperationalError

from app.db.session import SessionLocal
from app.services import notifications, sla
from app.tasks.celery_app import celery_app

RETRY = dict(autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=300, retry_jitter=True, max_retries=5)


@celery_app.task(**RETRY)
def send_notification(event: str, tracking_number: str, recipient: str, message: str) -> None:
    notifications.deliver(event, tracking_number, recipient, message)


@celery_app.task(autoretry_for=(OperationalError,), retry_backoff=True, max_retries=3)
def sla_check() -> int:
    with SessionLocal() as db:
        return sla.detect_sla_breaches(db)


@celery_app.task(autoretry_for=(OperationalError,), retry_backoff=True, max_retries=3)
def escalate() -> int:
    with SessionLocal() as db:
        return sla.escalate_exceptions(db)
