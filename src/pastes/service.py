from src.db.models import Paste, Visibility
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, or_
import uuid
from datetime import datetime, timedelta, timezone
from .schemas import PasteCreateModel
from starlette.concurrency import run_in_threadpool
from src.errors import NotFound, Forbidden, TooLarge

MAX_PASTE_BYTES = 512 * 1024

EXPIRY_DURATIONS = {
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
    "1w": timedelta(weeks=1),
}


def calculate_expires_in(expires_in: str) -> datetime | None:
    if expires_in == "never":
        return None
    return datetime.now(timezone.utc) + EXPIRY_DURATIONS[expires_in]


class PasteService:

    async def create_paste(
        self,
        payload: PasteCreateModel,
        user_uid: uuid.UUID | None,
        session: AsyncSession,
    ):

        # private + anonymousity = not allowed

        if user_uid is None and payload.visibility == Visibility.private:
            raise Forbidden("Log in to create private pastes.")

        # compute the bytes

        size_bytes = len(payload.content.encode("utf-8"))
        if size_bytes > MAX_PASTE_BYTES:
            raise TooLarge("Paste is larger than 512 KB.")

        computed_expires_at = calculate_expires_in(payload.expires_in)

        new_paste = Paste(
            owner_uid=user_uid,
            title=payload.title,
            content=payload.content,
            language=payload.language,
            visibility=payload.visibility,
            burn_after_reading=payload.burn_after_reading,
            size_bytes=size_bytes,
            expires_at=computed_expires_at,
        )

        session.add(new_paste)
        await session.commit()
        await session.refresh(new_paste)
        return new_paste

    async def view_paste(
        self, paste_uid: uuid.UUID, user_uid: uuid.UUID | None, session: AsyncSession
    ):

        # fetch the paste object before anything, and check burn after expiry

        statement = select(Paste).where(
            Paste.uid == paste_uid,
            or_(
                Paste.expires_at.is_(None),
                Paste.expires_at > datetime.now(timezone.utc),
            ),
        )
        result = await session.exec(statement)
        response_paste = result.one_or_none()
        if not response_paste:
            raise NotFound()

        # check the visibility

        if (
            response_paste.visibility == Visibility.private
            and response_paste.owner_uid != user_uid
        ):
            raise NotFound()

        if response_paste.burn_after_reading:
            response_paste.content = None

        return response_paste

    async def reveal_paste(
        self, paste_uid: uuid.UUID, user_uid: uuid.UUID | None, session: AsyncSession
    ):

        # fetch the burn-after-reading paste

        statement = select(Paste).where(
            Paste.uid == paste_uid,
            Paste.burn_after_reading == True,
            or_(
                Paste.expires_at.is_(None),
                Paste.expires_at > datetime.now(timezone.utc),
            ),
        ).with_for_update()
        result = await session.exec(statement)
        response_paste = result.one_or_none()
        if not response_paste:
            raise NotFound()

        # check the visibility

        if (
            response_paste.visibility == Visibility.private
            and response_paste.owner_uid != user_uid
        ):
            raise NotFound()

        # delete the paste

        await session.delete(response_paste)
        await session.commit()

        return response_paste
