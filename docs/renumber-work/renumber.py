"""表2-4 已刪除：把表2-5～表2-8 往前遞補為表2-4～表2-7，並修正所有引用。

目錄、圖目錄、表目錄是 Word 欄位，之後由 finalize.ps1 重新產生並更新頁碼，
這裡不改 TOC 段落的快取文字。

    python renumber.py in.docx out.docx
"""
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

SRC, OUT = Path(sys.argv[1]), Path(sys.argv[2])
work = Path(tempfile.mkdtemp())
with zipfile.ZipFile(SRC) as z:
    z.extractall(work)
doc = work / "word" / "document.xml"
x = doc.read_text(encoding="utf-8")
paras = re.findall(r"<w:p[ >].*?</w:p>", x, flags=re.S)
text_of = lambda p: "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p))  # noqa: E731


def edit_text(p, old, new):
    """在單一 <w:t> 內替換；跨 run 時先把整段文字併進第一個 <w:t>。"""
    ts = re.findall(r"(<w:t[^>]*>)([^<]*)(</w:t>)", p)
    for open_, body, close in ts:
        if old in body:
            return p.replace(open_ + body + close, open_ + body.replace(old, new) + close, 1)
    full = text_of(p)
    assert old in full, (old, full[:60])
    first = True

    def merge(m):
        nonlocal first
        if first:
            first = False
            return f'<w:t xml:space="preserve">{full.replace(old, new)}</w:t>'
        return "<w:t></w:t>"
    return re.sub(r"<w:t[^>]*>[^<]*</w:t>", merge, p)


changes = []
# 1. 先處理指向已刪除表2-4 的文字
fixes = {
    311: ("金額試算見表2-3、表2-4", "金額試算見表2-3"),
    2761: ("表2-3、表2-4列模型單價、字元換算用量、主機與人力情境", "表2-3列模型單價、字元換算用量與主機情境"),
}
for i, (old, new) in fixes.items():
    p2 = edit_text(paras[i], old, new)
    x = x.replace(paras[i], p2, 1)
    paras[i] = p2
    changes.append((i, old, new))

# 2. 表2-5～表2-8 遞補（單次替換，避免連鎖重編；TOC 段落交給 Word 重建）
PAT = re.compile(r"表2-([5-8])(?!\d)")
for i, p in enumerate(paras):
    if "TOC1" in p or not PAT.search(text_of(p)):
        continue
    p2 = p
    # 先逐個 <w:t> 處理
    def sub_t(m):
        return m.group(1) + PAT.sub(lambda k: f"表2-{int(k.group(1)) - 1}", m.group(2)) + m.group(3)
    p2 = re.sub(r"(<w:t[^>]*>)([^<]*)(</w:t>)", sub_t, p2)
    if PAT.search(text_of(p2)) or text_of(p2) == text_of(p):
        # 編號跨 run 被拆開：整段文字合併後再替換
        full = PAT.sub(lambda k: f"表2-{int(k.group(1)) - 1}", text_of(p))
        first = [True]

        def merge(m):
            if first[0]:
                first[0] = False
                return f'<w:t xml:space="preserve">{full}</w:t>'
            return "<w:t></w:t>"
        p2 = re.sub(r"<w:t[^>]*>[^<]*</w:t>", merge, p)
    changes.append((i, text_of(p)[:50], text_of(p2)[:50]))
    x = x.replace(p, p2, 1)
    paras[i] = p2

# 檢查：正文中不應再出現表2-8，也不應出現指向已刪表格的「表2-3、表2-4」
body = [text_of(p) for p in paras if "TOC1" not in p]
assert not any("表2-8" in t for t in body)
captions = [t for t in body if re.match(r"^表2-\d", t)]
print("chapter 2 table captions:", [c.split(" ")[0] for c in captions])

doc.write_text(x, encoding="utf-8")
if OUT.exists():
    OUT.unlink()
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    ct = work / "[Content_Types].xml"
    z.write(ct, "[Content_Types].xml")
    for f in work.rglob("*"):
        if f.is_file() and f != ct:
            z.write(f, f.relative_to(work).as_posix())
shutil.rmtree(work)
for c in changes:
    print(c)
