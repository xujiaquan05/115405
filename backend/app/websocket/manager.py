# backend/app/websocket/manager.py

import asyncio
from typing import List, Dict, Any
from fastapi import WebSocket


class ConnectionManager:
    """
    說明：
    ConnectionManager 負責管理所有連線中的 WebSocket client。

    例如：
    - User A 開著 Dashboard
    - User B 也開著 Dashboard

    當 crawler 執行時，backend 會 broadcast 訊息給
    所有開著 Dashboard 的 user。

    限制：連線清單存在單一 process 的 RAM 中，
    若之後 scale 多個 worker，broadcast 只會送到
    同一個 worker 的 client，需要改用 Redis pub/sub。
    """

    def __init__(self):
        # active_connections 保存仍在連線中的 WebSocket client。
        self.active_connections: List[WebSocket] = []
        self._loop = None

    async def connect(self, websocket: WebSocket):
        """
        前端建立 WebSocket 連線時，
        backend 必須先 accept()，再保存 connection。
        """

        await websocket.accept()
        self._loop = asyncio.get_running_loop()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """
        當 user 關閉分頁 / 重新整理 / 斷網時，
        把該 websocket 從清單中移除。
        """

        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """
        把同一則訊息送給所有連線中的 client。

        WebSocket 隨時可能斷線，
        所以每次傳送都要 try/except；
        傳送失敗的 connection 加入待移除清單。
        """

        disconnected_clients = []

        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # 傳送失敗代表 client 可能已經斷線。
                disconnected_clients.append(connection)

        # 移除已斷線的 client，之後不再對它們傳送。
        for connection in disconnected_clients:
            self.disconnect(connection)

    def broadcast_sync(self, message: Dict[str, Any]):
        """
        提供給同步程式呼叫 broadcast 的入口。

        因為 crawler 是同步函式，無法直接 await。

        處理方式：
        - 目前執行緒有 event loop：建立 task
        - 沒有 event loop：透過已記錄的 loop 或 asyncio.run() 執行
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


# 建立全域共用的 manager，
# 各 router 和 crawler 匯入此物件來 broadcast。
websocket_manager = ConnectionManager()
