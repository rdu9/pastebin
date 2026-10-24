from fastapi import APIRouter, Depends, Query
from src.db.main import get_session
from .schemas import PasteCreateModel
from sqlmodel.ext.asyncio.session import AsyncSession
from .service import PasteService
from src.auth.dependencies import get_optional_user_uid,get_current_user_uid
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
    response = await pastes_service.view_paste(paste_uid, user_uid, session)
    return response


@pastes_router.post("/{paste_uid}/reveal")
async def view_reveal_paste(
    paste_uid: uuid.UUID,
    user_uid: uuid.UUID | None = Depends(get_optional_user_uid),
    session: AsyncSession = Depends(get_session),
):
    response = await pastes_service.reveal_paste(paste_uid, user_uid, session)
    return response


@pastes_router.get("/{paste_uid}/raw")
async def get_raw_paste(
    paste_uid: uuid.UUID,
    user_uid: uuid.UUID | None = Depends(get_optional_user_uid),
    session: AsyncSession = Depends(get_session),
):
    response = await pastes_service.get_raw_paste(paste_uid,user_uid,session)
    return response

@pastes_router.delete("/{paste_uid}")
async def delete_paste(
    paste_uid: uuid.UUID,
    user_uid: uuid.UUID | None = Depends(get_current_user_uid),
    session: AsyncSession = Depends(get_session)
):
    response = await pastes_service.delete(paste_uid,user_uid,session)
    return response

@pastes_router.get("/")
async def list_public_pastes(
    page: int = Query(1, ge=1),
    session: AsyncSession = Depends(get_session),
):
    response = await pastes_service.list_public_pages(page, session)
    return response

@pastes_router.get("/me/pastes")
async def get_user_pastes(
    page: int = Query(1,ge=1),
    user_uid: uuid.UUID | None = Depends(get_current_user_uid),
    session: AsyncSession = Depends(get_session)
):
    response = await pastes_service.get_user_pastes(page, user_uid,session)
    return response