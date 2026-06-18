from celery import Celery

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery(
    "ciet_ai",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_retry_delay=20,
    task_routes={"app.workers.tasks.*": {"queue": "ingestion"}},
)
