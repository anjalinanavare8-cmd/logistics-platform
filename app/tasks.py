"""Celery wiring. Run: celery -A app.tasks worker -B"""
from celery import Celery
from .core.config import settings
import os

celery = Celery("logistics", broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"))
celery.conf.beat_schedule = {"sla-scan": {"task": "sla_scan", "schedule": 300.0}}


@celery.task(name="sla_scan", autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def sla_scan():
    from .core.db import SessionLocal
    from .services.sla import detect_sla_breaches
    db = SessionLocal()
    try:
        n = detect_sla_breaches(db); db.commit(); return n
    except Exception:
        db.rollback(); raise
    finally:
        db.close()
