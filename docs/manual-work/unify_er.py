"""以單一表示法重繪第8章的四張實體關聯圖。

原本圖8-1（總覽）以純折線加文字標示基數，圖8-2至圖8-4則用鴉腳式符號，
同一節出現兩種讀法。本程式把四張圖收斂到同一套繪製規則：

  * 實體框：白底、#EAF2F8 標題列、#315C80 外框，標題列左側放資料庫圖示。
  * 關聯線：父端 ｜ 表示恰好一筆、○｜ 表示可為空；子端一律 ○<（零至多筆）。
  * 外鍵欄位後標 [R##]，對應 8-1 外鍵表，基數改由鴉腳符號表達，不再重複寫字。

綱要來源是 schema_db.json（由實際資料庫產生），不是 ORM 推導的 schema.json，
因為 8-1 描述的是資料庫實際施行的限制。
"""
from pathlib import Path
import json, math
from PIL import Image, ImageDraw, ImageFont

WORK = Path(__file__).resolve().parent
FIG = WORK / "figures"
FIG.mkdir(exist_ok=True)
FONT = "C:/Windows/Fonts/kaiu.ttf"
F = lambda n: ImageFont.truetype(FONT, n)

LINE = "#315C80"      # 外框與關聯線
HEAD = "#EAF2F8"      # 標題列底色
ROW = 46              # 欄位列高
HEADER_H = 62         # 標題列高度

DATA = json.loads((WORK / "schema_db.json").read_text(encoding="utf-8"))
BY = {t["table"]: t for t in DATA}

# 外鍵依子表名、欄位名排序後編號，與 8-1 表的 R01..R14 一致。
RELS = []
for t in sorted(DATA, key=lambda z: z["table"]):
    for c in t["columns"]:
        if c["fk"]:
            RELS.append((t["table"], c["name"], c["fk"][0], c["nullable"]))
RID = {(child, col): i for i, (child, col, _, _) in enumerate(RELS, 1)}


def wrap(s, max_width, font):
    out = []
    for line in s.split("\n"):
        cur = ""
        for ch in line:
            if font.getlength(cur + ch) > max_width and cur:
                out.append(cur)
                cur = ch
            else:
                cur += ch
        out.append(cur)
    return out


def txt(d, xy, text, size=34, width=400, center=True):
    x, y = xy
    for i, line in enumerate(wrap(text, width, F(size))):
        d.text((x, y + i * (size + 10)), line, font=F(size), fill="black",
               anchor="mt" if center else "lt")


def cylinder(d, x, y):
    """標題列左側的資料表圖示，與其他章節的圖示風格一致。"""
    d.rectangle((x + 5, y + 13, x + 57, y + 49), fill=HEAD, outline=LINE, width=3)
    d.ellipse((x + 5, y + 37, x + 57, y + 60), fill=HEAD, outline=LINE, width=3)
    d.rectangle((x + 8, y + 28, x + 54, y + 46), fill=HEAD)
    d.ellipse((x + 5, y + 2, x + 57, y + 25), fill=HEAD, outline=LINE, width=3)
    d.arc((x + 5, y + 22, x + 57, y + 45), 0, 180, fill=LINE, width=3)


def key_rows(name, extra=0):
    """取出要顯示的欄位：識別鍵與關聯欄位優先，必要時補足一般欄位。"""
    cols = [c for c in BY[name]["columns"] if c["pk"] or c["fk"] or c["unique"]]
    if extra:
        for c in BY[name]["columns"]:
            if len(cols) >= extra:
                break
            if c not in cols:
                cols.append(c)
    if not cols:
        cols = BY[name]["columns"][:2]
    return cols


def label(c):
    flags = "/".join(k for k, yes in
                     [("PK", c["pk"]), ("FK", bool(c["fk"])), ("UQ", c["unique"])] if yes)
    return (flags + "  " + c["name"]).strip()


def entity(d, name, x, y, w=490, extra=0, rid_suffix=True):
    cols = key_rows(name, extra)
    h = HEADER_H + 13 + len(cols) * ROW
    d.rectangle((x, y, x + w, y + h), fill="white", outline=LINE, width=3)
    d.rectangle((x, y, x + w, y + HEADER_H), fill=HEAD, outline=LINE, width=3)
    cylinder(d, x + 10, y + 3)
    txt(d, (x + 80, y + 16), name, 32, w - 95, False)
    for i, c in enumerate(cols):
        text = label(c)
        if rid_suffix and c["fk"]:
            text += f"  [R{RID[(name, c['name'])]:02}]"
        txt(d, (x + 15, y + HEADER_H + 14 + i * ROW), text, 28, w - 25, False)
    return h


def box_height(name, extra=0):
    return HEADER_H + 13 + len(key_rows(name, extra)) * ROW


def er_line(d, points, parent_optional):
    """父端在 points[0]，子端在 points[-1]；兩端都畫鴉腳式符號。"""
    d.line(points, fill=LINE, width=3)

    def mark(p, q, many=False, optional=False):
        dx, dy = q[0] - p[0], q[1] - p[1]
        mag = math.hypot(dx, dy)
        ux, uy = dx / mag, dy / mag

        def pos(a, b):
            return (p[0] + ux * a - uy * b, p[1] + uy * a + ux * b)

        if many:
            for b in (-13, 0, 13):
                d.line((pos(0, b), pos(25, 0)), fill=LINE, width=3)
        else:
            d.line((pos(13, -13), pos(13, 13)), fill=LINE, width=3)
        if optional:
            cx, cy = pos(40, 0)
            d.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), fill="white", outline=LINE, width=3)
        else:
            d.line((pos(31, -13), pos(31, 13)), fill=LINE, width=3)

    mark(points[0], points[1], optional=parent_optional)
    mark(points[-1], points[-2], many=True, optional=True)


LEGEND = "PK 主鍵   FK 外鍵   UQ 唯一鍵   ○ 可無   | 一筆   分叉 多筆   [R##] 對照8-1外鍵表"


def domain(name, positions, edges, h, subtitle, w=1800):
    im = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(im)
    for points, parent_optional in edges:
        er_line(d, points, parent_optional)
    for table_name, xy in positions.items():
        entity(d, table_name, *xy)
    txt(d, (w // 2, h - 110), subtitle, 29, w - 80)
    txt(d, (w // 2, h - 65), LEGEND, 28, w - 80)
    im.save(FIG / (name + ".png"))
    print(f"  {name}.png  {w}x{h}")


# ---------------------------------------------------------------- 圖8-2 內容領域
domain("er_content", {
    "platforms": (40, 30), "boards": (655, 30), "authors": (1270, 30),
    "articles": (655, 465), "comments": (40, 1020), "article_chunks": (1270, 1020)}, [
    ([(530, 135), (655, 135)], False),                                   # R08 platforms→boards
    ([(285, 197), (285, 380), (730, 380), (730, 465)], False),           # R04 platforms→articles
    ([(900, 197), (900, 465)], True),                                    # R05 boards→articles
    ([(1515, 197), (1515, 380), (1080, 380), (1080, 465)], True),        # R06 authors→articles
    ([(655, 710), (285, 710), (285, 1020)], False),                      # R09 articles→comments
    ([(1145, 710), (1515, 710), (1515, 1020)], False),                   # R03 articles→article_chunks
], 1340, "內容領域實體關聯圖  僅顯示識別鍵與關聯欄位；完整型別見資料字典")

# ---------------------------------------------------------------- 圖8-3 帳號領域
domain("er_users", {
    "plans": (40, 30), "users": (655, 30), "audit_logs": (1270, 30),
    "analysis_history": (40, 540), "usage_counters": (1270, 540),
    "watch_keywords": (40, 1000), "alerts": (1270, 1000)}, [
    ([(530, 130), (655, 130)], True),                                    # R13 plans→users
    ([(1145, 130), (1270, 130)], True),                                  # R07 users→audit_logs
    ([(730, 243), (730, 430), (285, 430), (285, 540)], False),           # R02 users→analysis_history
    ([(1080, 243), (1080, 430), (1515, 430), (1515, 540)], False),       # R12 users→usage_counters
    ([(850, 243), (850, 880), (285, 880), (285, 1000)], True),           # R14 users→watch_keywords
    ([(970, 243), (970, 880), (1515, 880), (1515, 1000)], True),         # R01 users→alerts
], 1320, "帳號領域實體關聯圖  關聯端點是否可空依實際 FK 欄位定義")

# ---------------------------------------------------------------- 圖8-4 維運與共用
domain("er_ops", {
    "platforms": (40, 30), "boards": (1270, 30), "crawl_logs": (655, 440),
    "analysis_results": (40, 870), "settings": (1270, 870),
    "system_locks": (40, 1180), "rate_limit_hits": (1270, 1180)}, [
    ([(285, 197), (285, 330), (760, 330), (760, 440)], True),            # R10 platforms→crawl_logs
    ([(1515, 197), (1515, 330), (1040, 330), (1040, 440)], True),        # R11 boards→crawl_logs
], 1560, "維運與共用資料  platforms 與 boards 為前圖參照；下方四表無宣告 FK")


# ---------------------------------------------------------------- 圖8-1 全資料庫總覽
# 總覽原本用純折線加文字基數，與上面三張不同；改為同一套鴉腳符號與實體框。
OV_W, COL_X, GAP = 600, (40, 880, 1700, 2600), 58
COLUMNS = (
    ["platforms", "authors", "comments", "settings"],
    ["boards", "articles", "article_chunks", "crawl_logs"],
    ["plans", "analysis_history", "watch_keywords", "analysis_results", "system_locks"],
    ["users", "usage_counters", "alerts", "audit_logs", "rate_limit_hits"],
)
TOP = 205
pos, bh = {}, {}
for ci, names in enumerate(COLUMNS):
    y = TOP
    for n in names:
        h = box_height(n, extra=5)
        pos[n], bh[n] = (COL_X[ci], y), h
        y += h + GAP
OV_H = max(y for y in (pos[n][1] + bh[n] for n in pos)) + 230

im = Image.new("RGB", (3300, OV_H), "white")
d = ImageDraw.Draw(im)
txt(d, (1650, 20), "MeBOD 關聯資料庫總覽", 54, 3200)
txt(d, (1650, 95), "18張ORM資料表＋版本表　　14條實體外鍵以 R01 至 R14 編號　　基數符號與圖8-2至圖8-4相同", 30, 3200)
txt(d, (760, 158), "內容領域", 32, 700)
txt(d, (2450, 158), "帳號與個人領域", 32, 700)

# 關聯線先畫，實體框後畫，框才會蓋住進入框內的線頭。
for i, (child, col, fk, nullable) in enumerate(RELS, 1):
    parent = fk["target"].split(".")[0]
    px, py0 = pos[parent]
    cx, cy0 = pos[child]
    rows = key_rows(child, extra=5)
    row_y = cy0 + HEADER_H + 28 + [c["name"] for c in rows].index(col) * ROW
    par_y = py0 + HEADER_H + 20 + (i * 37) % max(bh[parent] - HEADER_H - 40, 40)
    if px == cx:                                   # 同一欄：繞到欄位右側的通道
        lane = px + OV_W + 30 + i * 9
        pts = [(px + OV_W, par_y), (lane, par_y), (lane, row_y), (cx + OV_W, row_y)]
    else:
        right = cx > px
        a = (px + OV_W, par_y) if right else (px, par_y)
        b = (cx, row_y) if right else (cx + OV_W, row_y)
        # 轉折通道必須落在兩個框之間；欄距只有120點，偏移要夾在範圍內，
        # 否則折線會伸進子表框內，鴉腳符號被框蓋住。
        lo, hi = min(a[0], b[0]) + 26, max(a[0], b[0]) - 26
        lane = min(max((a[0] + b[0]) / 2 + (i % 5 - 2) * 14, lo), hi)
        pts = [a, (lane, a[1]), (lane, b[1]), b]
    er_line(d, pts, nullable)

for name, (x, y) in pos.items():
    entity(d, name, x, y, w=OV_W, extra=5)

d.rectangle((40, OV_H - 185, 1360, OV_H - 110), fill=HEAD, outline=LINE, width=3)
txt(d, (58, OV_H - 168), "alembic_version　PK version_num　（遷移版本，不參與關聯）", 29, 1290, False)
txt(d, (1650, OV_H - 175), "完整欄位、NULL 與刪除規則見 8-1 外鍵表及 8-2 資料字典", 29, 1600)
txt(d, (1650, OV_H - 70), LEGEND, 28, 3100)
im.save(FIG / "er_overview.png")
print(f"  er_overview.png  3300x{OV_H}")
