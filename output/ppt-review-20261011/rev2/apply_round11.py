"""第十一輪：系統正式改用 Gemini 3.1 Flash-Lite 後，同步附錄與備忘稿。

- 附錄 C、F 改用第 7 頁的新數字（貢獻 437 元、人力情境 13～22 個、單價 0.25／1.50）。
- 第 6、7、18 頁備忘稿更新成本說法與測試數。
- 資料表數 18 → 19（新增 qa_conversations：AI 問答對話依帳號保存）。
- 第 15 頁備忘稿補充：Dashboard 開啟為空白、示範請用專業版或管理員帳號。

輸入 stage10.pptx，輸出 stage11.pptx。
"""
import math
import sys

from pptx import Presentation

SRC, OUT = sys.argv[1], sys.argv[2]
p = Presentation(SRC)

RATE, IN_PRICE, OUT_PRICE = 32, 0.25, 1.50


def cost(tokens_in, tokens_out):
    return (tokens_in * IN_PRICE + tokens_out * OUT_PRICE) / 1e6 * RATE


QA, INSIGHT = cost(9_794, 2_150), cost(14_341, 4_519)
JUDGE_RAW = cost(500_000, 123_000) + 2.6
FIXED = 1_408 + 35 + math.ceil(JUDGE_RAW)
VARIABLE = round(100 * QA) + round(60 * INSIGHT) + round(490 * 0.03)
MARGIN = 490 - VARIABLE
LABOR = [(h, FIXED + h * 196) for h in (20, 40)]
BE = [math.ceil(FIXED / MARGIN)] + [math.ceil(f / MARGIN) for _, f in LABOR]
assert (FIXED, VARIABLE, MARGIN, BE) == (1456, 53, 437, [4, 13, 22]), (FIXED, VARIABLE, MARGIN, BE)
ENT_QA, ENT_INS, ENT_FEE = round(1000 * QA), round(200 * INSIGHT), round(1990 * 0.03)
ENT_CONTRIB = 1990 - ENT_QA - ENT_INS - ENT_FEE


def slide(n):
    return p.slides[n - 1]


def set_text(frame, text):
    """只改第一個 run 的文字並刪除其餘 run，保留原本字型與顏色。"""
    paras = frame.paragraphs
    par = paras[0]
    par.runs[0].text = text
    for r in par.runs[1:]:
        r._r.getparent().remove(r._r)
    for extra in paras[1:]:
        extra._p.getparent().remove(extra._p)


def replace_in_slide(n, old, new):
    """在一頁的文字框與表格中，把含 old 的那段整段換成 new。"""
    hits = 0
    for sh in slide(n).shapes:
        frames = []
        if sh.has_text_frame:
            frames.append(sh.text_frame)
        if sh.has_table:
            frames += [c.text_frame for row in sh.table.rows for c in row.cells]
        for tf in frames:
            if tf.text == old:
                set_text(tf, new)
                hits += 1
    assert hits == 1, (n, old, hits)


def replace_notes(n, pairs):
    tf = slide(n).notes_slide.notes_text_frame
    text = tf.text
    for old, new in pairs:
        assert old in text, (n, old)
        text = text.replace(old, new)
    set_text(tf, text)


# ── 資料表數 18 → 19 ─────────────────────────────────
replace_in_slide(4, "四平台、18 張表、分層測試紀錄", "四平台、19 張表、分層測試紀錄")
replace_in_slide(9, "18 張表・Alembic 遷移", "19 張表・Alembic 遷移")
# 第 10 頁「入庫」卡片是兩段文字，只改第一段。
hits = [sh for sh in slide(10).shapes if sh.has_text_frame and sh.text_frame.text.startswith("18 張資料表")]
assert len(hits) == 1
hits[0].text_frame.paragraphs[0].runs[0].text = "19 張資料表"
replace_notes(9, [
    ("現行ORM有18張表。", "現行ORM有19張表，10/18新增qa_conversations，AI問答對話改存資料庫並依帳號隔離。"),
])

# ── 第 6 頁備忘稿：模型費用已不是「很便宜」可帶過 ─────────
replace_notes(6, [
    ("成本結構依下一頁實測重算：雲端主機與資料庫是主要固定支出，模型呼叫很便宜，金流手續費與維運人力反而是大頭。",
     f"成本結構依下一頁實測重算：雲端主機與資料庫是主要固定支出；每位專業版用戶每月模型費用約 "
     f"{round(100 * QA) + round(60 * INSIGHT)} 元，加金流手續費約 {round(490 * 0.03)} 元，變動成本約 {VARIABLE} 元；"
     "維運人力則是最大的隱藏成本。"),
])

# ── 第 7 頁備忘稿：說明思考等級 ─────────────────────────
replace_notes(7, [
    ("以 Gemini 3.1 Flash-Lite 官方價每百萬 0.25／1.50 美元計算",
     "系統已改用 Gemini 3.1 Flash-Lite，思考等級設為 minimal，以官方價每百萬 0.25／1.50 美元計算"),
])

# ── 第 15 頁備忘稿：Demo 前提 ──────────────────────────
replace_notes(15, [
    ("預先登入正確帳號並備妥兩筆歷史。",
     "預先以專業版或管理員帳號登入並備妥兩筆歷史；Dashboard 開啟時為空白，需先輸入關鍵字再搜尋，"
     "訪客與免費版只能查近 7 天。"),
])

# ── 第 18 頁備忘稿：測試數與人力情境 ─────────────────────
replace_notes(18, [
    ("後端498項、前端43項自動化測試通過", "後端522項、前端47項自動化測試通過"),
    ("算入人力則需12到21個", f"算入人力則需{BE[1]}到{BE[2]}個"),
])

# ── 附錄 C ───────────────────────────────────────────
replace_in_slide(21, "附錄 C｜加入維運人力後，平衡帳號數變成 12～21 個",
                 f"附錄 C｜加入維運人力後，平衡帳號數變成 {BE[1]}～{BE[2]} 個")
replace_in_slide(21, "1,450", f"{FIXED:,}")
replace_in_slide(21, "⌈1,450 ÷ 463⌉ = 4", f"⌈{FIXED:,} ÷ {MARGIN}⌉ = {BE[0]}")
replace_in_slide(21, "5,370", f"{LABOR[0][1]:,}")
replace_in_slide(21, "⌈5,370 ÷ 463⌉ = 12", f"⌈{LABOR[0][1]:,} ÷ {MARGIN}⌉ = {BE[1]}")
replace_in_slide(21, "9,290", f"{LABOR[1][1]:,}")
replace_in_slide(21, "⌈9,290 ÷ 463⌉ = 21", f"⌈{LABOR[1][1]:,} ÷ {MARGIN}⌉ = {BE[2]}")
replace_in_slide(21, "每帳號月貢獻＝月費 490 − 變動成本 27＝463 元", f"每帳號月貢獻＝月費 490 − 變動成本 {VARIABLE}＝{MARGIN} 元")
set_text(slide(21).notes_slide.notes_text_frame,
         f"備詢：人力以115年基本工資時薪196元計，每月20或40小時維運。固定支出{FIXED:,}＋3,920＝{LABOR[0][1]:,}，"
         f"÷{MARGIN}取整為{BE[1]}；{FIXED:,}＋7,840＝{LABOR[1][1]:,}，÷{MARGIN}取整為{BE[2]}。"
         f"企業版建議價1,990為假設：重度使用者每月1,000次問答約{ENT_QA}元、200次洞察約{ENT_INS}元、金流3%約{ENT_FEE}元，"
         f"貢獻約{ENT_CONTRIB:,}元，約等於{ENT_CONTRIB / MARGIN:.1f}個專業版。"
         "要回答何時獲利，還需實際帳單、獲客速度與開發投入，目前沒有可支持的日期。")

# ── 附錄 F ───────────────────────────────────────────
replace_in_slide(24, "兩次呼叫：輸入 9,794＋輸出 2,150 ≈ 0.06 元", f"兩次呼叫：輸入 9,794＋輸出 2,150 ≈ {QA:.2f} 元")
replace_in_slide(24, "Gemini 官方價 0.10／0.40 美元／百萬 token",
                 "Gemini 3.1 Flash-Lite 0.25／1.50 美元／百萬 token；思考等級 minimal")
replace_in_slide(24, "輸入 14,341＋輸出 4,519 token ≈ 0.10 元", f"輸入 14,341＋輸出 4,519 token ≈ {INSIGHT:.2f} 元")
replace_in_slide(24, "近 30 天 897 篇＋3,216 則 ≈ 6.3 元（計 7）",
                 f"近 30 天 897 篇＋3,216 則 ≈ {JUDGE_RAW:.1f} 元（計 {math.ceil(JUDGE_RAW)}）")
replace_notes(24, [
    ("Gemini單價查自ai.google.dev/gemini-api/docs/pricing（10/12）",
     "Gemini 3.1 Flash-Lite單價查自ai.google.dev/gemini-api/docs/pricing（10/18）；思考token依輸出計價，系統設為minimal"),
])

p.save(OUT)
print("ok", FIXED, VARIABLE, MARGIN, BE, ENT_CONTRIB)
