# backend/app/services/plan_service.py

"""訂閱方案與額度檢查。

額度值 -1 一律代表「不限制」（見 Plan 模型）。

管理員不受額度限制：他們負責維運系統，若被自己設定的方案擋住
會沒辦法處理問題。實際付費控管針對一般使用者。
"""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.time_utils import taiwan_now
from app.models.database_models import Plan, UsageCounter, WatchKeyword


UNLIMITED = -1

DEFAULT_PLAN_CODE = "free"

# 找不到方案資料時的保底值，確保系統仍可運作（相當於免費版）。
FALLBACK_LIMITS = {
    "code": DEFAULT_PLAN_CODE,
    "display_name": "免費版",
    "max_watch_keywords": 1,
    "max_history_days": 7,
    "allow_all_platforms": 0,
    "monthly_qa_quota": 0,
    "allow_export": 0,
}


def current_period(now: datetime | None = None) -> str:
    """計費週期字串（YYYY-MM）。月份換了就自動重新計算，不必排程歸零。"""
    moment = now or taiwan_now()
    return moment.strftime("%Y-%m")


def is_unlimited(value: int | None) -> bool:
    return value is None or value == UNLIMITED


def is_admin(user) -> bool:
    return getattr(user, "role", None) == "admin"


def get_limits(db: Session, user) -> dict:
    """取得使用者目前方案的額度設定。"""
    code = getattr(user, "plan_code", None) or DEFAULT_PLAN_CODE
    plan = db.query(Plan).filter(Plan.code == code).first()

    if plan is None:
        return dict(FALLBACK_LIMITS)

    return {
        "code": plan.code,
        "display_name": plan.display_name,
        "max_watch_keywords": plan.max_watch_keywords,
        "max_history_days": plan.max_history_days,
        "allow_all_platforms": plan.allow_all_platforms,
        "monthly_qa_quota": plan.monthly_qa_quota,
        "allow_export": plan.allow_export,
    }


def clamp_history_days(db: Session, user, days: int) -> int:
    """把查詢天數收斂到方案允許的範圍內。

    刻意「收斂」而不是報錯：使用者只是看到較短的區間，
    畫面仍然可用，比直接擋掉友善。
    """
    if user is None:
        return days

    if is_admin(user):
        return days

    limit = get_limits(db, user)["max_history_days"]

    if is_unlimited(limit):
        return days

    return min(days, limit)


def ensure_keyword_quota(db: Session, user) -> None:
    """建立監控關鍵字前檢查數量上限。"""
    if is_admin(user):
        return

    limits = get_limits(db, user)
    maximum = limits["max_watch_keywords"]

    if is_unlimited(maximum):
        return

    used = db.query(WatchKeyword).filter(WatchKeyword.user_id == user.id).count()

    if used >= maximum:
        raise HTTPException(
            status_code=403,
            detail=(
                f"「{limits['display_name']}」最多只能監控 {maximum} 組關鍵字"
                f"（目前 {used} 組），請升級方案或先移除其他關鍵字。"
            ),
        )


def _get_counter(db: Session, user, period: str) -> UsageCounter:
    counter = (
        db.query(UsageCounter)
        .filter(UsageCounter.user_id == user.id, UsageCounter.period == period)
        .first()
    )

    if counter is None:
        counter = UsageCounter(user_id=user.id, period=period, qa_count=0)
        db.add(counter)
        db.flush()

    return counter


def ensure_qa_quota(db: Session, user) -> None:
    """AI 問答前檢查當月次數。"""
    if user is None or is_admin(user):
        return

    limits = get_limits(db, user)
    quota = limits["monthly_qa_quota"]

    if is_unlimited(quota):
        return

    used = _get_counter(db, user, current_period()).qa_count

    if used >= quota:
        if quota == 0:
            detail = f"「{limits['display_name']}」未包含 AI 問答功能，請升級方案。"
        else:
            detail = (
                f"本月 AI 問答次數已用完（{used}/{quota}），"
                "下個月會重新計算，或可升級方案。"
            )

        raise HTTPException(status_code=403, detail=detail)


def record_qa_usage(db: Session, user) -> None:
    """問答成功後才累計，失敗的請求不該扣額度。"""
    if user is None or is_admin(user):
        return

    counter = _get_counter(db, user, current_period())
    counter.qa_count += 1
    counter.updated_at = taiwan_now()
    db.commit()


def ensure_export_allowed(db: Session, user) -> None:
    if user is None or is_admin(user):
        return

    limits = get_limits(db, user)

    if not limits["allow_export"]:
        raise HTTPException(
            status_code=403,
            detail=f"「{limits['display_name']}」未包含匯出報表功能，請升級方案。",
        )


def get_plan_status(db: Session, user) -> dict:
    """給前端顯示的方案與用量摘要。"""
    limits = get_limits(db, user)
    period = current_period()

    keywords_used = db.query(WatchKeyword).filter(WatchKeyword.user_id == user.id).count()
    counter = (
        db.query(UsageCounter)
        .filter(UsageCounter.user_id == user.id, UsageCounter.period == period)
        .first()
    )

    return {
        "plan": limits,
        "period": period,
        "unlimited_admin": is_admin(user),
        "usage": {
            "watch_keywords": keywords_used,
            "qa_questions": counter.qa_count if counter else 0,
        },
    }
