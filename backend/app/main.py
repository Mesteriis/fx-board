from fastapi import FastAPI

from app.core.errors import AppError, app_error_handler
from app.routers.ads import router as ads_router
from app.routers.auth import router as auth_router


def create_app() -> FastAPI:
    app = FastAPI(title="FX Board API")
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(auth_router)
    app.include_router(ads_router)

    @app.get("/api/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
