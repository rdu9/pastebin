from src.celery import celery_app

@celery_app.task
def ping() -> str:
    return "ping"