# backend/app/routers/websocket.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.websocket.manager import websocket_manager


router = APIRouter(
    prefix="/ws",
    tags=["WebSocket"],
)


@router.websocket("/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    """
    說明：
    Dashboard 用的 WebSocket endpoint。

    前端會連線到：
    ws://localhost:8000/ws/dashboard

    連線後 backend 可以推送即時事件：
    - crawler_started
    - crawler_progress
    - crawler_completed
    - crawler_failed
    - stats_updated
    """

    await websocket_manager.connect(websocket)

    try:
        # 先送出第一則訊息，讓前端知道 WebSocket 已連線成功。
        await websocket.send_json({
            "type": "connected",
            "message": "WebSocket connected successfully",
            "client_count": websocket_manager.connection_count(),
        })

        while True:
            # 維持連線。
            # 前端可能送 ping 或任意文字，
            # 目前不需要處理 client 送上來的內容。
            await websocket.receive_text()

    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)

    except Exception:
        websocket_manager.disconnect(websocket)
