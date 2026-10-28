from celery import Celery
from src.config import Config

celery_app = Celery(
    "pastebin",
    broker=Config.CELERY_URL,
    backend=Config.CELERY_URL,
    include=["src.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_redirect_stdouts=False,
)