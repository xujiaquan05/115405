# backend/app/services/keyword_extractor.py

"""從文章中找出「這個主題特別常談」的詞。

為什麼不是單純數次數？
單純數次數時，排行榜前幾名會是「還是」「就是」「起來」「時候」這種虛詞——
它們在哪篇文章裡都很多，卻不代表任何話題。實測查「玻尿酸」時，
前 20 名有 8 個是這類詞，真正的醫美詞只有 4 個。

停用詞清單擋得掉已知的那些，但永遠有新的漏進來，是在跟它追。
這裡改成看「這個詞對這批文章有多特別」：

    分數 = 這批文章裡有幾篇提到它 × log(1 + 全庫篇數 / (1 + 全庫有幾篇提到它))

「還是」在全庫幾乎每篇都有，右邊那項趨近 log(2)，自然被壓下去；
「保濕」只在部分文章出現，右邊那項大，查「玻尿酸」時就浮得上來。
好處是不必事先知道哪些詞是雜訊，新出現的流行詞也照樣排得進來。

IDF 用 log(1 + N/df) 而不是教科書的 log(N/df)：後者在 df 等於 N 時
會變成 0，整個詞被完全抹掉；加一能保留一點點權重。
這與 rag_service 的混合檢索用的是同一個式子。
"""

import math
import re
from collections import Counter
from datetime import timedelta

import jieba
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.time_utils import taiwan_now
from app.models.database_models import Article
from app.services.beauty_lexicon import BEAUTY_LEXICON

# 說明：
# 把領域詞加入 jieba 詞庫，避免像「玻尿酸」「皮秒雷射」被切碎。
# 同一份清單也用來過濾結果，所以加進詞庫這件事變成必要而不只是優化：
# 詞沒被完整切出來，就不可能比對到清單。
for _word in BEAUTY_LEXICON:
    jieba.add_word(_word)

# 中文常見停用詞 + PTT 常見雜訊詞，斷詞後濾掉。
# IDF 已能壓下大部分虛詞，這份清單只是先擋掉最明顯的，少算一輪分數。
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

# 全庫詞頻統計：掃完 10,275 篇要 31 秒，不可能每次請求都算。
# 改成抽樣 + 快取；我們只需要知道一個詞是「幾乎每篇都有」還是「只有少數篇有」，
# 抽樣估出來的比例已經足夠分辨，不需要精確值。
CORPUS_SAMPLE_SIZE = 1500
CORPUS_CACHE_TTL = timedelta(hours=6)
CONTENT_CHARS_FOR_DF = 800

_corpus_cache: dict = {"built_at": None, "size": 0, "document_frequency": {}}


def _is_meaningful(token: str) -> bool:
    """只認領域詞。

    熱門話題要給的是「這段期間大家在討論哪些醫美項目」，
    不是「這批文章用了哪些中文詞」。純統計時排行榜會被
    「留言」「大學」「昨天」「在意」佔滿——它們確實常出現，
    但對輿情分析沒有意義。
    """
    return token.strip() in BEAUTY_LEXICON


def _tokens_in(text: str) -> set[str]:
    """一篇文章出現過哪些詞（只看有沒有出現，不看出現幾次）。"""
    return {token for token in jieba.cut(text or "") if _is_meaningful(token)}


def corpus_document_frequencies(db: Session) -> tuple[dict[str, int], int]:
    """回傳 (每個詞在幾篇文章出現過, 取樣篇數)。

    結果快取 6 小時。爬蟲一天只跑一輪，詞的分布不會在幾小時內大幅改變，
    而重算一次要數秒，不值得每次請求都做。
    """
    now = taiwan_now()
    built_at = _corpus_cache["built_at"]

    if built_at is not None and now - built_at < CORPUS_CACHE_TTL:
        return _corpus_cache["document_frequency"], _corpus_cache["size"]

    rows = (
        db.query(Article.title, Article.content)
        .order_by(func.random())
        .limit(CORPUS_SAMPLE_SIZE)
        .all()
    )

    frequency: Counter[str] = Counter()
    for row in rows:
        text = f"{row.title or ''} {(row.content or '')[:CONTENT_CHARS_FOR_DF]}"
        frequency.update(_tokens_in(text))

    _corpus_cache.update(
        {"built_at": now, "size": len(rows), "document_frequency": dict(frequency)}
    )
    return _corpus_cache["document_frequency"], len(rows)


def reset_corpus_cache() -> None:
    """測試用：清掉快取，下次呼叫會重新統計。"""
    _corpus_cache.update({"built_at": None, "size": 0, "document_frequency": {}})


def extract_keywords(
    texts: list[str],
    top_n: int = 20,
    corpus_document_frequency: dict[str, int] | None = None,
    corpus_size: int = 0,
) -> list[dict]:
    """找出這批文章中最具代表性的詞。

    回傳 [{"keyword": 詞, "count": 有幾篇文章提到它}, ...]，
    count 是「篇數」而非「出現次數」——畫面上寫的是「N 則」，
    用篇數才名實相符，也不會被一篇狂刷同一個詞的長文灌爆。

    沒有提供全庫統計時退回純篇數排序，行為與舊版相近；
    這樣呼叫端（例如測試）不給統計也能運作。
    """
    document_frequency: Counter[str] = Counter()

    for text in texts:
        if not text:
            continue
        document_frequency.update(_tokens_in(text))

    if not document_frequency:
        return []

    # 一個詞至少要被兩篇文章提到才算「話題」。
    # 這條同時處理了兩件事：濾掉斷詞失誤留下的碎片（實測出現過
    # 「還掰說」「慎選有」），以及冷門查詢——查「音波拉皮」只命中一篇時，
    # 每個詞都只出現一次，排序純粹是雜訊，這時回空的比硬湊二十個詞誠實。
    MINIMUM_DOCUMENTS = 2
    matched_total = max(len(texts), 1)

    def score(word: str, appears_in: int) -> float:
        if not corpus_document_frequency or corpus_size <= 0:
            return float(appears_in)

        # 比的是「在這批文章裡的普及程度」對上「在全庫的普及程度」。
        # 單看全庫 IDF 不夠：「還是」在九成文章裡出現，IDF 雖小，
        # 但它在這批文章裡的篇數也很大，乘起來還是擠得進前二十。
        # 改看兩個比例的倍率，普及程度一樣的詞倍率趨近 1、取對數趨近 0，
        # 比例低於全庫的（更不特別）甚至變負數，自然沉到底。
        smoothing = 1 / (corpus_size + 1)
        here = appears_in / matched_total
        everywhere = corpus_document_frequency.get(word, 0) / corpus_size
        lift = math.log((here + smoothing) / (everywhere + smoothing))

        # 乘上絕對篇數：只在兩三篇出現的冷門詞倍率很高，
        # 但它代表的討論量小，不該排在被上百篇提到的詞前面。
        return appears_in * lift

    ranked = sorted(
        (
            (word, appears_in)
            for word, appears_in in document_frequency.items()
            if appears_in >= MINIMUM_DOCUMENTS
        ),
        key=lambda pair: (score(*pair), pair[1]),
        reverse=True,
    )

    return [{"keyword": word, "count": appears_in} for word, appears_in in ranked[:top_n]]
