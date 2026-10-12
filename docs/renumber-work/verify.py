import pymupdf, re, sys
d = pymupdf.open(sys.argv[1])
printed = {i: int(m.group(1)) for i, p in enumerate(d) if (m := re.search(r'MeBOD\s*系統手冊\s*(\d+)', p.get_text()))}
body0 = next(i for i in range(1, 20) if re.search(r'第1\s*章\s*前言\s*\n\s*1-1', d[i].get_text()))
entries = []
for i in range(1, body0):
    for line in d[i].get_text().split('\n'):
        m = re.match(r'^((?:第\s*\d+\s*章|\d+-\d+(?:-\d+)?|附錄\S*|(?:圖|表)(?:附-)?\d*-?\d+))\s*(.*?)\s*\.{3,}\s*(\d+)\s*$', line.strip())
        if m: entries.append((m.group(1).replace(' ', ''), int(m.group(3)), m.group(2).replace(' ', '')))
bad = 0
for key, pg, title in entries:
    needle = (key + title[:6]).replace(' ', '')
    found = None
    for i in range(body0, d.page_count):
        flat = d[i].get_text().replace(' ', '').replace('\n', '')
        if needle in flat:
            found = printed.get(i); break
    if found != pg:
        bad += 1; print('MISMATCH', key, 'list', pg, 'actual', found, title[:15])
print('entries', len(entries), 'mismatches', bad)
