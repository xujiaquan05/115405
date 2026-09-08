import logging
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.scheduler import shutdown_scheduler, start_scheduler
from app.core.startup import initialize_database
from app.routers import admin, analysis, articles, auth, dashboard, export, monitor, qa, websocket
from app.routers.crawler_router import router as crawler_router

# 說明：
# 設定 root logger，讓各模組的 logger.exception() 真的會輸出。
# 沒有這段的話，uvicorn 只會顯示自己的存取紀錄，
# 應用程式內部記的錯誤在正式環境等於消失。
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


# 說明：
# FastAPI 建議用 lifespan 取代已 deprecated 的 @app.on_event("startup")。
# yield 之前的程式碼在啟動時執行，之後的在關閉時執行。
@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(
    title="Medical Beauty Public Opinion Analysis System",
    description="Medical Beauty Public Opinion Analysis System API",
    version="1.0.0",
    lifespan=lifespan,
)


# APP_ENV=development 時放寬部分只在正式環境才適用的限制（HSTS、Secure cookie）。
IS_DEVELOPMENT = os.getenv("APP_ENV", "development").lower() == "development"


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


# 說明：
# 未被攔截的例外統一在這裡處理。
# 沒有這段的話，錯誤會變成沒有內容的 500，而且看不出是哪一次請求出錯——
# 使用者回報「剛剛壞了」時，log 裡找不到對應的那一筆。
#
# 作法：產生一組短代碼，同時寫進 log 與回傳給使用者，
# 使用者把代碼提供給維運，就能直接定位到那一次的堆疊。
# 回應本身不含例外內容，避免洩漏內部結構。
@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception):
    incident_id = uuid.uuid4().hex[:8]

    logger.exception(
        "Unhandled error [%s] on %s %s",
        incident_id,
        request.method,
        request.url.path,
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": f"系統發生未預期的錯誤，請稍後再試。（錯誤代碼：{incident_id}）",
            "incident_id": incident_id,
        },
    )


# 說明：
# 安全性標頭。這些是「瀏覽器層」的防護，跟密碼雜湊互補：
# 雜湊保護的是資料庫外洩，這些保護的是使用者的瀏覽器連線。
#
# CSP 只允許自家資源：前端是建置後的靜態檔（同源），
# 樣式需要 unsafe-inline 是因為 Vue 會注入行內樣式。
CSP_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self' data:",
    "connect-src 'self' ws: wss:",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
])


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)

    # 不要讓瀏覽器自己猜檔案型別（可被用來把上傳內容當成腳本執行）。
    response.headers["X-Content-Type-Options"] = "nosniff"
    # 禁止被嵌入 iframe，避免點擊劫持。
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = CSP_POLICY

    # HSTS 只在正式環境送出：開發時走 http://localhost，
    # 送了會讓瀏覽器記住「這個網域只准 https」而連不上。
    if not IS_DEVELOPMENT:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(monitor.router)
app.include_router(crawler_router)
app.include_router(dashboard.router)
app.include_router(analysis.router)
app.include_router(websocket.router)
app.include_router(qa.router)
app.include_router(articles.router)
app.include_router(export.router)


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        database_status = "ok"
    except Exception:
        # 只回報「有問題」，不要把例外訊息原封不動吐出去：
        # 這個端點不需登入即可存取，而資料庫的錯誤訊息會帶出
        # 主機位址與連接埠等內部資訊。細節寫進 log 供維運查看。
        logger.exception("Health check failed to reach the database")
        database_status = "error"

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
