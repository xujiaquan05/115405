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
    Note:
    Đây là WebSocket endpoint cho Dashboard.

    Frontend sẽ kết nối tới:
    ws://localhost:8000/ws/dashboard

    Sau khi kết nối, backend có thể gửi realtime event:
    - crawler_started
    - crawler_progress
    - crawler_completed
    - crawler_failed
    - stats_updated
    """

    await websocket_manager.connect(websocket)

    try:
        # Note:
        # Gửi message đầu tiên để frontend biết WebSocket đã kết nối thành công.
        await websocket.send_json({
            "type": "connected",
            "message": "WebSocket connected successfully",
            "client_count": websocket_manager.connection_count(),
        })

        while True:
            # Note:
            # Giữ kết nối sống.
            # Frontend có thể gửi ping hoặc text bất kỳ.
            # Hiện tại mình không cần xử lý nội dung client gửi lên.
            await websocket.receive_text()

    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)

    except Exception:
        websocket_manager.disconnect(websocket) 
