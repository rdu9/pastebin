from fastapi import APIRouter, Depends, HTTPException, status, Response
from src.db.main import get_session
from .schemas import UserCreateModel, UserLoginModel
from sqlmodel.ext.asyncio.session import AsyncSession
from .service import UserService
from fastapi.responses import JSONResponse
from .dependencies import get_current_user_uid
import uuid
from src.ratelimit import login_ratelimit, register_ratelimit

## define routers , and service

user_service = UserService()
auth_router = APIRouter()

## the actual endpoints

@auth_router.post("/login", dependencies=[Depends(login_ratelimit)])
async def login_user(
    payload: UserLoginModel, session: AsyncSession = Depends(get_session)
):

    user_email = payload.email.strip().lower()
    user_password = payload.password

    # check if user exists and grab the uid

    user_uid = await user_service.get_user_uid_by_email(user_email, session)
    if not user_uid:
        raise HTTPException(status_code=401, detail="User not found")

    # user exists, now check its password

    checked_password = await user_service.check_user_password(
        user_email, user_password, session
    )
    if not checked_password:
        raise HTTPException(
            status_code=401, detail="User not found"
        )  # return similar message, for security purposes

    # user exists, credentials are fine, return the message and add the cookie

    response = JSONResponse(
        content={
            "message": "Account logged in successfully!",
        },
        status_code=status.HTTP_200_OK,
    )

    await user_service.add_cookie(response, user_uid, session)

    return response


@auth_router.post("/register", dependencies=[Depends(register_ratelimit)])
async def create_user(
    payload: UserCreateModel, session: AsyncSession = Depends(get_session)
):
    response = await user_service.create_user(payload, session)
    return response


@auth_router.post("/logout")
async def logout_user(
    response: Response,
    token: str = Depends(user_service.get_current_token),
    session: AsyncSession = Depends(get_session),
):
    await user_service.delete_session(token,session)
    response.delete_cookie("session", path="/")
    return {}


@auth_router.get("/me")
async def me(
    user_uid: uuid.UUID = Depends(get_current_user_uid),
    session: AsyncSession = Depends(get_session),
):
    return await user_service.get_user_by_uid(user_uid, session)

@auth_router.get("/")
async def healthz():
    return {"status":"ok"}