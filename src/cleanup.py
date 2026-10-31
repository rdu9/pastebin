from datetime import datetime, timezone

import structlog
from sqlalchemy import delete
from sqlmodel import select

from src.config import Config
from src.db.models import Image, Paste
from src.storage import s3_internal
from src.sync import get_sync_session

logger = structlog.get_logger()

BATCH_SIZE = 500 


def delete_expired_batch(session) -> int:

    # fetch the uids of expired pastes

    statement = (
        select(Paste.uid)
        .where(Paste.expires_at <= datetime.now(timezone.utc))
        .limit(BATCH_SIZE)
    )
    found_pastes_uids = session.exec(statement).all()
    if not found_pastes_uids:
        return 0

    # fetch the image keys 

    statement = select(Image.object_key, Image.thumb_key).where(
        Image.paste_uid.in_(found_pastes_uids)
    )
    found_images = session.exec(statement).all()

    # delete the paste rows

    session.execute(delete(Paste).where(Paste.uid.in_(found_pastes_uids)))
    session.commit()

    # delete the objects stored in garage

    for object_key, thumb_key in found_images:
        s3_internal.delete_object(Bucket=Config.S3_BUCKET, Key=object_key)
        if thumb_key is not None:
            s3_internal.delete_object(Bucket=Config.S3_BUCKET, Key=thumb_key)

    # return the len to calculate the total
    
    return len(found_pastes_uids)


def main():
    total = 0
    with get_sync_session() as session:
        while True:
            deleted = delete_expired_batch(session)
            if deleted == 0:
                break
            total += deleted

    logger.info("cleanup.done", deleted=total)


if __name__ == "__main__":
    main()
