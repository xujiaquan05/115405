import re, sys, zipfile
x = zipfile.ZipFile(sys.argv[1]).read("word/document.xml").decode("utf-8")
paras = re.findall(r"<w:p[ >].*?</w:p>", x, flags=re.S)
txt = lambda p: "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p))
a, b = int(sys.argv[2]), int(sys.argv[3])
for i in range(a, b):
    t = txt(paras[i])
    if t.strip(): print(i, t[:160])
