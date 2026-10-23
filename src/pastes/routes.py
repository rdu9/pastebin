from fastapi import APIRouter, Depends, HTTPException, status, Response
from src.db.main import get_session
from .schemas import PasteCreateModel
from sqlmodel.ext.asyncio.session import AsyncSession
from .service import PasteService
from fastapi.responses import JSONResponse
from src.auth.dependencies import get_optional_user_uid
import uuid

pastes_router = APIRouter()
pastes_service = PasteService()


@pastes_router.post("/")
async def create_paste(
    payload: PasteCreateModel,
    user_uid: uuid.UUID | None = Depends(get_optional_user_uid),
    session: AsyncSession = Depends(get_session),
):
    response = await pastes_service.create_paste(payload, user_uid, session)
    return response


@pastes_router.get("/{paste_uid}")
async def view_paste(
    paste_uid: uuid.UUID,
    user_uid: uuid.UUID | None = Depends(get_optional_user_uid),
    session: AsyncSession = Depends(get_session),
):
    response = await pastes_service.view_paste(paste_uid,user_uid,session)
    return response


@pastes_router.post("/{paste_uid}/reveal")
async def view_reveal_paste(
    paste_uid: uuid.UUID,
    user_uid: uuid.UUID | None = Depends(get_optional_user_uid),
    session: AsyncSession = Depends(get_session)
):
    response = await pastes_service.reveal_paste(paste_uid,user_uid,session)
    return response