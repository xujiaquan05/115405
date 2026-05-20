# backend/app/websocket/manager.py

import asyncio
from typing import List, Dict, Any
from fastapi import WebSocket


class ConnectionManager:
    """
    Note:
    ConnectionManager dùng để quản lý tất cả WebSocket client đang kết nối.

    Ví dụ:
    - User A mở Dashboard
    - User B cũng mở Dashboard

    Khi crawler chạy, backend sẽ broadcast message cho tất cả user đang mở Dashboard.
    """

    def __init__(self):
        # Note:
        # active_connections lưu danh sách WebSocket client còn đang kết nối.
        self.active_connections: List[WebSocket] = []
        self._loop = None

    async def connect(self, websocket: WebSocket):
        """
        Note:
        Khi frontend kết nối WebSocket,
        backend phải accept() trước, sau đó mới lưu connection.
        """

        await websocket.accept()
        self._loop = asyncio.get_running_loop()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """
        Note:
        Khi user đóng tab / reload trang / mất mạng,
        mình xóa websocket đó ra khỏi danh sách.
        """

        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """
        Note:
        Gửi cùng một message cho tất cả client đang kết nối.

        Vì WebSocket có thể bị ngắt bất cứ lúc nào,
        nên mỗi lần gửi phải try/except.
        Nếu gửi thất bại, đưa connection đó vào danh sách cần xóa.
        """

        disconnected_clients = []

        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # Note:
                # Nếu gửi thất bại, nghĩa là client có thể đã disconnect.
                disconnected_clients.append(connection)

        # Note:
        # Xóa các client đã mất kết nối để lần sau không gửi nữa.
        for connection in disconnected_clients:
            self.disconnect(connection)

    def broadcast_sync(self, message: Dict[str, Any]):
        """
        Note:
        Hàm này dùng để gọi broadcast từ code đồng bộ.

        Vì crawler hiện tại của mình là sync function,
        không thể dùng await trực tiếp.

        Cách xử lý:
        - Nếu đang có event loop: tạo task
        - Nếu không có event loop: dùng asyncio.run()
        """

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.broadcast(message))
        except RuntimeError:
            if self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(self.broadcast(message), self._loop)
            else:
                asyncio.run(self.broadcast(message))

    def connection_count(self) -> int:
        return len(self.active_connections)


# Note:
# Tạo một manager global dùng chung cho toàn backend.
# Các router và crawler sẽ import object này để broadcast.
websocket_manager = ConnectionManager()
