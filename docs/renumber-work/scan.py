import re
import sys
import zipfile

x = zipfile.ZipFile(sys.argv[1]).read("word/document.xml").decode("utf-8")
BS = chr(92)
print("SEQ fields:", x.count(" SEQ "), "TOC fields:", x.count("TOC " + BS), "PAGEREF:", x.count("PAGEREF"))
paras = re.findall(r"<w:p[ >].*?</w:p>", x, flags=re.S)
txt = lambda p: "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p))  # noqa: E731
rows = []
for i, p in enumerate(paras):
    t = txt(p).strip()
    sty = re.search(r'<w:pStyle w:val="([^"]+)"', p)
    sty = sty.group(1) if sty else ""
    if re.match(r"^(圖|表|程式)\s*(附-)?\d", t) and len(t) < 90:
        rows.append(f"{i}\t{sty}\t{t}")
open("caps.txt", "w", encoding="utf-8").write("\n".join(rows))
print(len(paras), len(rows))
