# backend/app/core/rate_limit.py

"""依 IP 計算的請求頻率限制（狀態存在資料庫）。

為什麼不放記憶體？
舊版把計數存在 process 的 dict 裡，只有單一 worker 時才正確：
開 N 個 worker，每個 worker 各有一份計數，等於把限制放寬成 N 倍。
狀態改存資料庫後，所有 worker 共用同一份計數。

為什麼從滑動視窗改成固定視窗？
滑動視窗要保存每一次請求的時戳，寫入量大得多。
固定視窗每個 key 只需一列，代價是視窗交界處最多可能放行接近兩倍的請求。
對登入保護而言可以接受——帳號層級的鎖定（連續失敗即鎖定）才是主要防線，
這裡擋的是同一個來源的暴力嘗試。
"""

import logging
from datetime import timedelta

from fastapi import Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.time_utils import taiwan_now
from app.models.database_models import RateLimitHit

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    當作 FastAPI dependency 使用：
        limiter = RateLimiter(max_requests=10, window_seconds=60)

        @router.post("/ask", dependencies=[Depends(limiter)])
    """

    def __init__(self, max_requests: int, window_seconds: int, scope: str = "default"):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # 不同端點各自計數，避免登入的額度被問答用掉。
        self.scope = scope

    def _client_key(self, request: Request) -> str:
        # 在 Render 上請求會經過 proxy，真實 IP 在 X-Forwarded-For 的第一個元素。
        forwarded = request.headers.get("x-forwarded-for", "")

        if forwarded:
            client = forwarded.split(",")[0].strip()
        else:
            client = request.client.host if request.client else "unknown"

        return f"{self.scope}:{client}"[:200]

    def _reject(self):
        raise HTTPException(status_code=429, detail="請求太頻繁，請稍後再試。")

    def __call__(self, request: Request, db: Session = Depends(get_db)):
        key = self._client_key(request)
        now = taiwan_now()
        window_start = now - timedelta(seconds=self.window_seconds)

        row = db.query(RateLimitHit).filter(RateLimitHit.key == key).first()

        if row is None:
            try:
                db.add(RateLimitHit(key=key, window_start=now, count=1))
                db.commit()
                return
            except IntegrityError:
                # 同一個 key 幾乎同時進來兩個請求，另一邊先插入了。
                db.rollback()
                row = db.query(RateLimitHit).filter(RateLimitHit.key == key).first()

                if row is None:
                    # 極少見：插入失敗又讀不到。放行比誤擋使用者好，
                    # 頻率限制不是唯一防線。
                    logger.warning("Rate limit row vanished for %s; allowing request", key)
                    return

        # 視窗已經過去就重新開始計數。
        if row.window_start < window_start:
            row.window_start = now
            row.count = 1
            db.commit()
            return

        if row.count >= self.max_requests:
            self._reject()

        row.count += 1
        db.commit()


def clear_rate_limits(db: Session) -> None:
    """清掉所有頻率限制計數。

    給測試使用：狀態改存資料庫後，不能再直接清空記憶體中的 dict。
    測試若要驗證「帳號鎖定」而不想被 IP 限制干擾，就在嘗試之間呼叫這個。
    """
    db.query(RateLimitHit).delete()
    db.commit()
