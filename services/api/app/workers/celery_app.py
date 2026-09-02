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
    worker_concurrency=2,
    worker_max_tasks_per_child=50,
    task_default_retry_delay=20,
    task_soft_time_limit=270,
    task_time_limit=300,
    task_reject_on_worker_lost=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_routes={"app.workers.tasks.*": {"queue": "ingestion"}},
    imports=["app.workers.tasks"],
)
