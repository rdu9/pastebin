from src.db.models import Paste, Image, ImageStatus
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, or_
import uuid
from src.config import Config
from datetime import datetime, timezone
from .schemas import UploadUrlRequest, MAX_IMAGE_BYTES
from src.errors import NotFound
from src.storage import s3_public


class ImageService:

    async def configure_image(self,payload: UploadUrlRequest,image_uid: uuid.UUID, object_key: str,paste_uid: uuid.UUID,session: AsyncSession):
        new_image = Image(
            uid=image_uid,
            paste_uid=paste_uid,
            object_key=object_key,
            content_type= payload.content_type,
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

        return {"image_uid": str(image_uid), "url": post["url"], "fields": post["fields"]}
    


    async def create_upload(
        self,payload: UploadUrlRequest, user_uid: uuid.UUID, session: AsyncSession
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
        response = await self.configure_image(payload,image_uid,object_key,found_paste.uid,session)
        return response


