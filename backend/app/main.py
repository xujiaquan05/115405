from pathlib import Path
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.core.database import SessionLocal
from app.core.startup import initialize_database
from app.routers.crawler_router import router as crawler_router
from app.routers import analysis, dashboard, export, qa, websocket


app = FastAPI(
    title="Medical Beauty Public Opinion Analysis System",
    description="Medical Beauty Public Opinion Analysis System API",
    version="1.0.0",
)


def get_cors_origins() -> list[str]:
    configured_origins = os.getenv("CORS_ORIGINS", "")
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    if configured_origins:
        origins.extend(
            origin.strip()
            for origin in configured_origins.split(",")
            if origin.strip()
        )

    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    initialize_database()


app.include_router(crawler_router)
app.include_router(dashboard.router)
app.include_router(analysis.router)
app.include_router(websocket.router)
app.include_router(qa.router)
app.include_router(export.router)


@app.get("/health")
def health_check():
    db = SessionLocal()

    try:
        db.execute(text("SELECT 1"))
        database_status = "ok"
    except Exception as error:
        database_status = f"error: {error}"
    finally:
        db.close()

    return {
        "api": "ok",
        "database": database_status,
    }


FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"

    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/")
def root():
    index_file = FRONTEND_DIST / "index.html"

    if index_file.exists():
        return FileResponse(index_file)

    return {
        "message": "Medical Beauty Public Opinion Analysis System API is running",
    }


@app.get("/{full_path:path}")
def serve_spa(full_path: str):
    if full_path.startswith(("api/", "ws/", "docs", "openapi.json", "redoc")):
        raise HTTPException(status_code=404, detail="Not found")

    requested_file = FRONTEND_DIST / full_path
    if requested_file.exists() and requested_file.is_file():
        return FileResponse(requested_file)

    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(index_file)

    raise HTTPException(status_code=404, detail="Frontend build not found")
