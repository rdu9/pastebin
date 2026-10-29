from src.db.models import Paste, Image, ImageStatus, Visibility
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, or_
import uuid
from src.config import Config
from datetime import datetime, timezone
from .schemas import UploadUrlRequest, MAX_IMAGE_BYTES
from src.errors import NotFound
from src.storage import s3_public
from botocore.exceptions import ClientError
from src.storage import s3_internal
from starlette.concurrency import run_in_threadpool
from starlette.responses import RedirectResponse
from src.tasks import process_image

class ImageService:

    ## sevices that talk straight to garage api

    async def configure_image(
        self,
        payload: UploadUrlRequest,
        image_uid: uuid.UUID,
        object_key: str,
        paste_uid: uuid.UUID,
        session: AsyncSession,
    ):
        new_image = Image(
            uid=image_uid,
            paste_uid=paste_uid,
            object_key=object_key,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
        )

        session.add(new_image)
        await session.commit()

        post = s3_public.generate_presigned_post(
            Bucket=Config.S3_BUCKET,
            Key=object_key,
            Fields={"Content-Type": payload.content_type},
            Conditions=[
                ["content-length-range", 1, MAX_IMAGE_BYTES],
                {"Content-Type": payload.content_type},
            ],
            ExpiresIn=300,
        )

        return {
            "image_uid": str(image_uid),
            "url": post["url"],
            "fields": post["fields"],
        }

    async def confirm_and_queue(self, found_image: Image ,object_key: str, session: AsyncSession):
        try:
            head = await run_in_threadpool(
                s3_internal.head_object, Bucket=Config.S3_BUCKET, Key=object_key
            )
            found_image.size_bytes = head["ContentLength"]
            await session.commit()
            process_image.delay(str(found_image.uid))
            return {"image_uid": str(found_image.uid), "status": "processing"}
        except ClientError:
            raise NotFound("Upload not found. Upload the file first.")

    async def fetch_the_image(self, object_key: str):
        url = s3_public.generate_presigned_url(
            "get_object",
            Params = {"Bucket": Config.S3_BUCKET, "Key": object_key},
            ExpiresIn=300,
        )
        return RedirectResponse(url,status_code=302)

    ## api services

    async def create_upload(
        self, payload: UploadUrlRequest, user_uid: uuid.UUID, session: AsyncSession
    ):
        # fetch the paste

        statement = select(Paste).where(
            Paste.uid == payload.paste_uid,
            Paste.owner_uid == user_uid,
            or_(
                Paste.expires_at.is_(None),
                Paste.expires_at > datetime.now(timezone.utc),
            ),
        )
        result = await session.exec(statement)
        found_paste = result.one_or_none()
        if not found_paste:
            raise NotFound()

        # configure the image

        image_uid = uuid.uuid4()
        object_key = f"images/{payload.paste_uid}/{image_uid}"
        response = await self.configure_image(
            payload, image_uid, object_key, found_paste.uid, session
        )
        return response

    async def complete_upload(
        self, image_uid: uuid.UUID, user_uid: uuid.UUID, session: AsyncSession
    ):
        statement = select(Image).join(Paste, Paste.uid == Image.paste_uid).where(
            Image.uid == image_uid,
            Paste.owner_uid == user_uid,
            Image.status == ImageStatus.pending,
        )
        result = await session.exec(statement)
        found_image = result.one_or_none()
        if not found_image:
            raise NotFound()


        # check if the image was found inside of garage,and let it return the data / raise the error

        image_object_key = found_image.object_key

        image_in_garage = await self.confirm_and_queue(found_image,image_object_key,session)
        return image_in_garage

    async def view_image(self,image_uid: uuid.UUID, thumb: bool , user_uid: uuid.UUID | None, session: AsyncSession):

        # fetch both the image and the paste in one query, and then unpack them into 2 variables
        
        statement = (
            select(Image,Paste)
            .join(Paste, Paste.uid == Image.paste_uid)
            .where(
                Image.uid == image_uid,
                Image.status == ImageStatus.ready,
                or_(
                    Paste.expires_at.is_(None),
                    Paste.expires_at > datetime.now(timezone.utc)
                )
            )
        )

        result = await session.exec(statement)
        row = result.first()
        if not row:
            raise NotFound()
        image, paste = row

        # check if the paste and image are good

        if paste.visibility == Visibility.private and paste.owner_uid != user_uid:
            raise NotFound()

        # burn-after-reading pastes are out of this scope, because they would bypass the /reveal endpoint specifically made for them
        if paste.burn_after_reading:
            raise NotFound()

        if thumb:
            if image.thumb_key is None:
                raise NotFound()
            object_key = image.thumb_key
        else:
            object_key = image.object_key

        fetched_image = await self.fetch_the_image(object_key)
        return fetched_image
        
