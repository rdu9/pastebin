from src.db.models import User, LoginSession
import json
from fastapi import HTTPException, Request
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi.responses import JSONResponse
from sqlmodel import select
import uuid
from src.config import Config
from datetime import datetime, timedelta, timezone
from .schemas import UserCreateModel, UserLoginModel
from .security import (
    verify_hashed_password,
    generate_token,
    generate_hashed_token,
    hash_password,
)
from starlette.concurrency import run_in_threadpool
from src.errors import NotFound, NotAuthenticated


class UserService:

    ## checks , simple returns

    async def user_exists(self, email: str, session: AsyncSession):
        statement = select(User).where(User.email == email)
        result = await session.exec(statement)
        result_first = result.first()
        if not result_first:
            return False
        return True

    async def get_current_token(self, request: Request) -> uuid.UUID:
                token = request.cookies.get("session")
                if not token:
                    raise NotAuthenticated()
                return token

    async def get_user_by_uid(self, user_uid: uuid.UUID, session: AsyncSession):
            statement = select(User).where(User.uid == user_uid)
            result = await session.exec(statement)
            user_info = result.one_or_none()
            if not user_info:
                raise NotFound
            return {
                    "user_uid": str(user_info.uid),
                    "email": user_info.email,
                }

    async def get_user_uid_by_email(self, user_email: str, session: AsyncSession):
            statement = select(User.uid).where(User.email == user_email)
            result = await session.exec(statement)
            result_uid = result.one_or_none()
            if not result_uid:
                return None
            return result_uid
    
    async def check_user_password(
            self, user_email: str, user_password: str, session: AsyncSession
        ):
            statement = select(User.password_hash).where(User.email == user_email)
            result = await session.exec(statement)
            hashed_password = result.one_or_none()
            is_valid = await run_in_threadpool(verify_hashed_password, hashed_password, user_password)
            if is_valid:
                return True
            else:
                return False

    async def get_user_uid_by_token_hash(self, token: str, session: AsyncSession):

        # user carries the unhashed token in the session and the loginsession table has the hashed version of it

        token_hash = await run_in_threadpool(generate_hashed_token,token)

        statement = select(LoginSession.user_uid).where(LoginSession.token_hash == token_hash, LoginSession.expires_at > datetime.now(timezone.utc))
        result = await session.exec(statement)
        response = result.one_or_none()
        if not response:
            raise NotAuthenticated()
        return response


    async def delete_session(self, token: str, session: AsyncSession):

        # again, get the token hash , because user carries unhashed token

        token_hash = await run_in_threadpool(generate_hashed_token,token)

        login_session = await session.get(LoginSession, token_hash)

        if not login_session:
             raise NotAuthenticated()

        await session.delete(login_session)
        await session.commit()
        return True

    async def get_user_by_email(self, email: str, session: AsyncSession):
        statement = select(User).where(User.email == email)
        result = await session.exec(statement)
        result_first = result.first()
        if not result_first:
            return None
        return result_first

    ## creates, logins, etc

    async def create_user(self, payload: UserCreateModel, session: AsyncSession):
        user_email = payload.email.strip().lower()
        user_password = payload.password

        #check if the user exists
        
        if await self.user_exists(user_email, session):
            raise HTTPException(status_code=409, detail="User already exists")

        # hash the user password

        hashed_password = await run_in_threadpool(hash_password, user_password)

        # create the new user object and commit everything

        new_user = User(email=user_email, password_hash=hashed_password)

        session.add(new_user)
        await session.commit()
        return new_user


    async def add_cookie(self, response: JSONResponse, user_uid: uuid.UUID, session: AsyncSession):

        token = generate_token()
        token_hash = generate_hashed_token(token)

        # create the db table

        new_login_session = LoginSession(token_hash=token_hash,user_uid=user_uid,expires_at=datetime.now(timezone.utc) + timedelta(days=30))
        session.add(new_login_session)

        # finally, add the cookie

        response.set_cookie(
            key="session",
            value=token,
            httponly=True,
            secure=Config.COOKIE_SECURE,
            samesite="lax",
            max_age=30 * 24 * 3600,
            path="/"
        )

        # commit the db changes at the end

        await session.commit()

        return response
