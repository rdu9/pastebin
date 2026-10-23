import structlog
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = structlog.get_logger()


class AppError(Exception):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "internal_error"
    message = "Something went wrong."

    def __init__(self, message: str | None = None):
        if message:
            self.message = message
        super().__init__(self.message)


class NotAuthenticated(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "not_authenticated"
    message = "Log in first."


class InvalidCredentials(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "invalid_credentials"
    message = "Invalid email or password."

class TooLarge(AppError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    error_code = "too_large"
    message = "Too large."

class Forbidden(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "forbidden"
    message = "You can't do that."


class NotFound(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "not_found"
    message = "Not found."


class AlreadyExists(AppError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "already_exists"
    message = "Already exists."


class RateLimited(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "rate_limited"
    message = "Too many requests."


def register_all_errors(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error_code": exc.error_code, "message": exc.message},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        logger.exception("unhandled_error", path=request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error_code": "internal_error", "message": "Something went wrong."},
        )
