from celery import Celery

from app.core.config import get_settings

celery_app = Celery("logistics", broker=get_settings().redis_url, backend=get_settings().redis_url,
                    include=["app.tasks.jobs"])
celery_app.conf.update(
    task_publish_retry_policy={"max_retries": 1, "interval_start": 0, "interval_max": 0.2},  # fail fast if broker is down
    task_acks_late=True,            # a crashed worker's task is redelivered
    task_reject_on_worker_lost=True,
    beat_schedule={
        "sla-breach-check": {"task": "app.tasks.jobs.sla_check", "schedule": 300.0},
        "escalate-exceptions": {"task": "app.tasks.jobs.escalate", "schedule": 900.0},
    },
)
