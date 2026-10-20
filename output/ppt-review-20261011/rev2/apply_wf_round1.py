"""工作流程與問答版（31 頁）第一輪修正。

依 115/10/20 檢查結果修正：
- 主講人以第 2 頁為準：第 1–3 部分陳威帆、第 4 部分許家全；備忘稿標記同步。
- 第 2 頁議程補上「商業模式、成本」與第 16 頁「初評修正」（該頁本來就是第 3 部分第一頁）。
- 第 22 頁 GitHub 數字：166 次是 5–10 月合計（10/12 統計），不是 7–10 月。
- 第 22–24 頁備忘稿換成許家全的完整講稿，內容對齊第 24 頁的「下一步」與最新測試數。
- 第 7、10、30 頁備忘稿殘留的舊說法。
- 第 8、20、21 頁的橘色粗框卡片改回一般卡片（白底、1pt 淺灰藍框）。

用法：python apply_wf_round1.py in.pptx out.pptx
"""
import copy
import sys

from lxml import etree
from pptx import Presentation
from pptx.oxml.ns import qn

SRC, OUT = sys.argv[1], sys.argv[2]
p = Presentation(SRC)


def slide(n):
    return p.slides[n - 1]


def shape(n, shape_id):
    for sh in slide(n).shapes:
        if sh.shape_id == shape_id:
            return sh
    raise KeyError((n, shape_id))


def set_lines(sh, lines, expect=None):
    """改寫文字框，每行一段；沿用第一段第一個 run 的格式。"""
    tf = sh.text_frame
    if expect is not None:
        assert tf.text == expect, (sh.shape_id, tf.text)
    first = tf.paragraphs[0]
    for extra in tf.paragraphs[1:]:
        extra._p.getparent().remove(extra._p)
    for r in first.runs[1:]:
        r._r.getparent().remove(r._r)
    template = copy.deepcopy(first._p)
    first.runs[0].text = lines[0]
    anchor = first._p
    for _ in lines[1:]:
        new_p = copy.deepcopy(template)
        anchor.addnext(new_p)
        anchor = new_p
    for para, text in zip(tf.paragraphs, lines):
        para.runs[0].text = text


def notes(n):
    return slide(n).notes_slide.notes_text_frame


def set_notes(n, paragraphs):
    tf = notes(n)
    first = tf.paragraphs[0]
    for extra in tf.paragraphs[1:]:
        extra._p.getparent().remove(extra._p)
    for r in first.runs[1:]:
        r._r.getparent().remove(r._r)
    template = copy.deepcopy(first._p)
    anchor = first._p
    for _ in paragraphs[1:]:
        new_p = copy.deepcopy(template)
        anchor.addnext(new_p)
        anchor = new_p
    for para, text in zip(tf.paragraphs, paragraphs):
        para.runs[0].text = text
    assert [para.text for para in tf.paragraphs] == paragraphs, n


def replace_notes(n, pairs):
    text = notes(n).text
    for old, new in pairs:
        assert old in text, (n, old)
        text = text.replace(old, new)
    set_notes(n, text.split("\n"))


# ── 第 2 頁：議程 ─────────────────────────────────────
set_lines(shape(2, 9), ["問題、工作流程、資料蒐集", "使用者、專業度、SWOT", "商業模式、成本"],
          expect="問題、工作流程、資料蒐集\n使用者、專業度、SWOT")
set_lines(shape(2, 23), ["初評修正、完成度、Demo", "成果與困難、跨產業"],
          expect="完成度、Demo\n成果與困難、跨產業")
set_notes(2, ["【陳威帆｜15 秒】先談問題、工作流程、資料與營運，再說明技術、初評修正、完成度與 Demo，"
              "最後由家全報告進度、分工與結論；附錄供問答使用。"])

# ── 主講人標記：第 1–3 部分（第 3–21 頁）為陳威帆 ────────────
for n in (12, 13, 15, 17, 18, 19):
    text = notes(n).text
    assert text.startswith("【許家全｜"), (n, text[:10])
    replace_notes(n, [("【許家全｜", "【陳威帆｜")])

# ── 第 7、10、30 頁備忘稿 ───────────────────────────────
replace_notes(7, [("需求交流依初評口頭報告，正式訪談紀錄待補。",
                   "需求來自雜誌社社長交流：4/22 電話、4/28 面談、5/12 看過前期系統後回饋；正式訪談紀錄仍待補。")])
replace_notes(10, [("以方案額度區分免費、專業、企業三級。專業版 490、企業版 1,990 都是假設價格，",
                    "以方案額度區分免費與付費方案。專業版 490 元是假設價格，")])
replace_notes(30, [("本頁列出第7頁與附錄C", "本頁列出第11頁與附錄C")])

# ── 第 22 頁：GitHub 數字 ──────────────────────────────
set_lines(shape(22, 53), ["GitHub：5–10 月 166 次提交（10/12 統計）。"],
          expect="GitHub：7–10 月 166 次提交（10/11 統計）。")

# ── 第 22–24 頁：第 4 部分改由許家全主講 ───────────────────
set_notes(22, [
    "【許家全｜45 秒】",
    "接下來由我說明進度管理與後續規劃。",
    "初評時老師提醒甘特圖要用實際年月，所以這頁從 115 年 2 月排到 116 年 1 月，分成起始、精化、建構、移轉四個階段，"
    "目前正在移轉階段。上方標出四個查核點：6 月 2 日初審、10 月 13 日複審繳件、11 月 25 日觀摩展，以及 12 月 29 日最終版。",
    "左邊是 GitHub 每月提交數，5 月到 10 月共 166 次；右邊是各月份第一次完成的功能：5 月 PTT 爬蟲與儀表板，"
    "7 月帳號與權限，8 月擴充到 Dcard、Mobile01、Threads，9 月加入方案額度、資料庫遷移與向量檢索，"
    "10 月則完成情緒一致性與問答修正。",
    "來源：GitHub 提交紀錄（10/12 統計：5 月 14、6 月 0、7 月 27、8 月 42、9 月 47、10 月 36）。",
])
set_notes(23, [
    "【許家全｜30 秒】",
    "分工上，組長威帆負責需求企劃與雜誌社交流，以及成本、STP、SWOT 等營運計畫，並統整系統手冊第 1 到 6 章與簡報。",
    "我負責系統架構、資料庫與 FastAPI 後端，四平台爬蟲和每日排程，AI 問答、情緒評分與向量檢索，"
    "也包含前端介面、測試，以及手冊第 7 到 12 章。",
    "另外說明，程式提交集中在單一帳號，所以提交次數不能直接當作兩個人的貢獻比例。",
    "來源：使用者原稿第 16 頁工作分配；本機 Git 提交歷史。",
])
set_notes(24, [
    "【許家全｜100 秒】",
    "最後做個總結。",
    "已經完成的：系統每天自動收錄四個平台的討論；AI 問答用關鍵字加向量的混合檢索，每個回答都附引用來源；"
    "情緒評分有 100 篇重跑的一致性紀錄；帳號、方案額度與監測預警都在後端檢查，目前後端 528 項、前端 47 項自動化測試全部通過；"
    "營運面也做了成本試算、STP 與 SWOT，4 個專業版帳號就能打平每月約 1,456 元的雲端支出。",
    "接下來有五件事：第一，建立人工標註，驗證情緒判讀的準確度；第二，用固定題組評估檢索品質；"
    "第三，建立專人審查流程，並逐步補上療程知識庫；第四，和雜誌社社長合作，建立他們公司的專屬版本；"
    "第五，把領域設定抽成設定檔，先拿保養品這類相近產業試做。",
    "至於通用 AI 代理：它確實能自己搜尋、整理資料，我們不宣稱一定比它好。MeBOD 的定位是長期累積的歷史資料、"
    "每個回答都能回查原文，以及依帳號持續監測與預警。",
    "以上是我們的報告，謝謝老師，敬請指教。",
    "備註：測試數為 10/20 統計（後端 528 項通過、1 項略過；前端 47 項）。",
])

# ── 第 8、20、21 頁：橘色粗框改回一般卡片 ───────────────────
for n, shape_id in ((8, 8), (20, 23), (21, 7)):
    spPr = shape(n, shape_id)._element.find(qn("p:spPr"))
    ln = spPr.find(qn("a:ln"))
    assert ln.find(".//" + qn("a:srgbClr")).get("val") == "D46A12", (n, shape_id)
    ln.set("w", "12700")
    fill = ln.find(qn("a:solidFill"))
    for child in list(fill):
        fill.remove(child)
    etree.SubElement(fill, qn("a:srgbClr"), val="D3DEEA")

p.save(OUT)
print("ok")
