from dataclasses import dataclass


FOCUSED_BOARDS = {
    "facelift",
    "BeautySalon",
    "MakeUp",
    "Mix_Match",
    "fashion",
    "NailSalon",
    "Mancare",
    "teeth_salon",
}

BROAD_BOARDS = {
    "Brand",
    "e-shopping",
}

TITLE_WEIGHT = 3
CONTENT_WEIGHT = 1
FOCUSED_BOARD_WEIGHT = 1

# Dcard / Mobile01 / Threads 較嚴格門檻：這些平台的內容較生活化，
# 不像 PTT 給「整板加權」，一律需要關鍵字命中分數達到此門檻才收錄。
# 門檻 2 表示：標題含 1 個領域關鍵字（×3）即可，或內文含 2 個以上。
DCARD_MIN_SCORE = 2

# 採用「關鍵字門檻」而非整板加權的平台。
KEYWORD_THRESHOLD_PLATFORMS = {"dcard", "mobile01", "threads"}

BEAUTY_FASHION_KEYWORDS = [
    "醫美",
    "整形",
    "微整",
    "玻尿酸",
    "肉毒",
    "雷射",
    "皮秒",
    "音波",
    "電波",
    "隆鼻",
    "抽脂",
    "雙眼皮",
    "診所",
    "醫師",
    "術後",
    "恢復期",
    "副作用",
    "保養",
    "保濕",
    "防曬",
    "美白",
    "抗老",
    "精華",
    "乳液",
    "化妝水",
    "面膜",
    "痘痘",
    "粉刺",
    "敏感肌",
    "彩妝",
    "粉底",
    "底妝",
    "遮瑕",
    "口紅",
    "眼影",
    "睫毛",
    "穿搭",
    "服飾",
    "外套",
    "洋裝",
    "包包",
    "鞋",
    "精品",
    "品牌",
    "美甲",
    "指甲",
    "凝膠",
    "男士保養",
    "男性保養",
    "牙齒美白",
    "美白牙齒",
]

HARD_EXCLUDE_KEYWORDS = [
    "公告",
    "板規",
    "置底",
    "徵人",
    "問卷",
    "抽獎",
    "贈送",
    "交易",
    "二手",
    "轉讓",
    "代買",
]


@dataclass(frozen=True)
class RelevanceResult:
    is_relevant: bool
    score: int
    reason: str


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _count_keyword_score(text: str, weight: int) -> int:
    return sum(weight for keyword in BEAUTY_FASHION_KEYWORDS if keyword in text)


def evaluate_article_relevance(article: dict) -> RelevanceResult:
    platform = (article.get("platform_name") or "ptt").lower()
    board = article.get("board_name") or ""
    title = article.get("title") or ""
    content = article.get("content") or ""
    combined_text = f"{title} {content}"

    has_domain_keyword = _contains_any(combined_text, BEAUTY_FASHION_KEYWORDS)
    has_hard_exclude = _contains_any(title, HARD_EXCLUDE_KEYWORDS)

    score = _count_keyword_score(title, TITLE_WEIGHT)
    score += _count_keyword_score(content, CONTENT_WEIGHT)

    # 硬排除（廣告 / 版務 / 交易）：所有平台一致。
    if has_hard_exclude and not has_domain_keyword:
        return RelevanceResult(
            is_relevant=False,
            score=score,
            reason="hard_exclude_without_domain_keyword",
        )

    # Dcard / Mobile01：不採「整板加權」，一律需關鍵字命中達門檻才收錄（較嚴格）。
    if platform in KEYWORD_THRESHOLD_PLATFORMS:
        if score >= DCARD_MIN_SCORE:
            return RelevanceResult(
                is_relevant=True,
                score=score,
                reason=f"{platform}_keyword_match",
            )
        return RelevanceResult(
            is_relevant=False,
            score=score,
            reason=f"{platform}_low_relevance",
        )

    # PTT：專注看板整板都與主題相關，給予加權。
    if board in FOCUSED_BOARDS:
        score += FOCUSED_BOARD_WEIGHT

    if board in FOCUSED_BOARDS and score >= 1:
        return RelevanceResult(
            is_relevant=True,
            score=score,
            reason="focused_board",
        )

    if board in BROAD_BOARDS and score >= 2:
        return RelevanceResult(
            is_relevant=True,
            score=score,
            reason="broad_board_with_domain_keyword",
        )

    if score >= 3:
        return RelevanceResult(
            is_relevant=True,
            score=score,
            reason="domain_keyword_match",
        )

    return RelevanceResult(
        is_relevant=False,
        score=score,
        reason="low_relevance_score",
    )


def is_relevant_article(article: dict) -> bool:
    return evaluate_article_relevance(article).is_relevant
