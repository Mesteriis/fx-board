from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="FX Board API")

    @app.get("/api/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
