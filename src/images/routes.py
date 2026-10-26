from fastapi import APIRouter, Depends, Query
from src.db.main import get_session
from .schemas import UploadUrlRequest
from sqlmodel.ext.asyncio.session import AsyncSession
from .service import ImageService
from src.auth.dependencies import get_optional_user_uid, get_current_user_uid
import uuid
from src.ratelimit import images_upload_ratelimit

image_route = APIRouter()
image_service = ImageService()


@image_route.post("/upload-url", dependencies=[Depends(images_upload_ratelimit)])
async def upload_image(
    payload: UploadUrlRequest,
    user_uid=Depends(get_current_user_uid),
    session: AsyncSession = Depends(get_session),
):
    result = await image_service.create_upload(payload,user_uid,session)
    return result