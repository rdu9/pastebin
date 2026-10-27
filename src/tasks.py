from src.celery import celery_app
from src.sync import get_sync_session
from src.db.models import Paste
from sqlmodel import select

## test tasks


@celery_app.task
def ping() -> str:
    return "ping"

@celery_app.task
def count_pastes() -> int:
    with get_sync_session() as session:
        return len(session.exec(select(Paste)).all())