# backend/app/services/keyword_extractor.py

import re
from collections import Counter

import jieba

from app.services.dashboard_service import BEAUTY_KEYWORDS


# 說明：
# 把醫美領域詞加入 jieba 詞庫，避免像「玻尿酸」「皮秒雷射」被切碎。
for _word in BEAUTY_KEYWORDS:
    jieba.add_word(_word)

# 中文常見停用詞 + PTT 常見雜訊詞，斷詞後濾掉。
STOPWORDS = {
    "的", "了", "是", "我", "你", "他", "她", "它", "們", "也", "在", "和", "與", "或",
    "有", "沒有", "沒", "就", "都", "很", "還", "但", "但是", "而且", "因為", "所以",
    "如果", "這", "那", "這個", "那個", "這些", "那些", "什麼", "怎麼", "為什麼", "可以",
    "不會", "不能", "不要", "自己", "大家", "真的", "覺得", "感覺", "知道", "應該",
    "會", "要", "想", "說", "看", "用", "去", "來", "被", "把", "讓", "給", "跟",
    "一個", "一下", "一些", "現在", "已經", "然後", "其實", "比較", "問題", "謝謝",
    "推", "噓", "樓", "文", "版", "各位", "請問", "分享", "心得", "討論",
}

# 只保留含中日韓字元的詞（去掉純英數、標點）。
_CJK_RE = re.compile(r"[一-鿿]")


def _is_meaningful(token: str) -> bool:
    token = token.strip()
    if len(token) < 2:
        return False
    if token in STOPWORDS:
        return False
    if not _CJK_RE.search(token):
        return False
    return True


def extract_keywords(texts: list[str], top_n: int = 20) -> list[dict]:
    """
    說明：
    用 jieba 對一批文字斷詞，統計詞頻，回傳出現最多的關鍵字。
    相較於固定關鍵字清單，這能自動浮現新興討論詞。

    回傳格式：[{"keyword": 詞, "count": 次數}, ...]
    """

    counter: Counter[str] = Counter()

    for text in texts:
        if not text:
            continue
        for token in jieba.cut(text):
            if _is_meaningful(token):
                counter[token] += 1

    return [
        {"keyword": word, "count": count}
        for word, count in counter.most_common(top_n)
    ]
