"""重畫 4-1 的圖4-1：把甘特條改成帶階段與里程碑的時程圖。

原圖只有七條灰藍色長條，與下方表4-1 的六個階段名稱對不起來（原圖寫
「資料庫與爬蟲」「儀表板與問答」「測試與修正」，表格寫「核心開發」
「分析與權限」「整合驗證」），讀者要自己猜兩者的對應。新圖改用表4-1
的六個階段，並補上三件原圖沒有的資訊：

  * Unified Process 四階段（起始、精化、建構、移轉）的所在區間，
    本文第4-1節以這四階段描述專案，原圖卻看不到它們。
  * 兩個學期與暑期的分界，讓週次敘述能對到月份。
  * 里程碑：民國115年6月2日初審（日期見4-2節），以及期末交付。

長條的起訖沿用原甘特圖的規劃區間，只是把原本分開的「資料庫與爬蟲」
與「儀表板與問答」併成表格所稱的「核心開發」，沒有改動規劃本身。
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

WORK = Path(__file__).resolve().parent
FIG = WORK / "figures"
FIG.mkdir(exist_ok=True)
FONT = "C:/Windows/Fonts/kaiu.ttf"
F = lambda n: ImageFont.truetype(FONT, n)

INK = "#315C80"       # 外框與軸線，與第8章關聯圖同色
GRID = "#C8D6E2"      # 月份格線
TEXT = "#1F2937"

W, H = 1800, 1010
LEFT, RIGHT = 330, 1740          # 時間軸的左右邊界
MONTHS = ["115/2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "116/1"]
COL = (RIGHT - LEFT) / len(MONTHS)


def x(month):
    """月份座標；0 代表115年2月的月初，12 代表116年1月的月底。"""
    return LEFT + month * COL


# Unified Process 四階段：依4-1節的週次敘述換算到月份區間。
PHASES = [
    ("起始", 0.0, 1.5, "#DCE9F5", TEXT),
    ("精化", 1.5, 4.0, "#B7D0E6", TEXT),
    ("建構", 4.0, 8.5, "#7FA9CC", "white"),
    ("移轉", 8.5, 12.0, "#4E7EA8", "white"),
]

# 表4-1 的六個階段；顏色取自其所屬的 UP 階段，讓上下兩列互相對應。
STAGES = [
    ("需求與選題", 0.0, 2.5, "#DCE9F5"),
    ("分析設計", 1.0, 4.5, "#B7D0E6"),
    ("核心開發", 2.5, 7.5, "#7FA9CC"),
    ("分析與權限", 5.5, 8.5, "#7FA9CC"),
    ("整合驗證", 6.5, 10.5, "#4E7EA8"),
    ("文件與交付", 7.5, 12.0, "#4E7EA8"),
]

# 學期分界：第一學期以115年6月2日初審作結，暑期之後進入第二學期。
TERMS = [("第一學期", 0.0, 4.9), ("暑期", 4.9, 7.0), ("第二學期", 7.0, 12.0)]

MILESTONES = [("初審　115/6/2", 4.07), ("期末交付與展示", 11.6)]

AXIS_Y = 150          # 月份刻度所在高度
PHASE_Y = 185         # UP 階段帶
BAR_TOP = 300         # 第一條階段長條的上緣
BAR_H, BAR_GAP = 62, 30
MILE_Y = BAR_TOP + len(STAGES) * (BAR_H + BAR_GAP) + 24

im = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(im)


def centered(text, cx, cy, size, fill=TEXT):
    d.text((cx, cy), text, font=F(size), fill=fill, anchor="mm")


# ── 學期帶 ────────────────────────────────────────────────────────────
for name, a, b in TERMS:
    d.rectangle((x(a), 60, x(b), 108), fill="#F4F7FA", outline=GRID, width=2)
    centered(name, (x(a) + x(b)) / 2, 84, 30)

# ── 月份刻度與格線 ────────────────────────────────────────────────────
for i, label in enumerate(MONTHS):
    centered(label, x(i) + COL / 2, AXIS_Y - 24, 29)
    d.line((x(i), AXIS_Y, x(i), MILE_Y - 10), fill=GRID, width=2)
d.line((x(12), AXIS_Y, x(12), MILE_Y - 10), fill=GRID, width=2)
d.line((LEFT, AXIS_Y, RIGHT, AXIS_Y), fill=INK, width=3)

# ── Unified Process 階段帶 ────────────────────────────────────────────
d.text((LEFT - 22, PHASE_Y + 32), "UP 階段", font=F(29), fill=TEXT, anchor="rm")
for name, a, b, fill, ink in PHASES:
    d.rectangle((x(a), PHASE_Y, x(b), PHASE_Y + 64), fill=fill, outline=INK, width=3)
    centered(name, (x(a) + x(b)) / 2, PHASE_Y + 32, 31, ink)

# ── 六個階段長條 ──────────────────────────────────────────────────────
for i, (name, a, b, fill) in enumerate(STAGES):
    y0 = BAR_TOP + i * (BAR_H + BAR_GAP)
    d.text((LEFT - 22, y0 + BAR_H / 2), name, font=F(31), fill=TEXT, anchor="rm")
    d.rounded_rectangle((x(a), y0, x(b), y0 + BAR_H), radius=10,
                        fill=fill, outline=INK, width=3)
    # 不另外標月份數字：月份已在上方刻度，長條兩端對齊刻度即可讀出區間。

# ── 里程碑 ────────────────────────────────────────────────────────────
d.line((LEFT, MILE_Y, RIGHT, MILE_Y), fill=INK, width=3)
d.text((LEFT - 22, MILE_Y), "里程碑", font=F(29), fill=TEXT, anchor="rm")
for label, at in MILESTONES:
    cx = x(at)
    d.polygon([(cx, MILE_Y - 17), (cx + 17, MILE_Y), (cx, MILE_Y + 17), (cx - 17, MILE_Y)],
              fill="white", outline=INK)
    centered(label, cx, MILE_Y + 50, 28)

centered("規劃時程；長條為規劃區間，實際完成日期以版本紀錄與團隊確認為準，實際提交分布見圖4-2。",
         W / 2, H - 46, 28, "#4B5563")

im.save(FIG / "gantt.png")
print(f"  gantt.png  {W}x{H}")
