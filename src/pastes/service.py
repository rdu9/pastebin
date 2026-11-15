from src.db.models import Paste, Visibility, Image, ImageStatus, PasteRevision
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, or_
import uuid
from datetime import datetime, timedelta, timezone
from .schemas import PasteCreateModel, PasteUpdateModel, RevisionVisibilityModel
from src.errors import NotFound, Forbidden, TooLarge
from fastapi.responses import PlainTextResponse
from starlette.concurrency import run_in_threadpool
from src.storage import s3_internal
from src.config import Config
from src.db.redis import record_view
from sqlalchemy import func

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
        rows = (
            await session.exec(
                select(Image.object_key, Image.thumb_key).where(
                    Image.paste_uid == paste.uid
                )
            )
        ).all()
        await session.delete(paste)
        await session.commit()
        for row in rows:
            await run_in_threadpool(
                s3_internal.delete_object, Bucket=Config.S3_BUCKET, Key=row.object_key
            )
            if row.thumb_key is not None:
                await run_in_threadpool(
                    s3_internal.delete_object,
                    Bucket=Config.S3_BUCKET,
                    Key=row.thumb_key,
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

    async def get_viewable_paste(
        self,
        paste_uid: uuid.UUID,
        user_uid: uuid.UUID | None,
        session: AsyncSession,
    ):
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

        if (
            response_paste.visibility == Visibility.private
            and response_paste.owner_uid != user_uid
        ):
            raise NotFound()

        return response_paste

    async def view_paste(
        self,
        paste_uid: uuid.UUID,
        user_uid: uuid.UUID | None,
        viewer: str,
        session: AsyncSession,
    ):
        response_paste = await self.get_viewable_paste(paste_uid, user_uid, session)

        if response_paste.burn_after_reading:
            response_paste.content = None

        is_owner = user_uid is not None and response_paste.owner_uid == user_uid
        if not response_paste.burn_after_reading and not is_owner:
            await record_view(response_paste, viewer)

        return response_paste

    async def view_paste_with_images(
        self,
        paste_uid: uuid.UUID,
        user_uid: uuid.UUID | None,
        viewer: str | None,
        session: AsyncSession,
    ):

        paste = await self.view_paste(paste_uid, user_uid, viewer, session)

        if paste.burn_after_reading:
            image_uids = []
        else:
            image_uids = (
                await session.exec(
                    select(Image.uid).where(
                        Image.paste_uid == paste_uid, Image.status == ImageStatus.ready
                    )
                )
            ).all()

        return {**paste.model_dump(), "images": [str(uid) for uid in image_uids]}

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

        await self.delete_with_images(response_paste, session)

        return response_paste

    async def get_raw_paste(
        self, paste_uid: uuid.UUID, user_uid: uuid.UUID | None, session: AsyncSession
    ):

        # reuse the view paste function. all the checks are the same, but if burn-after-reading is enabled, raw content is not available

        response_paste = await self.view_paste(
            paste_uid=paste_uid, user_uid=user_uid, viewer=None, session=session
        )
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

        await self.delete_with_images(paste_to_delete, session)

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

    async def search_pastes(self, q: str, page: int, session: AsyncSession):

        query = func.websearch_to_tsquery("simple", q)

        statement = (
            select(
                Paste.uid,
                Paste.title,
                Paste.language,
                Paste.created_at,
                Paste.size_bytes,
            )
            .where(
                Paste.search_vector.op("@@")(query),
                Paste.visibility == Visibility.public,
                Paste.burn_after_reading == False,
                or_(
                    Paste.expires_at.is_(None),
                    Paste.expires_at > datetime.now(timezone.utc),
                ),
            )
            .order_by(
                func.ts_rank(Paste.search_vector, query).desc(), Paste.created_at.desc()
            )
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

    async def update_paste(
        self,
        paste_uid: uuid.UUID,
        payload: PasteUpdateModel,
        user_uid: uuid.UUID,
        session: AsyncSession,
    ):

        # first part

        # set the new values for the main paste, revision gets the current ones
        title = payload.title
        content = payload.content

        size_bytes = len(content.encode("utf-8"))
        if size_bytes > MAX_PASTE_BYTES:
            raise TooLarge("Paste is larger than 512 KB.")

        language = payload.language

        statement = (
            select(Paste)
            .where(
                Paste.uid == paste_uid,
                Paste.owner_uid == user_uid,
                Paste.burn_after_reading == False,
                or_(
                    Paste.expires_at.is_(None),
                    Paste.expires_at > datetime.now(timezone.utc),
                ),
            )
            .with_for_update()
        )

        found_paste = (await session.exec(statement)).one_or_none()

        if not found_paste:
            raise NotFound()

        # second part

        statement = select(func.max(PasteRevision.number)).where(
            PasteRevision.paste_uid == found_paste.uid
        )
        last_number = (await session.exec(statement)).one()
        next_number = (last_number or 0) + 1

        new_revision_paste = PasteRevision(
            paste_uid=found_paste.uid,
            number=next_number,
            title=found_paste.title,
            language=found_paste.language,
            content=found_paste.content,
            size_bytes=found_paste.size_bytes,
        )

        # update the result paste after the revision paste, so the revision paste gets the old values

        found_paste.title = title
        found_paste.content = content
        found_paste.language = language
        found_paste.size_bytes = size_bytes

        # commit them both at once

        session.add(found_paste)
        session.add(new_revision_paste)
        await session.commit()

        return found_paste

    async def list_revisions(
        self, paste_uid: uuid.UUID, user_uid: uuid.UUID | None, session: AsyncSession
    ):
        paste = await self.get_viewable_paste(paste_uid, user_uid, session)
        is_owner = user_uid is not None and paste.owner_uid == user_uid

        statement = select(PasteRevision).where(PasteRevision.paste_uid == paste_uid)
        if not is_owner:
            statement = statement.where(PasteRevision.is_public == True)
        statement = statement.order_by(PasteRevision.number)

        found_revisions = (await session.exec(statement)).all()

        return [
            {
                "uid": revision.uid,
                "title": revision.title,
                "number": revision.number,
                "public": revision.is_public,
                "created_at": revision.created_at,
            }
            for revision in found_revisions
        ]

    async def get_revision(
        self,
        paste_uid: uuid.UUID,
        number: int,
        user_uid: uuid.UUID | None,
        session: AsyncSession,
    ):
        paste = await self.get_viewable_paste(paste_uid, user_uid, session)
        is_owner = user_uid is not None and paste.owner_uid == user_uid

        statement = select(PasteRevision).where(
            PasteRevision.paste_uid == paste_uid,
            PasteRevision.number == number,
        )
        if not is_owner:
            statement = statement.where(PasteRevision.is_public == True)

        found_revision = (await session.exec(statement)).one_or_none()

        if not found_revision:
            raise NotFound()

        return {
            "uid": found_revision.uid,
            "title": found_revision.title,
            "number": found_revision.number,
            "content": found_revision.content,
            "public": found_revision.is_public,
        }

    async def set_revision_visibility(
        self,
        paste_uid: uuid.UUID,
        number: int,
        payload: RevisionVisibilityModel,
        user_uid: uuid.UUID,
        session: AsyncSession,
    ):
        visiblity = payload.is_public

        statement = (
            select(PasteRevision)
            .join(Paste)
            .where(
                Paste.uid == paste_uid,
                Paste.owner_uid == user_uid,
                PasteRevision.paste_uid == paste_uid,
                PasteRevision.number == number,
            )
        )

        found_revision = (await session.exec(statement)).one_or_none()

        if not found_revision:
            raise NotFound()

        found_revision.is_public = visiblity

        session.add(found_revision)

        await session.commit()
        return found_revision
