from src.db.models import LoginSession
from fastapi import Request, Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from datetime import datetime, timezone
from sqlmodel import select
from .security import (
    generate_hashed_token,
)
from starlette.concurrency import run_in_threadpool
from src.errors import NotAuthenticated
from src.db.main import get_session


async def get_current_user_uid(
    request: Request, session: AsyncSession = Depends(get_session)
):

    token = request.cookies.get("session")
    if not token:
        raise NotAuthenticated()

    token_hash = await run_in_threadpool(generate_hashed_token, token)


    statement = select(LoginSession.user_uid).where(
        LoginSession.token_hash == token_hash,
        LoginSession.expires_at > datetime.now(timezone.utc),
    )
    result = await session.exec(statement)
    user_uid = result.one_or_none()
    if not user_uid:
        raise NotAuthenticated()

    return user_uid


# same as the current user, but is now optional and returns none
async def get_optional_user_uid(
    request: Request, session: AsyncSession = Depends(get_session)
):

    token = request.cookies.get("session")
    if not token:
        return None

    token_hash = await run_in_threadpool(generate_hashed_token, token)

    statement = select(LoginSession.user_uid).where(
        LoginSession.token_hash == token_hash,
        LoginSession.expires_at > datetime.now(timezone.utc),
    )

    result = await session.exec(statement)
    user_uid = result.one_or_none()
    if not user_uid:
        return None

    return user_uid
