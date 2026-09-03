# backend/app/services/password_policy.py

"""密碼強度規則。

只放「擋得住實際攻擊」的規則，不做那種強迫加大小寫與符號的複雜度要求：
研究顯示那種規則常讓使用者改出 Password1! 這類仍然好猜的密碼。
這裡改為要求足夠長度，並直接封鎖常見密碼與跟帳號相同的密碼。
"""

from fastapi import HTTPException


MIN_LENGTH = 8
MAX_LENGTH = 200

# 外洩密碼排行榜上長年名列前茅者，加上本系統自己的預設密碼。
COMMON_PASSWORDS = {
    "admin123", "password", "password1", "password123", "12345678",
    "123456789", "1234567890", "qwerty123", "abc12345", "iloveyou",
    "admin1234", "letmein1", "welcome1", "sunshine", "princess",
    "football", "baseball", "trustno1", "starwars", "passw0rd",
    "qwertyuiop", "1qaz2wsx", "zaq12wsx", "asdfghjkl", "11111111",
}


def _too_repetitive(password: str) -> bool:
    """整串只有一兩種字元（例如 aaaaaaaa、abababab）。"""
    return len(set(password)) <= 2


def validate_password(password: str, username: str | None = None) -> None:
    """檢查密碼是否符合規則，不合格就丟出 400。

    username 有給的話會一併檢查，避免把帳號本身當密碼。
    """

    if not password or len(password) < MIN_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"密碼至少需要 {MIN_LENGTH} 個字元。",
        )

    if len(password) > MAX_LENGTH:
        raise HTTPException(status_code=400, detail=f"密碼不可超過 {MAX_LENGTH} 個字元。")

    if password.lower() in COMMON_PASSWORDS:
        raise HTTPException(
            status_code=400,
            detail="這組密碼太常見，容易被猜中，請換一組。",
        )

    if _too_repetitive(password):
        raise HTTPException(
            status_code=400,
            detail="密碼過於重複，請混合更多不同字元。",
        )

    if username:
        lowered = username.strip().lower()

        if lowered and lowered in password.lower():
            raise HTTPException(
                status_code=400,
                detail="密碼不可包含帳號名稱。",
            )


def score_password(password: str) -> dict:
    """給前端顯示的強度評分（0–4）。

    與 validate_password 分開：驗證決定「能不能用」，
    評分只是提示「有多強」，兩者的門檻不一定相同。
    """

    if not password:
        return {"score": 0, "label": "尚未輸入"}

    score = 0

    if len(password) >= MIN_LENGTH:
        score += 1
    if len(password) >= 12:
        score += 1
    if any(c.isalpha() for c in password) and any(c.isdigit() for c in password):
        score += 1
    if any(not c.isalnum() for c in password):
        score += 1

    if password.lower() in COMMON_PASSWORDS or _too_repetitive(password):
        score = 0

    labels = {0: "非常弱", 1: "弱", 2: "普通", 3: "良好", 4: "很強"}
    return {"score": score, "label": labels[score]}
