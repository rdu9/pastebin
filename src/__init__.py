from fastapi import FastAPI
from contextlib import asynccontextmanager
import structlog
from src.config import Config
from src.auth.routes import auth_router
from src.errors import register_all_errors

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()

version = "v1"

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app.starting", domain=Config.DOMAIN)

    yield
    logger.info("app.shutting_down")

app = FastAPI(
    version=version,
    title="Pastebin",
    description = "Pastebin app, using k8s.",
    lifespan=lifespan
)

# STATIC MOUNT


# register all errors / middleware

register_all_errors(app)

# register all routes

app.include_router(auth_router, prefix=f"/api/{version}/auth", tags = ["Auth"])