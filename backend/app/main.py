from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


from app.core.database import get_db
from app.routers.crawler_router import router as crawler_router

from app.routers import dashboard
from app.routers import analysis

from app.routers import websocket
from app.routers import qa
from app.routers import export

app = FastAPI(
    title="Medical Beauty Public Opinion Analysis System",
    description="醫美時尚輿情分析系統 API",
    version="1.0.0"
)

# Note:
# CORS dùng để cho frontend Vue gọi API backend.
# Nếu không có đoạn này, trình duyệt sẽ chặn request từ localhost:5173 sang localhost:8000.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký crawler router vào FastAPI.
# Sau khi include, API /api/crawler/ptt sẽ xuất hiện trong /docs.
app.include_router(crawler_router) #Phase 2

app.include_router(dashboard.router) #phase 3

app.include_router(analysis.router) #Phase 4

# Phase 6 WebSocket API
app.include_router(websocket.router)

# Phase 7 AI Q&A API
app.include_router(qa.router)

# Phase 8 Excel export API
app.include_router(export.router)

@app.get("/")
def root():
    return {
        "message": "Medical Beauty Public Opinion Analysis System API is running"
    }


@app.get("/health")
def health_check():
    """
    Health check dùng để kiểm tra:
    1. Backend có chạy không.
    2. Database có kết nối được không.
    """
    db_status = get_db()

    return {
        "api": "ok",
        "database": db_status
    }
