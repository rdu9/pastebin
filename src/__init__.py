from fastapi import FastAPI
from contextlib import asynccontextmanager
import structlog
from src.config import Config
from src.auth.routes import auth_router
from src.pastes.routes import pastes_router
from src.images.routes import image_route
from src.images.routes import image_view_route
from src.errors import register_all_errors

### readyz imports / functions

import asyncio
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from src.db.main import async_engine
from src.db.redis import redis_client
from src.storage import s3_internal


async def check_db():
    async with async_engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

async def check_redis():
    await redis_client.ping()

async def check_garage():
    await run_in_threadpool(s3_internal.head_bucket, Bucket=Config.S3_BUCKET)


structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    cache_logger_on_first_use=True,
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

# static mount


# health endpoints for kubernetez, healthz for liveness , readyz for readiness

# HEALTH ENDPOINTS

@app.get("/healthz", tags=["Health"])
async def healthz():
    return {"status": "ok"}

@app.get("/readyz", tags=["Health"])
async def readyz():
    checks = {"postgres": check_db, "redis": check_redis, "garage": check_garage}
    results = {}
    for name, check in checks.items():
        try:
            await asyncio.wait_for(check(), timeout=2)
            results[name] = "ok"
        except Exception as e:
            logger.warning("readyz.faild", dependency=name, error=repr(e))
            results[name] = "down"

    status_code = 200 if all(v=="ok" for v in results.values()) else 503
    return JSONResponse(results, status_code=status_code)


# register all errors / middleware

register_all_errors(app)

# register all routes

app.include_router(auth_router, prefix=f"/api/{version}/auth", tags = ["Auth"])
app.include_router(pastes_router, prefix=f"/api/{version}/pastes", tags = ["Paste"])
app.include_router(image_route, prefix=f"/api/{version}/images", tags = ["Image"])
app.include_router(image_view_route, tags=["Images"])