"""Top-level FastAPI application entry point, re-exporting app from app.api.main."""

from app.api.main import app, create_app

__all__ = ["app", "create_app"]

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
