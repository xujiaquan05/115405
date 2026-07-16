# backend/app/services/llm_prompts.py
#
# 依「陳社長」初審建議優化的版本：
#   1. 每項輸出都要直覺好懂——讓不懂的人也知道「這項在看什麼、對我有什麼用」。
#   2. 行銷洞察要「分類」，不要一堆扁平條列。
#   3. 建議要可執行——看完要知道「做什麼 / 怎麼做 / 在哪裡做」。
#   4. 以 5W2H1E 拆解每一條建議，讓使用者真正看到「建議做法」。
#   5. 內容類建議要分平台寫法（FB / IG / Threads）並含長文 SEO / GEO 結構（H1, H2…）。
#
# 注意：本檔僅優化「送進 LLM 的提示詞與輸出 JSON 結構」。
#       因 marketing_suggestions / recommended_actions / improvement_actions 由「字串陣列」
#       改為「物件陣列」，前端顯示元件需同步調整欄位（詳見檔尾說明）。


# ──────────────────────────────────────────────────────────────
# 共用規範：所有建議都要遵守的「可執行 + 白話 + 5W2H1E」原則
# ──────────────────────────────────────────────────────────────
SUGGESTION_GUIDELINES = """
【建議撰寫原則｜務必全部遵守】
1. 白話可懂：用一般醫美業者也看得懂的話，避免術語；每一項都要讓不懂的人知道「這是什麼、對我有什麼用」。
2. 可執行：不要只給抽象方向（例如「加強社群經營」），要具體到「做什麼、怎麼做、在哪裡做」。
3. 每一條建議都用 5W2H1E 拆解，對應到下方 JSON 欄位：
   - what（做什麼）、why（為何做，對應哪個痛點/訊號）、who（誰來做）、where（在哪個管道做）、
     when（何時做/頻率）、how（怎麼做的具體步驟）、how_much（預估投入）、expected_effect（預期成效）。
4. 內容類建議（發文、寫文章）必須在 how/where 寫清楚平台寫法：
   - FB：可長文、適合情境故事與衛教，文末放 CTA 與連結。
   - IG：以圖卡/限動為主，重視覺、精簡文案，搭配 5–10 個相關 hashtag。
   - Threads：短句、口語、拋問題引互動，避免硬廣。
   - 長文（官網部落格 / 醫師專欄）：須符合 SEO/GEO 結構——明確 H1 主標題，H2/H3 分段，
     自然佈局關鍵字，段落簡短、可被搜尋引擎與 AI 摘要引用。
5. 保守誠實：資料不足以支撐的建議寧可不寫，禁止杜撰數據或療效宣稱。
6. 法遵提醒：醫美屬醫療廣告管制領域，建議只談「行銷/溝通方向」，不得出現療效保證或誇大宣傳字眼。
"""

# 共用：強制只回傳 JSON，方便後端 parse
JSON_RULE = "請務必只回傳合法 JSON，不要加入 markdown 標記，不要加入任何額外說明文字。"


# ──────────────────────────────────────────────────────────────
# 1. 總覽分析（市場摘要 + 熱門話題 + 痛點 + 可執行行銷建議）
# ──────────────────────────────────────────────────────────────
def build_overview_prompt(keyword: str, articles_context: str) -> str:
    """
    總覽分析提示詞。

    目標：
    - 摘要整體市場討論
    - 找出熱門話題與消費者痛點
    - 產出「分類化 + 5W2H1E」的可執行行銷建議（本次優化重點）

    LLM 必須只回傳 JSON，方便後端解析。
    """

    schema = """
{
  "summary": "整體討論摘要，繁體中文、約 80–120 字，用白話讓非專業者也看得懂",
  "hot_topics": [
    {
      "topic": "熱門話題名稱",
      "meaning": "用一句白話說明這個話題在紅什麼、代表消費者在關心什麼"
    }
  ],
  "consumer_pain_points": [
    {
      "pain_point": "消費者痛點",
      "meaning": "用一句白話說明這個痛點為什麼重要、業者可以從中看到什麼"
    }
  ],
  "positive_insights": [
    "正面觀察（業者可放大的優勢，白話一句）"
  ],
  "negative_risks": [
    "負面風險（業者要留意或避免的點，白話一句）"
  ],
  "marketing_suggestions": [
    {
      "category": "建議分類，擇一：內容行銷 / 社群經營 / SEO・GEO / 口碑經營 / 廣告投放 / 服務流程",
      "title": "一句話的建議標題，白話好懂",
      "based_on": "這條建議是根據哪個話題或痛點而來（讓人知道為什麼要做）",
      "what": "要做什麼（具體行動）",
      "why": "為什麼要做（對應的市場訊號或痛點）",
      "who": "建議由誰執行：小編 / 行銷企劃 / 醫師 / 客服 之一",
      "where": "在哪裡做：FB / IG / Threads / 官網部落格 / Google 商家 / LINE（可多選）",
      "when": "建議時機或頻率，例如『每週 2–3 篇』『諮詢旺季前 1 個月』",
      "how": "怎麼做的具體步驟；若為內容類，請寫明平台寫法與（長文）H1/H2 結構",
      "how_much": "預估投入（時間 / 人力 / 預算的粗估即可）",
      "expected_effect": "預期成效，盡量用可衡量指標，例如『提升相關貼文互動率』『增加官網自然搜尋曝光』"
    }
  ]
}
"""

    example = """
marketing_suggestions 範例（請依實際資料產出，至少 3 筆，且分屬不同 category，
其中至少 1 筆為「內容行銷」或「SEO・GEO」並寫出平台寫法/H1H2 結構）：
{
  "category": "SEO・GEO",
  "title": "針對熱門療程寫一篇衛教長文搶 Google 與 AI 摘要",
  "based_on": "熱門話題：消費者反覆詢問某療程的恢復期與風險",
  "what": "撰寫一篇『該療程術後恢復懶人包』長文",
  "why": "討論顯示大家最在意恢復期與副作用，搜尋需求高但缺乏可信來源",
  "who": "行銷企劃撰稿、醫師審稿",
  "where": "官網部落格 / 醫師專欄",
  "when": "兩週內完成首篇，之後每月 1 篇",
  "how": "用 H1 放主關鍵字（如『XX療程 恢復期』），H2 分『術後第幾天』『常見副作用』『何時回診』；段落簡短、自然帶關鍵字，文末附諮詢 CTA",
  "how_much": "約 1 人 2 個工作天",
  "expected_effect": "提升該關鍵字的自然搜尋排名與 AI 問答被引用機率，帶動諮詢表單填寫"
}
"""

    return f"""你是一位資深的醫美產業輿情分析師，也是行銷顧問。
請根據以下 PTT 文章資料，分析關鍵字「{keyword}」的網路討論狀況，
並產出「讓業者看完就知道接下來怎麼做」的可執行建議。
{SUGGESTION_GUIDELINES}
{JSON_RULE}

JSON 格式如下：
{schema}
{example}

以下是文章資料：
{articles_context}
"""


# ──────────────────────────────────────────────────────────────
# 2. 趨勢分析（上升/下降話題 + 預測 + 可執行行動）
# ──────────────────────────────────────────────────────────────
def build_trend_prompt(keyword: str, articles_context: str) -> str:
    """
    趨勢分析提示詞。

    目標：
    - 哪些話題在上升、哪些在下降
    - 預測未來走向
    - 將「下一步行動」由一句話升級為可執行建議（本次優化重點）
    """

    schema = """
{
  "trend_summary": "整體趨勢摘要，繁體中文、約 80–120 字，白話好懂",
  "rising_topics": [
    {
      "topic": "上升中的話題",
      "reason": "為什麼判斷它在上升",
      "meaning": "對業者代表的意義（白話一句，可切入的機會）"
    }
  ],
  "declining_topics": [
    {
      "topic": "下降中的話題",
      "reason": "為什麼判斷它在下降",
      "meaning": "對業者代表的意義（白話一句，要不要減少投入）"
    }
  ],
  "future_prediction": "未來 1–2 個月可能的討論走向",
  "recommended_actions": [
    {
      "category": "建議分類：內容行銷 / 社群經營 / SEO・GEO / 廣告投放 / 服務流程 之一",
      "title": "一句話的行動標題，白話好懂",
      "based_on": "對應哪個上升/下降趨勢",
      "what": "要做什麼",
      "where": "在哪裡做：FB / IG / Threads / 官網部落格 / Google / LINE",
      "how": "怎麼做的具體步驟；內容類請寫平台寫法與長文 H1/H2 結構",
      "when": "建議時機或頻率",
      "expected_effect": "預期成效（盡量可衡量）"
    }
  ]
}
"""

    return f"""你是一位醫美市場趨勢分析師，也是行銷顧問。
請根據以下 PTT 文章資料，分析關鍵字「{keyword}」的討論趨勢，
並把「下一步該做什麼」寫成業者可以直接照做的建議。
{SUGGESTION_GUIDELINES}
{JSON_RULE}

JSON 格式如下：
{schema}

以下是文章資料：
{articles_context}
"""


# ──────────────────────────────────────────────────────────────
# 3. 情緒與公關風險分析（情緒分數 + 口碑 + 危機 + 可執行改善）
# ──────────────────────────────────────────────────────────────
def build_sentiment_prompt(keyword: str, articles_context: str) -> str:
    """
    情緒與公關風險分析提示詞。

    目標：
    - 情緒分數與標籤
    - 代表性正/負面口碑
    - 公關危機警示
    - 將「改善建議」由字串升級為可執行行動（本次優化重點）
    """

    schema = """
{
  "sentiment_score": 0,
  "sentiment_label": "positive / neutral / negative",
  "score_explanation": "用一句白話解釋這個分數代表什麼，讓非專業者看得懂",
  "positive_reviews": [
    "具代表性的正面口碑（可改寫摘要，不需逐字照抄）"
  ],
  "negative_reviews": [
    "具代表性的負面口碑（可改寫摘要，不需逐字照抄）"
  ],
  "risk_level": "low / medium / high",
  "pr_warning": "是否需要公關危機處理，以及原因（白話說明）",
  "improvement_actions": [
    {
      "category": "建議分類：口碑經營 / 內容行銷 / 社群經營 / 服務流程 之一",
      "title": "一句話的改善行動標題，白話好懂",
      "based_on": "對應哪一類負評或風險",
      "what": "要做什麼",
      "who": "建議由誰執行：客服 / 行銷企劃 / 醫師 / 小編",
      "where": "在哪裡做：FB / IG / Threads / 官網 / Google 評論 / LINE",
      "how": "怎麼做的具體步驟；若為對外發文請寫平台寫法（語氣、格式）",
      "when": "建議時機或頻率（危機類請標明『立即』）",
      "expected_effect": "預期成效，例如『降低負面聲量』『提升回覆即時性』"
    }
  ]
}
"""

    return f"""你是一位醫美品牌的公關與口碑分析師。
請根據以下 PTT 文章資料，分析關鍵字「{keyword}」的消費者情緒與公關風險，
並把改善建議寫成可以直接執行的行動。
{SUGGESTION_GUIDELINES}
{JSON_RULE}

sentiment_score 請給 0 到 100 分：0 代表非常負面，50 代表中性，100 代表非常正面。

JSON 格式如下：
{schema}

以下是文章資料：
{articles_context}
"""


# ──────────────────────────────────────────────────────────────
# 4. 依 analysis_type 派發對應的 prompt（介面不變，後端可直接沿用）
# ──────────────────────────────────────────────────────────────
def build_prompt(
    analysis_type: str,
    keyword: str,
    articles_context: str,
) -> str:
    """
    依 analysis_type 選擇不同 prompt。

    支援的 analysis_type：
    - overview（預設）
    - trend
    - sentiment
    """

    if analysis_type == "trend":
        return build_trend_prompt(keyword, articles_context)

    if analysis_type == "sentiment":
        return build_sentiment_prompt(keyword, articles_context)

    return build_overview_prompt(keyword, articles_context)


# ──────────────────────────────────────────────────────────────
# 前端／後端對接提醒（本次結構變更）
# ──────────────────────────────────────────────────────────────
# 下列欄位由「字串陣列」改為「物件陣列」，前端顯示元件需同步調整：
#   - overview.marketing_suggestions : 物件含 category/title/based_on/what/why/who/where/when/how/how_much/expected_effect
#   - trend.recommended_action  → 改名 trend.recommended_actions（物件陣列）
#   - sentiment.improvement_suggestions → 改名 sentiment.improvement_actions（物件陣列）
# 另新增的說明性欄位（hot_topics[].meaning、score_explanation 等）可直接顯示，
# 讓不熟術語的使用者也看得懂每一項在表達什麼。
# 建議前端用「卡片」呈現每條建議：標題 + 分類標籤，展開後顯示 5W2H1E 細節。
