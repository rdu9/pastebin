from src.db.models import Paste, Visibility, Image
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, or_
import uuid
from datetime import datetime, timedelta, timezone
from .schemas import PasteCreateModel
from src.errors import NotFound, Forbidden, TooLarge
from fastapi.responses import PlainTextResponse
from starlette.concurrency import run_in_threadpool
from src.storage import s3_internal
from src.config import Config

# define global variables
MAX_PASTE_BYTES = 512 * 1024
PAGE_SIZE = 20

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

    async def delete_with_images(self, paste: Paste, session: AsyncSession):
        keys = (
            await session.exec(
                select(Image.object_key).where(Image.paste_uid == paste.uid)
            )
        ).all()
        await session.delete(paste)
        await session.commit()
        for key in keys:
            await run_in_threadpool(
                s3_internal.delete_object, Bucket=Config.S3_BUCKET, Key=key
            )

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

        statement = (
            select(Paste)
            .where(
                Paste.uid == paste_uid,
                Paste.burn_after_reading == True,
                or_(
                    Paste.expires_at.is_(None),
                    Paste.expires_at > datetime.now(timezone.utc),
                ),
            )
            .with_for_update()
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

        # delete the paste

        await self.delete_with_images(response_paste,session)

        return response_paste

    async def get_raw_paste(
        self, paste_uid: uuid.UUID, user_uid: uuid.UUID | None, session: AsyncSession
    ):

        # reuse the view paste function. all the checks are the same, but if burn-after-reading is enabled, raw content is not available

        response_paste = await self.view_paste(paste_uid, user_uid, session)
        if response_paste.burn_after_reading:
            raise Forbidden("Burn-after-reading paste. Use /reveal to see the content.")

        return PlainTextResponse(
            response_paste.content,
            headers={"X-Content-Type-Options": "nosniff"},
        )

    # user must be logged in here, in order to delete any paste
    async def delete_paste(
        self, paste_uid: uuid.UUID, user_uid: uuid.UUID, session: AsyncSession
    ):
        statement = select(Paste).where(
            Paste.uid == paste_uid, Paste.owner_uid == user_uid
        )
        result = await session.exec(statement)
        paste_to_delete = result.one_or_none()
        if not paste_to_delete:
            raise NotFound()

        response = await self.delete_with_images(paste_to_delete,session)

        return {}

    async def list_public_pages(self, page: int, session: AsyncSession):

        statement = (
            select(
                Paste.uid,
                Paste.title,
                Paste.language,
                Paste.created_at,
                Paste.size_bytes,
            )
            .where(
                Paste.visibility == Visibility.public,
                or_(
                    Paste.expires_at.is_(None),
                    Paste.expires_at > datetime.now(timezone.utc),
                ),
            )
            .order_by(Paste.created_at.desc())
            .offset((page - 1) * PAGE_SIZE)
            .limit(PAGE_SIZE)
        )
        result = await session.exec(statement)
        pastes = result.all()

        return [
            {
                "uid": paste.uid,
                "title": paste.title,
                "language": paste.language,
                "created_at": paste.created_at,
                "size_bytes": paste.size_bytes,
            }
            for paste in pastes
        ]

    async def get_user_pastes(
        self, page: int, user_uid: uuid.UUID, session: AsyncSession
    ):

        statement = (
            select(
                Paste.uid,
                Paste.title,
                Paste.language,
                Paste.created_at,
                Paste.size_bytes,
                Paste.visibility,
                Paste.expires_at,
            )
            .where(
                Paste.owner_uid == user_uid,
                or_(
                    Paste.expires_at.is_(None),
                    Paste.expires_at > datetime.now(timezone.utc),
                ),
            )
            .order_by(Paste.created_at.desc())
            .offset((page - 1) * PAGE_SIZE)
            .limit(PAGE_SIZE)
        )

        result = await session.exec(statement)
        pastes = result.all()

        return [
            {
                "uid": paste.uid,
                "title": paste.title,
                "language": paste.language,
                "created_at": paste.created_at,
                "size_bytes": paste.size_bytes,
            }
            for paste in pastes
        ]
