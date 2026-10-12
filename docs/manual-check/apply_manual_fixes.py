"""依 115/10/12–13 的程式修正與實測，更新系統手冊中已過時的段落。

只改文字內容、表格儲存格與圖 6-15；保留原有段落格式。
段落以 document.xml 中 <w:p> 的出現順序編號（與 text.txt 第一欄相同）。

    python apply_manual_fixes.py source.docx 輸出.docx
"""
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image

SRC, OUT = Path(sys.argv[1]), Path(sys.argv[2])
FIG = Path(__file__).resolve().parents[1] / "manual-work" / "uniform-figures" / "seq_qa_v2.png"

work = Path(tempfile.mkdtemp())
with zipfile.ZipFile(SRC) as z:
    z.extractall(work)
doc = work / "word" / "document.xml"
x = doc.read_text(encoding="utf-8")
PARAS = re.findall(r"<w:p[ >].*?</w:p>", x, flags=re.S)
text_of = lambda p: "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p))  # noqa: E731
new = {}


def set_para(i, text, expect=None):
    """整段換成新文字：保留段落屬性與第一個 run 的字型格式。"""
    p = new.get(i, PARAS[i])
    if expect is not None:
        assert expect in text_of(PARAS[i]), (i, expect, text_of(PARAS[i])[:60])
    ppr = re.search(r"<w:pPr>.*?</w:pPr>", p, flags=re.S)
    rpr = re.search(r"<w:r[ >](?:(?!</w:r>).)*?(<w:rPr>.*?</w:rPr>)", p, flags=re.S)
    head = re.match(r"<w:p[^>]*>", p).group(0)
    run = f'<w:r>{rpr.group(1) if rpr else ""}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'
    new[i] = f"{head}{ppr.group(0) if ppr else ''}{run}</w:p>"


def replace_in(i, old, repl):
    t = text_of(PARAS[i])
    assert old in t, (i, old)
    set_para(i, t.replace(old, repl))


def set_code(i, lines):
    """程式節錄段落：每行一個 run，第二行起以 <w:br/> 換行。"""
    p = PARAS[i]
    ppr = re.search(r"<w:pPr>.*?</w:pPr>", p, flags=re.S).group(0)
    rpr = re.search(r"<w:rPr>.*?</w:rPr>", p[p.index("</w:pPr>"):], flags=re.S).group(0)
    head = re.match(r"<w:p[^>]*>", p).group(0)
    runs = []
    for k, line in enumerate(lines):
        br = "<w:br/>" if k else ""
        body = f'<w:t xml:space="preserve">{escape(line)}</w:t>' if line else ""
        runs.append(f"<w:r>{rpr}{br}{body}</w:r>")
    # 長行換行時不要左右撐開字距
    ppr = re.sub(r"<w:jc [^>]*/>", "", ppr).replace("</w:pPr>", '<w:jc w:val="left"/></w:pPr>')
    new[i] = head + ppr + "".join(runs) + "</w:p>"


# ── 1-1 核對基準 ──
replace_in(232, "本次技術核對基準為民國115年10月6日GitHub版本（HEAD 9367bae）[8]；",
           "本次技術核對基準為民國115年10月6日GitHub版本（HEAD 9367bae）[8]，並依10月12日至13日的程式修正（預警帳號隔離、AI問答檢索範圍與前端建置，見10-3）更新相關章節；")

# ── 2-2 成本：改用系統實際使用的模型與實測 token 量 ──
replace_in(315, "模型呼叫、主機、備份、維護人力", "模型呼叫、主機、備份、金流手續費、維護人力")
set_para(319, "以下為情境估算，不是實際帳單或營收。模型單價取自Google Gemini API官方定價頁（查閱日期民國115年10月12日，見參考資料[11]）："
              "系統實際使用的gemini-2.5-flash-lite（.env之GEMINI_MODEL）每百萬輸入token 0.10美元、輸出token 0.40美元，"
              "gemini-embedding-001每百萬輸入token 0.15美元，並以1美元＝32新臺幣換算。token用量以backend/scripts/measure_llm_cost.py量測："
              "以系統實際組成prompt的函式產生問答與分析的輸入、不呼叫模型，以1個中文字約1個token保守估計；收錄量取近30天實際資料。"
              "正式營運應以API用量紀錄校正。", expect="以下為情境估算")
CELLS_23 = {
    325: "問題解析約440輸入／150輸出token；依證據回答最多約9,350輸入／2,000輸出token（含Dashboard摘要）",
    326: "約0.06元",
    328: "最多約14,300輸入／4,500輸出token（輸出取已存31筆分析的最大值）；同一關鍵字6小時內共用快取",
    329: "約0.10元",
    331: "近30天實際新增897篇文章、3,216則留言，每批20則；約50萬輸入／12萬輸出token",
    332: "約3.2元",
    334: "近30天897篇，平均每篇1.91段、每段約314字，約54萬token",
    335: "約2.6元",
    340: "Render雲端Web 25美元＋PostgreSQL 19美元；網域年費420元（價格取自第三方彙整，正式採用前以官網確認）",
    341: "約1,443元",
}
for i, t in CELLS_23.items():
    set_para(i, t)
CELLS_24 = {
    346: "固定成本F（主機＋網域＋情緒評分與向量，後兩項約6元保守計7元）",
    347: "295元", 348: "1,450元",
    349: "每位付費用戶變動成本v（問答100次＋分析60次＋金流手續費3%，額度用滿）",
    350: "27元", 351: "27元",
    356: "1人", 357: "4人",
    359: "＋4,335元", 360: "＋3,180元",
    362: "＋13,595元", 363: "＋12,440元",
}
for i, t in CELLS_24.items():
    set_para(i, t)
set_para(364, "計算式為月成本C(N)＝F＋N×v、月收入R(N)＝N×p，月損益＝R(N)−C(N)。v＝100×0.06＋60×0.10＋490×3%≈27元；"
              "情境B的F＝1,408＋35＋7＝1,450元。免費版不開放問答與匯出，成本以資料庫查詢為主，未列入變動成本；企業版問答不限次數，需依實際用量另行定價。"
              "上表未計入維護人力、稅與前期開發投入；若計入每月20或40小時維運人力（以115年基本工資時薪196元計），情境B的損益兩平人數分別為12人與21人。"
              "月損益兩平只表示當月收支打平，不代表已回收開發成本。金流手續費3%與網域年費為假設值；改用其他模型或官方調價時，以相同公式重新計算。",
         expect="計算式為月成本")

# ── 3-4 問答檢索 ──
replace_in(509, "內容依民國115年10月6日原始碼（HEAD 9367bae）核對", "內容依民國115年10月13日原始碼核對（AI問答檢索範圍於10月12日修正）")
set_para(549, text_of(PARAS[549]) + "使用者在AI問答頁提問時，檢索範圍沿用Dashboard選定的關鍵字與期間（問題自行指定期間時以問題為準），Dashboard指標只作回答背景。")
set_para(565, "依檢索文章回答；AI問答頁的檢索範圍套用Dashboard關鍵字與期間，指標作背景；附參考來源與信心程度")

# ── 4-1、4-3 時程與提交數（依各檔案首次提交日期與 git log） ──
replace_in(602, "完成PTT爬蟲、儀表板查詢API與前端儀表板雛形", "完成PTT爬蟲、儀表板查詢API、WebSocket即時通道與前端儀表板雛形")
set_para(603, "暑期與第二學期（民國115年7月至116年1月）：7月加入帳號登入與角色權限、監測預警；8月加入Dcard、Mobile01與Threads爬蟲；"
              "9月加入方案額度、Alembic資料庫遷移與向量切段檢索；10月3日完成PostgreSQL整合測試10項，10月6日完成情緒標籤一致性評估並將分類改為temperature 0，"
              "10月12日修正預警帳號隔離並讓AI問答頁採用混合檢索，10月13日繳交複評文件。預定11月25日至27日參加校內觀摩展，12月29日交付最終文件。"
              "以上月份依各功能程式檔首次提交的日期整理，11月以後為預定。", expect="暑期與第二學期")
set_para(726, "依儲存庫xujiaquan05/115405至民國115年10月13日的提交紀錄（git log）統計，共168次提交，分布如表4-4。提交次數反映版本更新的頻率，不代表功能完成度或個人貢獻比例。")
set_para(740, "10月（至10月13日）", expect="10月（至10月6日）")
set_para(741, "38", expect="20")
set_para(743, "168", expect="150")

# ── 第 5、6 章：問答流程與預警隔離 ──
replace_in(852, "依快取、儀表板脈絡或混合檢索分支處理", "依快取或混合檢索處理（有儀表板脈絡時以其關鍵字與期間限定範圍）")
set_para(866, "監測詞的擁有者檢查已實作；預警的查詢、單筆已讀、全部已讀與手動檢查自民國115年10月12日起均只處理本人資料，詳見6-1-8。", expect="監測詞的擁有者檢查")
set_para(973, "步驟三：有有效快取且未要求no_cache時直接返回；仍會經路由記錄用量。步驟四：未命中且帶有dashboard_context時，先由Gemini解析問題意圖，"
              "再把Dashboard的關鍵字補入檢索詞；問題未自行指定期間時，期間沿用Dashboard設定。", expect="步驟三")
set_para(974, "步驟五：在此範圍內執行關鍵字排名與段落向量搜尋，以RRF常數60融合排名，交由模型依檢索文章回答；Dashboard的總覽、情緒與洞察摘要只作背景，"
              "來源即檢索到的文章。範圍內檢索不到文章時，才改依Dashboard脈絡回答，來源為脈絡中的熱門文章；沒有脈絡的API呼叫同樣走解析與混合檢索。"
              "步驟六：回答非空時保存15分鐘RAM快取。步驟七：路由記錄用量並回傳。", expect="步驟五")
set_para(988, "GET alerts依登入帳號過濾，訪客得到空列表。民國115年10月12日起，單筆已讀以id加user_id查詢，他人的預警回404而不透露是否存在；"
              "全部已讀只更新本人未讀資料；手動check只評估本人的監測詞，回傳結果也只含本人預警，全體帳號的檢查改由每日排程執行。"
              "test_monitor_api.py已加入3項雙帳號負向測試。", expect="已實作的GET alerts")
replace_in(991, "此圖只描述新增操作，不代表其他預警異動已完成同樣隔離。", "預警的已讀與手動檢查同樣限定本人，見本節說明。")
replace_in(994, "GET預警清單另依user_id過濾，手動全域檢查及已讀操作的現況限制仍依本節說明。", "預警清單、已讀與手動檢查皆依user_id限定本人。")

# 圖 6-15：換成新流程
media = re.search(r'r:id="([^"]+)"', PARAS[970]).group(1)
rels = (work / "word" / "_rels" / "document.xml.rels").read_text(encoding="utf-8")
target = re.search(rf'Id="{media}"[^>]*Target="([^"]+)"', rels).group(1)
img = Image.open(FIG)
img.save(work / "word" / target, dpi=(300, 300))
w0, h0 = 510.5, 586.5
w1 = round(h0 * img.width / img.height, 1)  # 高度不變，寬度依新比例縮放，避免版面往後推
p970 = PARAS[970].replace(f"width:{w0}pt;height:{h0}pt", f"width:{w1}pt;height:{h0}pt")
assert p970 != PARAS[970]
new[970] = p970
set_para(971, "圖6-15 UC03在Dashboard範圍內混合檢索的分支循序", expect="圖6-15")

# ── 第 9 章 ──
replace_in(2223, "未命中時，有Dashboard脈絡就直接依脈絡生成；沒有脈絡才走關鍵字與向量混合檢索，再交模型回答。",
           "未命中時解析問題意圖並做關鍵字與向量混合檢索；有Dashboard脈絡時檢索範圍套用其關鍵字與期間，檢索不到文章才改依脈絡生成。")
set_para(2226, "程式9-1-3 回答快取與Dashboard範圍檢索", expect="程式9-1-3")
set_para(2227, "原碼節錄：backend/app/services/rag_service.py，第738至755行（民國115年10月13日版本）。", expect="原碼節錄")
rag = (Path(__file__).resolve().parents[2] / "backend/app/services/rag_service.py").read_text(encoding="utf-8").splitlines()
assert rag[737].strip().startswith("cache_key = _qa_cache_key") and "generate_rag_answer" in rag[754], rag[754]
set_code(2228, rag[737:755])
set_para(2229, "本段位於answer_question：use_cache為真且快取存在便直接返回。未命中且有dashboard_context時，先以scope_intent_to_dashboard把Dashboard關鍵字與期間"
               "套入解析後的意圖，再呼叫retrieve_articles混合檢索；有文章就依文章生成並以文章為來源，否則退回脈絡回答。即使快取命中，路由仍會記用量。"
               "對應6-1-6分支圖及9-1-7控制流程。", expect="本段位於answer_question")
set_para(2247, "驗證：預警的查詢、已讀、全部已讀與手動檢查皆限定本人，test_monitor_api.py含3項雙帳號負向測試；另驗證方案不足、非法設定及重複請求。", expect="現況限制與驗證")
set_para(2287, "適用分支：answer_question未命中可用快取時執行此RAG路徑；有Dashboard脈絡時檢索範圍套用其關鍵字與期間（見9-1-3），檢索不到文章才依脈絡生成。"
               "身分、額度及用量處理由qa路由負責，見9-1-7。對應第6章圖6-15。", expect="適用分支")
set_para(2289, "原碼節錄：backend/app/services/rag_service.py，第786至799行（民國115年10月13日版本；無Dashboard脈絡的API呼叫分支）。", expect="原碼節錄")

# ── 第 10 章 ──
set_para(2424, text_of(PARAS[2424]).replace("〔AI04〕", "") +
         "民國115年10月12日於Windows本機重跑：後端498項通過、1項跳過（符號連結權限），前端43項通過，JUnit報告存於backend/.test-artifacts；"
         "10月13日更正前端匯入大小寫與ESLint問題後，已提交程式的Ruff、ESLint與前端建置皆無錯誤。〔AI04〕", expect="民國115年10月8日")
set_para(2537, "已修正（115/10/12）：已讀、全部已讀與手動檢查限定本人；新增3項雙帳號測試", expect="尚待修正")
set_para(2546, "已修正（115/10/13）：更正匯入路徑並提交；10/08 Linux試建置已確認此修正可通過", expect="待修正")
set_para(2549, "已修正：Ruff（115/10/12）、ESLint（115/10/13），已提交程式皆無錯誤", expect="待修正")

# ── 第 14 章、附錄 ──
set_para(2784, "[8] MeBOD專案原始碼。民國115年10月6日GitHub版本HEAD 9367bae為主要核對基準，10月12日至13日修正後之提交（至2abc386）另行核對；"
               "資料庫遷移最新版a7d31c6f0e92。儲存庫https://github.com/xujiaquan05/115405。後端pytest與前端Vitest於10月8日（Linux）及10月12日（Windows）重跑，"
               "PostgreSQL整合與E2E沿用各自時間戳記之報告（第10章）。", expect="[8] MeBOD專案原始碼")
replace_in(2788, "查閱日期：民國115年10月6日", "查閱日期：民國115年10月12日")
set_para(2816, "程式開發與重構：民國115年7月8日至10月13日，儲存庫168次提交中有150次標註Claude共同撰寫（Opus 4.8 89次、Opus 5 36次、Opus 5.5 18次、"
               "Fable 5 6次、Sonnet 5 1次）。民國115年10月協助初評錄音整理、系統手冊校稿、情緒標籤對照標註、成本實測與測試重跑（第2、10章），"
               "以及第2至4、6、9、10、12、13章與附錄的增修。", expect="程式開發與重構")
set_para(2847, "表2-3與表2-4以系統實際使用模型的官方單價與實測token量重算（2-2），列出單價來源、假設與計算式，並估算加入維運人力後的損益兩平人數；"
               "部分處理：實際帳單與付費意願待驗證", expect="新增表2-3")
set_para(2868, text_of(PARAS[2868]) + "；民國115年10月12日起AI問答頁亦在Dashboard範圍內採用此檢索（6-1-6）", expect="改為意圖解析")

# 套用段落替換
out = x
for i, p in new.items():
    assert out.count(PARAS[i]) >= 1, i
    out = out.replace(PARAS[i], p, 1)


# ── 表格新增列：複製同表最後一列再改字 ──
def add_row_after(xml, anchor_text, cells):
    for tr in re.findall(r"<w:tr[ >].*?</w:tr>", xml, flags=re.S):
        if anchor_text in text_of(tr):
            break
    else:
        raise AssertionError(anchor_text)
    tcs = re.findall(r"<w:tc>.*?</w:tc>", tr, flags=re.S)
    assert len(tcs) == len(cells), (anchor_text, len(tcs))
    row = tr
    for tc, value in zip(tcs, cells):
        p = re.search(r"<w:p[ >].*?</w:p>", tc, flags=re.S).group(0)
        rpr = re.search(r"<w:rPr>.*?</w:rPr>", p[p.find("<w:r>"):] if "<w:r>" in p else "", flags=re.S)
        ppr = re.search(r"<w:pPr>.*?</w:pPr>", p, flags=re.S)
        head = re.match(r"<w:p[^>]*>", p).group(0)
        np = f'{head}{ppr.group(0) if ppr else ""}<w:r>{rpr.group(0) if rpr else ""}<w:t xml:space="preserve">{escape(value)}</w:t></w:r></w:p>'
        row = row.replace(tc, tc.replace(p, np, 1), 1)
    return xml.replace(tr, tr + row, 1)


out = add_row_after(out, "靜態檢查與建置115/10/08",
                    ["後端 tests 重跑115/10/12", "498", "跳過1 失敗0", "pytest-20261012.xml"])
out = add_row_after(out, "後端 tests 重跑115/10/12",
                    ["前端與靜態檢查115/10/13", "43", "失敗0；Ruff、ESLint、建置無錯誤", "vitest-20261012.xml"])
out = add_row_after(out, "靜態檢查未通過",
                    ["AI問答頁未使用混合檢索", "問答頁一律附Dashboard脈絡，該分支直接生成並以熱門文章前5篇為來源",
                     "改為在Dashboard範圍內混合檢索並以檢索文章為來源；新增5項單元測試（115/10/12）"])

doc.write_text(out, encoding="utf-8")
if OUT.exists():
    OUT.unlink()
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    names = [f for f in work.rglob("*") if f.is_file()]
    ct = work / "[Content_Types].xml"
    z.write(ct, "[Content_Types].xml")
    for f in names:
        if f != ct:
            z.write(f, f.relative_to(work).as_posix())
shutil.rmtree(work)
print("paragraphs changed:", len(new), "->", OUT)
