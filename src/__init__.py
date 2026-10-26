from fastapi import FastAPI
from contextlib import asynccontextmanager
import structlog
from src.config import Config
from src.auth.routes import auth_router
from src.pastes.routes import pastes_router
from src.images.routes import image_route
from src.images.routes import image_view_route
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

# HEALTH ENDPOINT

@app.get("/healthz", tags=["Health"])
async def healthz():
    return {"status": "ok"}

# STATIC MOUNT


# register all errors / middleware

register_all_errors(app)

# register all routes

app.include_router(auth_router, prefix=f"/api/{version}/auth", tags = ["Auth"])
app.include_router(pastes_router, prefix=f"/api/{version}/pastes", tags = ["Paste"])
app.include_router(image_route, prefix=f"/api/{version}/images", tags = ["Image"])
app.include_router(image_view_route, tags=["Images"])