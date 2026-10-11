"""把系統簡介內容填入學校的 115 年系統簡介範本。

保留範本的版面、字型、標題編號與頁尾，只替換文字：
  - 刪除標題旁的紅字括號提示（範本要求交件前刪除）
  - 填入組別、專題名稱、指導教師、專題學生
  - 七個章節的「內文」換成實際內容，必要處加入表格

用法：
    python docs\\intro-work\\build_intro.py 範本.docx 輸出.docx
"""
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

SRC, OUT = Path(sys.argv[1]), Path(sys.argv[2])

BODY_FONT = '<w:rFonts w:ascii="Times New Roman" w:eastAsia="標楷體" w:hAnsi="Times New Roman"/>'
SZ = 24  # 內文 12 號
TABLE_SZ = 21  # 表格 10.5 號


def run(text: str, bold: bool = False, size: int = SZ) -> str:
    b = "<w:b/>" if bold else ""
    return (f'<w:r><w:rPr>{BODY_FONT}{b}<w:sz w:val="{size}"/><w:szCs w:val="{size}"/></w:rPr>'
            f'<w:t xml:space="preserve">{escape(text)}</w:t></w:r>')


def rich(text: str, size: int = SZ) -> str:
    """**粗體** 標記轉成粗體 run。"""
    parts = re.split(r"(\*\*.+?\*\*)", text)
    return "".join(run(p[2:-2], True, size) if p.startswith("**") else run(p, False, size) for p in parts if p)


def body(text: str, first_indent: bool = True) -> str:
    """與範本「內文」相同的段落格式。"""
    ind = '<w:ind w:left="482" w:firstLineChars="200" w:firstLine="480"/>' if first_indent else '<w:ind w:left="482"/>'
    return ('<w:p><w:pPr><w:pStyle w:val="a9"/><w:snapToGrid w:val="0"/><w:spacing w:line="290" w:lineRule="auto"/>'
            f'{ind}<w:jc w:val="both"/></w:pPr>{rich(text)}</w:p>')


def item(label: str, text: str) -> str:
    """條列：以「1.」等編號懸掛縮排。"""
    return ('<w:p><w:pPr><w:pStyle w:val="a9"/><w:snapToGrid w:val="0"/><w:spacing w:line="290" w:lineRule="auto"/>'
            '<w:ind w:left="842" w:hanging="360"/><w:jc w:val="both"/></w:pPr>'
            f'{run(label + " ")}{rich(text)}</w:p>')


def table(headers: list[str], rows: list[list[str]], widths: list[int]) -> str:
    """細框線表格，標題列淺灰底。寬度單位 DXA，總寬配合版心內縮。"""
    border = '<w:{0} w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
    borders = "".join(border.format(k) for k in ("top", "left", "bottom", "right", "insideH", "insideV"))
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)

    def cell(text: str, w: int, head: bool) -> str:
        shade = '<w:shd w:val="clear" w:color="auto" w:fill="E7E6E6"/>' if head else ""
        return (f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/>{shade}<w:vAlign w:val="center"/></w:tcPr>'
                '<w:p><w:pPr><w:snapToGrid w:val="0"/><w:spacing w:before="20" w:after="20" w:line="280" w:lineRule="auto"/>'
                f'{"<w:jc w:val=\"center\"/>" if head else ""}</w:pPr>{rich(f"**{text}**" if head else text, TABLE_SZ)}</w:p></w:tc>')

    out = [f'<w:tbl><w:tblPr><w:tblW w:w="{sum(widths)}" w:type="dxa"/><w:tblInd w:w="482" w:type="dxa"/>'
           f'<w:tblBorders>{borders}</w:tblBorders><w:tblLayout w:type="fixed"/>'
           '<w:tblCellMar><w:left w:w="80" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar></w:tblPr>'
           f'<w:tblGrid>{grid}</w:tblGrid>']
    out.append('<w:tr><w:trPr><w:tblHeader/></w:trPr>' + "".join(cell(h, w, True) for h, w in zip(headers, widths)) + "</w:tr>")
    for r in rows:
        out.append("<w:tr>" + "".join(cell(c, w, False) for c, w in zip(r, widths)) + "</w:tr>")
    out.append("</w:tbl>")
    # 表格後留一點間距
    out.append('<w:p><w:pPr><w:spacing w:line="120" w:lineRule="exact"/></w:pPr></w:p>')
    return "".join(out)


W = 10466 - 482  # A4 寬減左右邊界（720×2）再扣左縮排

SECTIONS = {
    "前言": [
        body("醫美與保養的消費決策高度依賴社群口碑。PTT、Dcard、Mobile01 與 Threads 每天都有大量療程心得與產品討論，"
             "但資料分散、格式不一，行銷人員只能逐站搜尋、人工整理，關鍵的負面聲量也容易被淹沒；"
             "直接詢問 ChatGPT、Gemini 等通用 AI，又難以指定平台與期間，答案缺少可回查的原文。"),
        body("本專題開發 **MeBOD 醫美時尚輿情分析系統**，自動蒐集四個平台的公開討論，經過領域篩選、情緒判讀與語意切段後，"
             "以儀表板呈現聲量、情緒與熱門話題，並以混合檢索（RAG）提供**附原文出處**的 AI 問答。"),
    ],
    "系統功能簡介": [
        item("1.", "**跨平台資料蒐集：**四平台爬蟲支援每日排程與管理員手動觸發，以 WebSocket 即時回報進度；依醫美關鍵字評分過濾無關與重複文章。"),
        item("2.", "**輿情儀表板：**依關鍵字、期間（近 7／30／90 天）與平台篩選，呈現趨勢、情緒分布、熱門話題與熱門文章；文章詳情含逐則判讀情緒的留言。"),
        item("3.", "**情緒判讀：**以 Gemini 批次將文章與留言判讀為正面、中性或負面，判讀參數固定，重跑結果一致。"),
        item("4.", "**AI 問答與洞察：**關鍵字與語意向量混合檢索，以 RRF 融合排名後生成回答並列出引用文章；另提供熱門話題與消費者痛點洞察。"),
        item("5.", "**監測、報表與歷史：**關鍵字負面比例超過門檻自動預警；Excel 匯出、可列印的輿情報告與個人分析歷史。"),
        item("6.", "**帳號與系統管理：**訪客、一般帳號、管理員三種角色；免費版、專業版、企業版三種方案限制監測數、查詢期間、AI 問答次數與匯出；登入失敗鎖定與稽核紀錄。"),
    ],
    "系統使用對象": [
        body("本系統服務醫美與保養產業的**從業人員**。三類目標客戶的需求與對應功能如下：", first_indent=True),
        table(["使用對象", "主要需求", "對應功能"], [
            ["醫美診所行銷人員", "掌握療程（如玻尿酸、皮秒、音波）口碑，及早發現負評", "儀表板、留言情緒、監測預警"],
            ["保養／美妝品牌行銷人員", "觀察產品與成分討論、新品上市後的網友反應", "熱門話題、AI 問答、Excel 匯出"],
            ["公關與行銷研究團隊", "替多個客戶定期產出輿情報告並追蹤多組關鍵字", "輿情分析報告、分析歷史、企業版多組監測"],
        ], [2500, 4300, W - 6800]),
        body("一般消費者暫不列入本版：社群聲量不等於療程安全或成效，先服務能判讀資料的專業人員，消費者版列為未來發展。"),
    ],
    "系統特色": [
        item("1.", "**句句可回查：**AI 回答一律附引用文章，可點回社群原文核對；這是與通用 AI 最主要的差異。"),
        item("2.", "**垂直領域詞庫：**熱門話題只統計 178 個醫美與保養專業詞，排除無意義的高頻詞。"),
        item("3.", "**結果可重現：**判讀改用 temperature 0 後，同批 100 篇重判 0 篇改變（調整前 12 篇）；與另一模型交叉比對一致率 82%（非人工標註）。"),
        item("4.", "**主文與留言並重：**實測 PTT 留言負面比例 14.0%，約為主文 7.9% 的 1.8 倍，只看主文會低估負評。"),
        item("5.", "**帳號化監測與品質：**關鍵字、預警與歷史依帳號保存，不必每次重新下指令；後端 490 項、前端 43 項自動化測試通過。"),
        table(["比較項目", "直接詢問通用 AI", "MeBOD"], [
            ["資料來源", "不透明，難以指定平台與期間", "四平台原文，可依平台、期間篩選"],
            ["可查證性", "多半沒有附原文", "每則回答附引用文章，可點回原文"],
            ["判讀穩定度", "同樣問題重問可能不同", "情緒判讀固定參數，重跑一致"],
            ["持續追蹤", "每次都要重新詢問", "帳號化關鍵字監測與自動預警"],
        ], [2500, 3700, W - 6200]),
    ],
    "系統開發工具": [
        table(["類別", "工具"], [
            ["前端／後端", "Vue 3、Vite、Chart.js／Python、FastAPI、SQLAlchemy 2.0、Alembic、APScheduler"],
            ["資料庫／爬蟲", "PostgreSQL 18／Playwright（Chromium）、Requests、BeautifulSoup"],
            ["AI", "Gemini 2.5 Flash-Lite、gemini-embedding-001（768 維向量）、jieba 斷詞"],
            ["測試與設計", "pytest、Vitest、Playwright E2E、Ruff、ESLint、GitHub Actions；UML、Unified Process、Git"],
        ], [2500, W - 2500]),
    ],
    "系統使用環境": [
        table(["項目", "需求"], [
            ["使用端", "電腦、平板或手機的現代瀏覽器，免安裝；訪客可瀏覽儀表板，登入後使用 AI 問答與預警。"],
            ["伺服器端", "Windows 主機（建議 8 GB RAM）、Python 3.12+、Node.js、PostgreSQL 18、Chromium；需連線 Gemini API。"],
            ["對外服務", "以 Cloudflare Tunnel 提供 HTTPS，不需開放主機連接埠。"],
        ], [2500, W - 2500]),
    ],
    "結論及未來發展": [
        body("MeBOD 已完成從蒐集、判讀、檢索到報告的完整流程，截至 115 年 10 月 9 日收錄 10,370 篇文章、6,364 則留言。未來發展："),
        item("1.", "**營運驗證：**以試用回饋確認方案定價，量化主機、資料庫與 Gemini API 費用，計算損益兩平的付費帳號數。"),
        item("2.", "**消費者版：**提供一般民眾查詢療程口碑與常見風險。"),
        item("3.", "**資料與品質：**加入影音留言、新聞與部落格，自動辨識業配文，並以人工盲標驗證。"),
        item("4.", "**因應 AI 代理工具：**持續強化垂直資料庫、可回查出處與帳號化監測。"),
    ],
}

HEADER = {
    "組": "組    別：第115405組",
    "專題名稱": "專題名稱：MeBOD 醫美時尚輿情分析系統",
    "指導教師": "指導教師：陳信宏 老師",
    "專題學生": "專題學生：11246044 陳威帆（組長）、11246039 許家全",
}


def main() -> None:
    work = Path(tempfile.mkdtemp())
    with zipfile.ZipFile(SRC) as z:
        z.extractall(work)
    doc_path = work / "word" / "document.xml"
    x = doc_path.read_text(encoding="utf-8")

    paras = re.findall(r"<w:p[ >].*?</w:p>", x, flags=re.S)
    text_of = lambda p: "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p))  # noqa: E731

    # 1. 標題：只留「系統簡介」，刪除紅字提示與黃底
    title = paras[0]
    new_title = re.sub(r'<w:shd w:val="clear" w:color="auto" w:fill="FFF2CC"/>', "", title)
    new_title = re.sub(r"(<w:r[ >](?:(?!</w:r>).)*?<w:color w:val=\"FF0000\"/>.*?</w:r>)", "", new_title, flags=re.S)
    new_title = new_title.replace("<w:pPr>", '<w:pPr><w:jc w:val="center"/>', 1)
    assert text_of(new_title) == "系統簡介", text_of(new_title)
    x = x.replace(title, new_title, 1)

    # 2. 抬頭四行：保留段落格式，換成完整文字
    for p in paras[1:5]:
        t = text_of(p)
        key = next(k for k in HEADER if t.startswith(k))
        ppr = re.search(r"<w:pPr>.*?</w:pPr>", p, flags=re.S).group(0)
        r = ('<w:r><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="標楷體" w:hAnsi="Times New Roman"/>'
             f'<w:sz w:val="28"/></w:rPr><w:t xml:space="preserve">{escape(HEADER[key])}</w:t></w:r>')
        x = x.replace(p, f"<w:p>{ppr}{r}</w:p>", 1)

    # 3. 各章節的「內文」段落換成內容
    for i, p in enumerate(paras):
        name = text_of(p)
        if name in SECTIONS:
            placeholder = paras[i + 1]
            assert text_of(placeholder) == "內文", (name, text_of(placeholder))
            x = x.replace(placeholder, "".join(SECTIONS[name]), 1)

    # 章節標題的行距與範本相同時兩頁放不下，略縮段前後距
    x = x.replace('<w:spacing w:line="360" w:lineRule="auto"/><w:ind w:left="482" w:hanging="482"/>',
                  '<w:spacing w:before="120" w:line="300" w:lineRule="auto"/><w:ind w:left="482" w:hanging="482"/>')

    doc_path.write_text(x, encoding="utf-8")

    # 範本頁尾的「共1頁」是寫死的數字，改成 NUMPAGES 欄位，才會顯示「共2頁」
    foot_path = work / "word" / "footer1.xml"
    f = foot_path.read_text(encoding="utf-8")
    pattern = r"(<w:t>，共</w:t></w:r>)<w:r>(<w:rPr>(?:(?!</w:rPr>).)*</w:rPr>)?<w:t>1</w:t></w:r>"
    m = re.search(pattern, f, flags=re.S)
    assert m, "找不到頁尾的總頁數"
    rpr = m.group(2) or ""
    field = (f"<w:r>{rpr}<w:fldChar w:fldCharType=\"begin\"/></w:r>"
             f"<w:r>{rpr}<w:instrText xml:space=\"preserve\"> NUMPAGES \\* MERGEFORMAT</w:instrText></w:r>"
             f"<w:r>{rpr}<w:fldChar w:fldCharType=\"separate\"/></w:r>"
             f"<w:r>{rpr}<w:t>2</w:t></w:r>"
             f"<w:r>{rpr}<w:fldChar w:fldCharType=\"end\"/></w:r>")
    f = f[:m.start()] + m.group(1) + field + f[m.end():]
    foot_path.write_text(f, encoding="utf-8")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(work.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(work).as_posix())
    shutil.rmtree(work)
    print("written", OUT)


if __name__ == "__main__":
    main()
