from src.celery import celery_app
from src.sync import get_sync_session
from src.db.models import Image, ImageStatus
from sqlmodel import select
from io import BytesIO
from PIL import Image as PILImage, ImageOps, UnidentifiedImageError
from botocore.exceptions import EndpointConnectionError
from src.config import Config
from src.storage import s3_internal
import structlog

logger = structlog.get_logger()


PILImage.MAX_IMAGE_PIXELS = 40_000_000
PIL_FORMATS = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
    "GIF": "image/gif",
}

## test tasks


@celery_app.task
def ping() -> str:
    return "pong"


## real app tasks


@celery_app.task(
    autoretry_for=(EndpointConnectionError,), retry_backoff=True, max_retries=5
)
def process_image(image_uid: str) -> None:

    # set up the sync session
    with get_sync_session() as session:

        # fetch the image from the database and the original from garage

        statement = select(Image).where(Image.uid == image_uid)
        result = session.exec(statement)
        found_image = result.one_or_none()
        if not found_image:
            logger.warning("process_image.not_found", image_uid=image_uid)
            return

        if found_image.thumb_key is not None:
            logger.info("process_image.already_done", image_uid=image_uid)
            return

        if found_image.status == ImageStatus.failed:
            logger.info("process_image.already_failed", image_uid=image_uid)
            return

        original_image = s3_internal.get_object(
            Bucket=Config.S3_BUCKET, Key=found_image.object_key
        )["Body"].read()

        # the actual processing

        try:
            img = PILImage.open(BytesIO(original_image))
            pil_format = img.format

            # check if the real image format matches what the user provided
            if PIL_FORMATS.get(pil_format) != found_image.content_type:
                raise UnidentifiedImageError("Wrong image format provided.")

            img = ImageOps.exif_transpose(img)

            if pil_format == "GIF":
                cleaned = original_image
            else:
                out = BytesIO()
                img.save(out, format=pil_format)
                cleaned = out.getvalue()

            thumbnail = img.copy()
            thumbnail.thumbnail((400, 400))
            thumbnail_out = BytesIO()
            thumbnail.convert("RGBA").save(thumbnail_out, format="WEBP", quality=80)

        except (UnidentifiedImageError, PILImage.DecompressionBombError, OSError) as e:
            logger.error("process_image.failed", image_uid=image_uid, error=repr(e))
            found_image.status = ImageStatus.failed
            session.commit()
            return

        # upload the original / thumbnail

        s3_internal.put_object(
            Bucket=Config.S3_BUCKET,
            Key=found_image.object_key,
            Body=cleaned,
            ContentType=found_image.content_type,
        )

        thumb_key = f"{found_image.object_key}_thumb.webp"

        s3_internal.put_object(
            Bucket=Config.S3_BUCKET,
            Key=thumb_key,
            Body=thumbnail_out.getvalue(),
            ContentType="image/webp",
        )

        # update and commit

        found_image.thumb_key = thumb_key
        found_image.size_bytes = len(cleaned)
        found_image.status = ImageStatus.ready
        session.commit()
