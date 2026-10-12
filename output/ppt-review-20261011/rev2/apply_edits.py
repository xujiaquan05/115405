"""第二輪修訂：依 10/12 的程式與資料狀態更新簡報，並重算收費與成本。

輸入 stage1.pptx（已複製出附錄 F 的空白頁），輸出 stage2.pptx。
只改文字內容、表格儲存格與圖表數據，沿用原檔字型、字級與版面。
"""
import copy
import sys

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.util import Inches, Pt

SRC, OUT = sys.argv[1], sys.argv[2]
p = Presentation(SRC)
S = lambda n: p.slides[n - 1]  # noqa: E731


def shape(slide, name=None, contains=None):
    for sh in slide.shapes:
        if name is not None and sh.name == name:
            return sh
        if contains is not None and sh.has_text_frame and contains in sh.text_frame.text:
            return sh
    raise KeyError(name or contains)


def set_lines(tf, lines):
    """逐段替換文字，保留每段第一個 run 的格式；段數不同時增刪段落。"""
    paras = tf.paragraphs
    while len(paras) < len(lines):
        tf._txBody.append(copy.deepcopy(paras[-1]._p))
        paras = tf.paragraphs
    for par, text in zip(paras, lines):
        runs = par.runs
        if not runs:  # 空段落（例如複製出來的頁沒有備忘稿）
            par.add_run()
            runs = par.runs
        runs[0].text = text
        for r in runs[1:]:
            r._r.getparent().remove(r._r)
    for par in paras[len(lines):]:
        par._p.getparent().remove(par._p)


def set_text(slide, lines, name=None, contains=None):
    set_lines(shape(slide, name, contains).text_frame, lines if isinstance(lines, list) else [lines])


def table(slide):
    return next(sh for sh in slide.shapes if sh.has_table).table


def set_cell(tbl, r, c, text):
    set_lines(tbl.cell(r, c).text_frame, [text])


def set_notes(slide, text):
    set_lines(slide.notes_slide.notes_text_frame, [text])


# ── 成本模型（全部由 measure_llm_cost.py 實測與官方單價推得） ──
FX = 32
QA = 0.06          # 元／次：輸入 8,963、輸出 2,150 token
INSIGHT = 0.10     # 元／次：輸入 14,341、輸出 4,519 token
PRO_PRICE, BIZ_PRICE = 490, 1990
PRO_VAR = round(100 * QA + 60 * INSIGHT + PRO_PRICE * 0.03)   # 27
PRO_GAIN = PRO_PRICE - PRO_VAR                                  # 463
FIXED = 1450       # Render US$44 → 1,408 + 網域 35 + 每日判讀 7
LABOR20, LABOR40 = 20 * 196, 40 * 196
ceil = lambda a, b: -(-a // b)  # noqa: E731
assert PRO_VAR == 27 and PRO_GAIN == 463
BE = [ceil(FIXED, PRO_GAIN), ceil(FIXED + LABOR20, PRO_GAIN), ceil(FIXED + LABOR40, PRO_GAIN)]
assert BE == [4, 12, 21], BE

# ── 第 1 頁：換上海報 1 的 MeBOD 標誌 ──
s = S(1)
for sh in list(s.shapes):
    if sh.shape_type == 13:  # 原本右上角的魔杖圖示
        sh._element.getparent().remove(sh._element)
shape(s, "Text 5").width = Inches(8.4)
logo = s.shapes.add_picture("mebod-mark.png", Inches(9.75), Inches(1.45), Inches(2.75), Inches(2.75))
logo.name = "MeBOD Logo"
# 柔和陰影，讓標誌從淺色底浮起來
spPr = logo._element.spPr
spPr.append(spPr.makeelement(
    "{http://schemas.openxmlformats.org/drawingml/2006/main}effectLst", {}))
eff = spPr[-1]
shdw = eff.makeelement("{http://schemas.openxmlformats.org/drawingml/2006/main}outerShdw",
                       {"blurRad": "381000", "dist": "152400", "dir": "5400000", "algn": "t", "rotWithShape": "0"})
clr = shdw.makeelement("{http://schemas.openxmlformats.org/drawingml/2006/main}srgbClr", {"val": "4F46E5"})
alpha = clr.makeelement("{http://schemas.openxmlformats.org/drawingml/2006/main}alpha", {"val": "28000"})
clr.append(alpha)
shdw.append(clr)
eff.append(shdw)

# ── 第 4 頁：權限缺口已修正 ──
set_cell(table(S(4)), 4, 2, "部署驗證、負載測試待補")

# ── 第 6 頁：收益來源與成本結構 ──
s = S(6)
set_text(s, ["免費／專業 490／企業 1,990", "月費皆為假設，待付費意願驗證"], name="Text 18")
set_text(s, ["雲端主機、資料庫、模型", "金流手續費、維運人力"], name="Text 30")
set_notes(s, "【陳威帆｜35 秒】九個區塊串起訂閱服務：小型團隊透過網頁整理口碑，我們維護收錄、分析與檢索，以方案額度區分免費、專業、企業三級。"
             "專業版 490、企業版 1,990 都是假設價格，系統已有方案額度但尚未串接收款。成本結構依下一頁實測重算：雲端主機與資料庫是主要固定支出，"
             "模型呼叫很便宜，金流手續費與維運人力反而是大頭。來源：backend/app/models/database_models.py（plans）；附錄 C、F。")

# ── 第 7 頁：成本重算 ──
s = S(7)
set_text(s, "成本重算：4 個專業版帳號可打平雲端支出", name="Text 2")
set_text(s, "0.06 元", name="Text 5")
set_text(s, "每次 AI 問答（保守上限）", name="Text 6")
set_text(s, "實測 prompt×官方單價", name="Text 7")
set_text(s, "27 元", name="Text 9")
set_text(s, "每位專業版用戶／月", name="Text 10")
set_text(s, "問答100、洞察60、金流3%", name="Text 11")
set_text(s, "1,450 元", name="Text 13")
set_text(s, "每月雲端固定支出", name="Text 14")
set_text(s, "主機、資料庫、網域、判讀", name="Text 15")
set_text(s, "4 帳號", name="Text 18")
set_text(s, "⌈1,450 ÷ (490 − 27)⌉", name="Text 19")
set_text(s, f"4 帳號每月餘額 {4 * PRO_GAIN - FIXED} 元", name="Text 20")
set_text(s, "新臺幣／月；官方單價查於 10/12（1 USD≈32 元）；未含人力，見附錄 C、F。", name="Text 24")
chart = next(sh for sh in s.shapes if sh.has_chart).chart
cd = CategoryChartData()
cd.categories = ["0", "2", "4", "6", "8", "10"]
cd.add_series("月收入", [PRO_PRICE * n for n in (0, 2, 4, 6, 8, 10)])
cd.add_series("月支出", [FIXED + PRO_VAR * n for n in (0, 2, 4, 6, 8, 10)])
chart.replace_data(cd)
chart.value_axis.maximum_scale = 5000
chart.value_axis.major_unit = 2500
set_notes(s, "【陳威帆｜45 秒】初評說我們沒有量化，這頁用實測重算，不再沿用原稿的假設單價。"
             "一次 AI 問答：用系統程式組出真實 prompt，最多約 9 千 token 輸入、2 千 token 輸出，以 Gemini 2.5 Flash-Lite 官方價每百萬 0.10／0.40 美元計算，約 0.06 元，"
             "原稿假設 0.33 元高估了五倍。專業版用戶每月 100 次問答、60 次洞察，加上 3% 金流手續費，變動成本約 27 元。"
             "固定支出以 render.yaml 的雲端部署計：主機 25 美元、資料庫 19 美元，加網域與每日判讀約 1,450 元。"
             "收入 490N、支出 1,450＋27N，4 個帳號就能打平，每月餘 402 元。但這還沒算人力，算進去要 12 到 21 個帳號，見附錄 C；每個數字的出處在附錄 F。")

# ── 第 9 頁 ──
set_text(S(9), "權限與額度皆在後端檢查；預警的查詢、已讀與即時檢查已依帳號隔離。", name="Text 25")
set_notes(S(9), "【許家全｜45 秒】Vue介面透過FastAPI存取PostgreSQL，服務層提供分析、檢索及匯出，另接Gemini和四平台收錄。現行ORM有18張表。"
                "權限一律在後端檢查；上一版列為缺口的預警已讀端點，已於10/12修正為只能操作自己的預警，並補上跨帳號測試。"
                "來源：backend/app/models/database_models.py、backend/app/routers/monitor.py、backend/tests/test_monitor_api.py。")

# ── 第 12 頁 ──
s = S(12)
set_text(s, "全庫 1.6 萬筆已改 temperature 0 重評；模型一致率不等於正確率，人工標註待補。", name="Text 20")
set_notes(s, "【許家全｜45 秒】兩種問題分開回答。第一，同一批100篇由另一模型Claude盲標，與目前report.txt結果82%一致，kappa0.726約0.73，負面precision18/27約0.67。"
             "第二，temperature從0.3改為0後，本批重跑變動從12篇降到0篇；10/06已用相同設定重評全庫10,344篇文章與6,319則留言。"
             "分數是50+(正面百分比−負面百分比)/2，例60%、10%得到75。比較須固定資料範圍與分母，分數不是療程成效。"
             "來源：docs/manual-work/sentiment-eval/report.txt、temp0_run1.txt、temp0_run2.txt；backend/app/routers/analysis.py。")

# ── 第 13 頁：缺口清單移除已修正項目 ──
s = S(13)
set_text(s, ["Linux 建置與部署驗證", "情緒準確度（人工標註）", "檢索相關性（固定題組）", "高負載與多使用者"], name="Text 11")
set_notes(s, "【許家全｜40 秒】系統完成度用已實作、待驗證及規劃三欄說明。未建立權重和驗收分母，不用百分比。"
             "上一版的預警已讀帳號隔離已修正並補測試；Linux部署、負載與模型品質仍需驗證。來源：backend/app/routers/monitor.py；各前端功能頁。")

# ── 第 14 頁 ──
s = S(14)
set_cell(table(s), 6, 2, "只能操作自己的預警")
set_notes(s, "【許家全｜35 秒】功能完整性從使用者流程檢查。從範圍設定、讀圖、問答回查，到歷史與匯出都有對應畫面與輸出。"
             "監測預警依帳號隔離，10/12 補上跨帳號測試。報告使用瀏覽器列印，不是獨立伺服器PDF生成。"
             "來源：frontend/src/views/DashboardView.vue、QAView.vue、HistoryView.vue、ReportView.vue、MonitorView.vue；backend/app/routers/monitor.py。")

# ── 第 16 頁：10/12 重跑並保存報告 ──
s = S(16)
set_text(s, "分層測試：每一層都有可核對的原始報告", contains="分層測試")
t = table(s)
set_cell(t, 3, 1, "493 通過、1 略過｜2026/10/12")
set_cell(t, 3, 2, "pytest-20261012.xml")
set_cell(t, 4, 1, "43 通過｜2026/10/12")
set_cell(t, 4, 2, "vitest-20261012.xml")
set_text(s, "單元／API 測試 10/12 重跑並保存 XML；PostgreSQL、E2E 為先前報告，不同日期不累加。", contains="以上為歷史紀錄")
set_notes(s, "【許家全｜35 秒】PostgreSQL10項可核對2026/10/03原始XML；E2E4項可核對2026/09/27 17:14的all-results.xml，較早一份曾有1項失敗，保留失敗歷程。"
             "後端pytest與前端Vitest已於10/12重跑：後端493通過、1略過，前端43通過，報告存於backend/.test-artifacts。"
             "高負載、人工標註與檢索題組尚待驗證。來源：backend/.test-artifacts/pytest-20261012.xml、vitest-20261012.xml、postgres-results.xml、all-results.xml。")

# ── 第 17 頁：GitHub 提交（含本次簡報修訂的提交） ──
s = S(17)
MONTHS = [14, 0, 27, 42, 47, 30]
chart = next(sh for sh in s.shapes if sh.has_chart).chart
cd = CategoryChartData()
cd.categories = ["5月", "6月", "7月", "8月", "9月", "10月"]
cd.add_series("提交數", MONTHS)
chart.replace_data(cd)
set_lines(chart.chart_title.text_frame, [f"GitHub 每月提交（共 {sum(MONTHS)} 次）"])
set_text(s, f"GitHub：7–10 月 {sum(MONTHS[2:])} 次提交（截至 10/12，皆已推送）；非逐人貢獻比例。", name="Text 50")
set_notes(s, "【陳威帆｜45 秒】甘特圖保留原稿115/2至116/1的計畫，10月後為計畫工作。繳件與展覽日期沿用原稿，發表前仍按學校公告確認。"
             f"提交數由GitHub遠端於2026/10/12確認：5月14、6月0、7月27、8月42、9月47、10月30，總{sum(MONTHS)}；7–10月{sum(MONTHS[2:])}，皆已推送。"
             "提交集中於單一帳號，不能當作兩位組員的貢獻比例。")

# ── 第 19 頁 ──
s = S(19)
set_text(s, ["人工標註驗證情緒", "固定題組測檢索品質", "業配辨識", "Linux 部署回歸驗證", "正式需求訪談"], name="Text 11")
set_notes(s, "【陳威帆｜105 秒】總結三點：一、四平台到問答與報告形成完整研究流程；二、RAG與分數規則已可說明，測試報告可核對；三、尚未把品質驗證說成全部完成。"
             "下一步依序補Linux部署回歸、建立人工標註和檢索題組、辨識業配，再與實際使用者訪談試用。"
             "營運上，實測重算後4個專業版帳號可打平雲端支出，算入人力則需12到21個。與通用代理的差異需要同題實測，現階段著重長期資料、來源回查與持續監測。結束於14:30，保留30秒緩衝。")

# ── 附錄 A、B ──
t = table(S(20))
set_cell(t, 1, 1, "p7 實測重算；附錄 C、F 明細")
set_cell(t, 1, 2, "實際帳單、付費意願、獲利時點")
t = table(S(21))
set_cell(t, 3, 1, "熱門話題只計 178 個醫美領域詞")
set_cell(t, 3, 2, "知識萃取、專家驗證")

# ── 附錄 C：人力敏感度 ──
s = S(22)
set_text(s, "附錄 C · 成本敏感度（加入人力）", contains="附錄 C")
set_text(s, "加入維運人力後，平衡帳號數變成 12～21 個", contains="人力成本納入後")
t = table(s)
set_cell(t, 0, 1, "月固定支出")
set_cell(t, 0, 2, "平衡專業版帳號數")
rows = [("雲端基本支出；未含人力", FIXED), (f"＋維運 20 小時（時薪 196）", FIXED + LABOR20), ("＋維運 40 小時（時薪 196）", FIXED + LABOR40)]
for i, (label, cost) in enumerate(rows, start=1):
    set_cell(t, i, 0, label)
    set_cell(t, i, 1, f"{cost:,}")
    set_cell(t, i, 2, f"⌈{cost:,} ÷ {PRO_GAIN}⌉ = {ceil(cost, PRO_GAIN)}")
set_text(s, f"每帳號月貢獻＝月費 490 − 變動成本 {PRO_VAR}＝{PRO_GAIN} 元", contains="每帳號月貢獻")
set_text(s, "1 個企業版（建議價 1,990）約抵 4 個專業版；仍未含開發回收與稅費。", contains="5,000／10,000")
set_notes(s, "備詢：人力以115年基本工資時薪196元計，每月20或40小時維運。"
             f"固定支出1,450＋3,920＝5,370，÷463取整為12；1,450＋7,840＝9,290，÷463取整為21。"
             "企業版建議價1,990為假設：重度使用者每月1,000次問答約60元、200次洞察約20元、金流3%約60元，貢獻約1,850元，約等於4個專業版。"
             "要回答何時獲利，還需實際帳單、獲客速度與開發投入，目前沒有可支持的日期。")

# ── 附錄 F：成本明細與來源（由附錄 C 複製而來） ──
s = S(25)
set_text(s, "附錄 F · 成本明細與來源", contains="附錄 C")
set_text(s, "每一個數字的算法與出處", contains="人力成本納入後")
for sh in list(s.shapes):
    if sh.has_text_frame and "每帳號月貢獻" in sh.text_frame.text:
        sh._element.getparent().remove(sh._element)
set_text(s, "中文以 1 字≈1 token 保守估算；匯率 32（央行 115/8/20 收盤 31.925）。", contains="5,000／10,000")
gf = next(sh for sh in s.shapes if sh.has_table)
t = gf.table
DETAIL = [
    ("項目", "計算", "依據"),
    ("AI 問答／次", "輸入 8,963＋輸出 2,150 token ≈ 0.06 元", "Gemini 官方價 0.10／0.40 美元／百萬 token"),
    ("儀表板洞察／次", "輸入 14,341＋輸出 4,519 token ≈ 0.10 元", "同上；輸出取已存 31 筆最大值"),
    ("每日收錄與判讀", "近 30 天 897 篇＋3,216 則 ≈ 6.3 元（計 7）", "實際收錄量；向量 US$0.15／百萬 token"),
    ("主機與網域", "US$25＋US$19 ≈ 1,408 元；網域 35 元", "Render 公開價；網域年費 420 元為假設"),
    ("金流手續費", "月費 × 3%（專業版約 15 元）", "假設值，待向金流商確認"),
    ("維運人力", "20／40 小時 × 196 元", "115 年基本工資時薪 196 元"),
]
tr_proto = t._tbl.tr_lst[-1]
while len(t._tbl.tr_lst) < len(DETAIL):
    t._tbl.append(copy.deepcopy(tr_proto))
widths = [Inches(2.45), Inches(4.75), Inches(4.53)]
for i, w in enumerate(widths):
    t.columns[i].width = w
for r, row in enumerate(DETAIL):
    t.rows[r].height = Inches(0.58)
    for c, text in enumerate(row):
        set_cell(t, r, c, text)
        for par in t.cell(r, c).text_frame.paragraphs:
            for run in par.runs:
                run.font.size = Pt(15 if r else 16)
gf.height = Inches(0.58 * len(DETAIL))
set_text(s, "25", name="22")
set_notes(s, "備詢：本頁列出第7頁與附錄C每個數字的算法。token數由backend/scripts/measure_llm_cost.py以系統實際組prompt的函式量測，不呼叫模型；"
             "中文以1字約1 token估算，英文與數字其實更省，結果偏高。Gemini單價查自ai.google.dev/gemini-api/docs/pricing（10/12）；"
             "embedding單價依Google開發者部落格公告；Render價格為第三方整理，正式採用前要以官網確認；金流3%為假設。")

p.save(OUT)
print("saved", OUT)
