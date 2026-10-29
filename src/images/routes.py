from fastapi import APIRouter, Depends
from src.db.main import get_session
from .schemas import UploadUrlRequest
from sqlmodel.ext.asyncio.session import AsyncSession
from .service import ImageService
from src.auth.dependencies import get_optional_user_uid, get_current_user_uid
import uuid
from src.ratelimit import images_upload_ratelimit

image_route = APIRouter()
image_view_route = APIRouter()
image_service = ImageService()


@image_route.post("/upload-url", dependencies=[Depends(images_upload_ratelimit)])
async def upload_image(
    payload: UploadUrlRequest,
    user_uid=Depends(get_current_user_uid),
    session: AsyncSession = Depends(get_session),
):
    result = await image_service.create_upload(payload,user_uid,session)
    return result

@image_route.post("/{image_uid}/complete")
async def complete_image_upload(
    image_uid: uuid.UUID,
    user_uid: uuid.UUID = Depends(get_current_user_uid),
    session: AsyncSession = Depends(get_session)
):
    result = await image_service.complete_upload(image_uid,user_uid,session)
    return result

@image_view_route.get("/i/{image_uid}")
async def view_image(
    image_uid: uuid.UUID,
    thumb: bool = False,
    user_uid: uuid.UUID = Depends(get_optional_user_uid),
    session: AsyncSession = Depends(get_session)
):
    result = await image_service.view_image(image_uid,thumb,user_uid,session)
    return result
