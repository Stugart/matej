from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .logging_setup import setup_logging
from .routers import health
from .settings import get_settings

setup_logging()
log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    log.info(
        "api.startup",
        env=settings.app_env,
        version=__version__,
        log_level=settings.app_log_level,
    )
    # Dev: vytvor storage adresáre. Produkcia ich má z DEPLOYMENT.md.
    for path in (settings.storage_root, settings.tmp_root):
        path.mkdir(parents=True, exist_ok=True)
    yield
    log.info("api.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Kutaj AI Core API",
        version=__version__,
        # OpenAPI docs len v dev — v prod nie sú dôvod ich vystavovať.
        docs_url="/api/v1/docs" if not settings.is_prod else None,
        redoc_url=None,
        openapi_url="/api/v1/openapi.json" if not settings.is_prod else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api/v1")

    static_dir = Path(__file__).parent / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/", include_in_schema=False)
        async def root() -> FileResponse:
            return FileResponse(static_dir / "index.html")

    return app


app = create_app()
