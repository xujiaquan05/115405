# backend/app/services/llm_prompts.py


def build_overview_prompt(keyword: str, articles_context: str) -> str:
    """
    Note:
    Prompt phân tích tổng hợp.

    Mục tiêu:
    - Tóm tắt thị trường
    - Tìm chủ đề hot
    - Tìm pain points
    - Đưa ra marketing suggestions

    LLM bắt buộc trả JSON để backend dễ parse.
    """

    return f"""
你是一位醫美產業的輿情分析師。
請根據以下 PTT 文章資料，分析關鍵字「{keyword}」的網路討論狀況。

請務必只回傳 JSON，不要加入 markdown，不要加入額外說明。

JSON 格式如下：
{{
  "summary": "整體討論摘要，請用繁體中文，約 80-120 字",
  "hot_topics": [
    "熱門話題 1",
    "熱門話題 2",
    "熱門話題 3"
  ],
  "consumer_pain_points": [
    "消費者痛點 1",
    "消費者痛點 2",
    "消費者痛點 3"
  ],
  "positive_insights": [
    "正面觀察 1",
    "正面觀察 2"
  ],
  "negative_risks": [
    "負面風險 1",
    "負面風險 2"
  ],
  "marketing_suggestions": [
    "具體行銷建議 1",
    "具體行銷建議 2",
    "具體行銷建議 3"
  ]
}}

以下是文章資料：
{articles_context}
"""


def build_trend_prompt(keyword: str, articles_context: str) -> str:
    """
    Note:
    Prompt 分析趨勢。

    Mục tiêu:
    - Chủ đề nào đang lên
    - Chủ đề nào đang giảm
    - Dự đoán hướng phát triển
    """

    return f"""
你是一位醫美市場趨勢分析師。
請根據以下 PTT 文章資料，分析關鍵字「{keyword}」的討論趨勢。

請務必只回傳 JSON，不要加入 markdown，不要加入額外說明。

JSON 格式如下：
{{
  "trend_summary": "整體趨勢摘要，請用繁體中文，約 80-120 字",
  "rising_topics": [
    {{
      "topic": "上升中的話題",
      "reason": "為什麼判斷它在上升"
    }}
  ],
  "declining_topics": [
    {{
      "topic": "下降中的話題",
      "reason": "為什麼判斷它在下降"
    }}
  ],
  "future_prediction": "未來 1-2 個月可能的討論走向",
  "recommended_action": "給行銷人員的一句具體建議"
}}

以下是文章資料：
{articles_context}
"""


def build_sentiment_prompt(keyword: str, articles_context: str) -> str:
    """
    Note:
    Prompt 分析情緒與公關風險。

    Mục tiêu:
    - Sentiment score
    - Positive comments
    - Negative comments
    - Crisis warning
    """

    return f"""
你是一位醫美品牌公關與口碑分析師。
請根據以下 PTT 文章資料，分析關鍵字「{keyword}」的消費者情緒。

請務必只回傳 JSON，不要加入 markdown，不要加入額外說明。

JSON 格式如下：
{{
  "sentiment_score": 0,
  "sentiment_label": "positive / neutral / negative",
  "positive_reviews": [
    "具代表性的正面口碑 1",
    "具代表性的正面口碑 2"
  ],
  "negative_reviews": [
    "具代表性的負面口碑 1",
    "具代表性的負面口碑 2"
  ],
  "risk_level": "low / medium / high",
  "pr_warning": "是否需要公關危機處理，以及原因",
  "improvement_suggestions": [
    "改善建議 1",
    "改善建議 2"
  ]
}}

sentiment_score 請給 0 到 100 分：
0 代表非常負面，50 代表中性，100 代表非常正面。

以下是文章資料：
{articles_context}
"""


def build_prompt(
    analysis_type: str,
    keyword: str,
    articles_context: str,
) -> str:
    """
    Note:
    根據 analysis_type 選擇不同 prompt。

    analysis_type 支援:
    - overview
    - trend
    - sentiment
    """

    if analysis_type == "trend":
        return build_trend_prompt(keyword, articles_context)

    if analysis_type == "sentiment":
        return build_sentiment_prompt(keyword, articles_context)

    return build_overview_prompt(keyword, articles_context)