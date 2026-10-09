"""由 data.json 產生海報裡的向量圖表，填入 *.tpl.html，輸出 poster2.html、poster3.html。

圖表直接以 SVG 內嵌在頁面裡（而不是 <img>），才會沿用頁面的靜態字型，
輸出 PDF 時文字仍是可放大的向量。

    python output\\poster-trio\\build.py
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).parent
DATA = json.loads((HERE / "data.json").read_text(encoding="utf-8"))

GROUP_COLORS = {
    "保養": "#4F46E5",
    "彩妝": "#C2508A",
    "肌膚": "#0A7D70",
    "醫療": "#C98512",
    "療程": "#6D4AE0",
    "其他": "#7C7896",
}


def fmt(n: int) -> str:
    return f"{n:,}"


def bubbles() -> str:
    """熱門詞泡泡圖：面積與「提到這個詞的文章數」成正比，顏色代表詞的類別。"""
    terms = DATA["top_terms"][:18]
    placed: list[tuple[float, float, float, list]] = []
    gap = 0.7
    for word, count, group in terms:
        r = 3.2 * math.sqrt(count / 100)
        if not placed:
            placed.append((0.0, 0.0, r, [word, count, group]))
            continue
        best = None
        for px, py, pr, _ in placed:
            for step in range(72):
                a = step * math.pi / 36
                x = px + (pr + r + gap) * math.cos(a)
                y = py + (pr + r + gap) * math.sin(a)
                if any(math.hypot(x - qx, y - qy) < qr + r + gap - 0.01 for qx, qy, qr, _ in placed):
                    continue
                # 版面是橫長方形，垂直方向加權，讓泡泡往左右擴散
                cost = math.hypot(x, y * 2.1)
                if best is None or cost < best[0]:
                    best = (cost, x, y)
        placed.append((best[1], best[2], r, [word, count, group]))

    pad = 1
    min_x = min(x - r for x, _, r, _ in placed) - pad
    max_x = max(x + r for x, _, r, _ in placed) + pad
    min_y = min(y - r for _, y, r, _ in placed) - pad
    max_y = max(y + r for _, y, r, _ in placed) + pad
    parts = [f'<svg class="bubbles" viewBox="{min_x:.1f} {min_y:.1f} {max_x - min_x:.1f} {max_y - min_y + 1:.1f}">']
    # 每個類別一組放射漸層：左上偏亮，做出玻璃球的立體感（不用 SVG 濾鏡，PDF 仍是向量）
    parts.append("<defs>")
    for name, color in GROUP_COLORS.items():
        gid = "bg" + str(list(GROUP_COLORS).index(name))
        parts.append(
            f'<radialGradient id="{gid}" cx="0.3" cy="0.22" r="0.8">'
            f'<stop offset="0" stop-color="#fff" stop-opacity="0.42"/>'
            f'<stop offset="0.45" stop-color="{color}" stop-opacity="0.95"/>'
            f'<stop offset="1" stop-color="{color}"/></radialGradient>'
        )
    parts.append("</defs>")
    for x, y, r, (word, count, group) in placed:
        color = GROUP_COLORS[group]
        gid = "bg" + str(list(GROUP_COLORS).index(group))
        parts.append(f'<circle cx="{x:.1f}" cy="{y + r * 0.12:.1f}" r="{r:.1f}" fill="{color}" fill-opacity="0.18"/>')
        size = max(r * 0.42, 2.2)
        if len(word) == 3:
            size *= 0.85
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="url(#{gid})"/>'
            f'<text x="{x:.1f}" y="{y - size * 0.12:.1f}" text-anchor="middle" font-size="{size:.1f}" font-weight="800" fill="#fff">{word}</text>'
            f'<text x="{x:.1f}" y="{y + size * 0.95:.1f}" text-anchor="middle" font-size="{size * 0.5:.1f}" font-weight="600" fill="#fff" fill-opacity="0.85">{fmt(count)} 篇</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def bubble_legend() -> str:
    groups = []
    for _, _, group in DATA["top_terms"][:18]:
        if group not in groups:
            groups.append(group)
    return "".join(f'<span><i style="background:{GROUP_COLORS[g]}"></i>{g}</span>' for g in groups)


def monthly_bars() -> str:
    """近 12 個月的新文章數。"""
    months = DATA["monthly"]
    peak = max(n for _, n in months)
    w, h, bw = 120, 50, 7.2
    step = w / len(months)
    parts = [f'<svg class="months" viewBox="0 -6 {w} {h + 14}">']
    for i, (ym, n) in enumerate(months):
        bh = (h - 4) * n / peak
        x = i * step + (step - bw) / 2
        color = "#4F46E5" if n == peak else "#B9AEEA"
        parts.append(f'<rect x="{x:.2f}" y="{h - bh:.2f}" width="{bw}" height="{bh:.2f}" rx="1.6" fill="{color}"/>')
        parts.append(f'<text x="{x + bw / 2:.2f}" y="{h - bh - 1.6:.2f}" text-anchor="middle" font-size="2.7" font-weight="700" fill="#37325F">{n}</text>')
        month = int(ym[5:])
        parts.append(f'<text x="{x + bw / 2:.2f}" y="{h + 4.2:.2f}" text-anchor="middle" font-size="2.7" fill="#514C6E">{month}月</text>')
        if month in (10, 1):
            year = int(ym[:4]) - 1911
            parts.append(f'<text x="{x + bw / 2:.2f}" y="{h + 7.6:.2f}" text-anchor="middle" font-size="2.4" font-weight="700" fill="#6D4AE0">{year}年</text>')
    parts.append(f'<line x1="0" y1="{h}" x2="{w}" y2="{h}" stroke="#DCD6F5" stroke-width="0.3"/>')
    parts.append("</svg>")
    return "".join(parts)


def sparkline() -> str:
    """海報 2「之後」畫面裡的小趨勢線，用同一份月資料。"""
    months = DATA["monthly"]
    peak = max(n for _, n in months)
    w, h = 100, 30
    pts = [(i * w / (len(months) - 1), h - 2 - (h - 6) * n / peak) for i, (_, n) in enumerate(months)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"0,{h} " + line + f" {w},{h}"
    return (
        f'<svg class="spark" viewBox="0 0 {w} {h}" preserveAspectRatio="none">'
        '<defs><linearGradient id="sp" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6D4AE0" stop-opacity="0.35"/>'
        '<stop offset="1" stop-color="#6D4AE0" stop-opacity="0"/></linearGradient></defs>'
        f'<polygon points="{area}" fill="url(#sp)"/>'
        f'<polyline points="{line}" fill="none" stroke="#6D4AE0" stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>'
        "</svg>"
    )


def donut(cls: str, label_top: str, label_bottom: str, thickness: float = 9, big_label: bool = False) -> str:
    """情緒比例圓環。"""
    s = DATA["sentiment"]
    parts_data = [("正面", s["positive"], "#3DBE9F"), ("中性", s["neutral"], "#D9D5E6"), ("負面", s["negative"], "#E5736A")]
    total = sum(v for _, v, _ in parts_data)
    r = 40
    c = 2 * math.pi * r
    offset = 0.0
    parts = [f'<svg class="{cls}" viewBox="0 0 100 100"><g transform="rotate(-90 50 50)">']
    for _, v, color in parts_data:
        length = c * v / total
        parts.append(
            f'<circle cx="50" cy="50" r="{r}" fill="none" stroke="{color}" stroke-width="{thickness}" '
            f'stroke-dasharray="{length - 0.6:.2f} {c - length + 0.6:.2f}" stroke-dashoffset="{-offset:.2f}"/>'
        )
        offset += length
    parts.append("</g>")
    if big_label:
        # 小尺寸圓環只放一個大字，避免印出來看不清
        parts.append(f'<text x="50" y="58" text-anchor="middle" font-size="21" font-weight="900" fill="#1E1B4B">{label_top}</text>')
    else:
        parts.append(f'<text x="50" y="49" text-anchor="middle" font-size="13" font-weight="800" fill="#1E1B4B" font-family="Segoe UI">{label_top}</text>')
        parts.append(f'<text x="50" y="62" text-anchor="middle" font-size="6.5" font-weight="600" fill="#514C6E">{label_bottom}</text>')
    parts.append("</svg>")
    return "".join(parts)


def treatment_rows() -> str:
    """療程排行：前三名做成獎台卡片，其餘用橫條。"""
    rows = DATA["top_treatments"]
    peak = rows[0][1]
    medals = ["#4F46E5", "#6D4AE0", "#C2508A"]
    podium = []
    for i, (word, n) in enumerate(rows[:3]):
        podium.append(
            f'<div class="pod" style="--m:{medals[i]}"><span class="medal">{i + 1}</span>'
            f'<div class="pw">{word}</div><div class="pn"><b>{n}</b> 篇</div>'
            f'<div class="pb"><i style="width:{n / peak * 100:.1f}%"></i></div></div>'
        )
    out = ['<div class="podium">' + "".join(podium) + "</div>"]
    for i, (word, n) in enumerate(rows[3:], 4):
        out.append(
            f'<div class="tr"><span class="rk">{i}</span><span class="tw">{word}</span>'
            f'<span class="tb"><i style="width:{n / peak * 100:.1f}%"></i></span><span class="tn">{n} 篇</span></div>'
        )
    return "".join(out)


def treatment_mini() -> str:
    """海報 2 右側小卡：前四名療程與提到它的文章數。"""
    rows = DATA["top_treatments"][:4]
    peak = rows[0][1]
    return "".join(
        f'<div class="tm"><span class="tw">{w}</span><span class="tb"><i style="width:{n / peak * 100:.1f}%"></i></span><span class="tn">{n} 篇</span></div>'
        for w, n in rows
    )


def percent(key: str) -> str:
    s = DATA["sentiment"]
    total = s["positive"] + s["neutral"] + s["negative"]
    return f"{s[key] / total * 100:.1f}%"


def values() -> dict[str, str]:
    s = DATA["sentiment"]
    p = DATA["platforms"]
    scored = s["positive"] + s["neutral"] + s["negative"]
    y, m, d = DATA["as_of"].split("-")
    return {
        "ARTICLES": fmt(DATA["articles"]),
        "COMMENTS": fmt(DATA["comments"]),
        "CHUNKS": fmt(DATA["chunks"]),
        "BOARDS": str(DATA["boards"]),
        "SCORED": fmt(scored),
        "NEG_COUNT": fmt(s["negative"]),
        "POS": percent("positive"),
        "NEU": percent("neutral"),
        "NEG": percent("negative"),
        "PTT": fmt(p["ptt"]),
        "DCARD": fmt(p["dcard"]),
        "THREADS": fmt(p["threads"]),
        "MOBILE01": fmt(p["mobile01"]),
        "PTT_F": str(p["ptt"]),
        "DCARD_F": str(p["dcard"]),
        "THREADS_F": str(p["threads"]),
        "MOBILE01_F": str(p["mobile01"]),
        "AS_OF": f"{int(y) - 1911}/{m}/{d}",
        "PEAK_MONTH": max(DATA["monthly"], key=lambda r: r[1])[0][5:].lstrip("0"),
        "PEAK_COUNT": fmt(max(n for _, n in DATA["monthly"])),
        "BUBBLES": bubbles(),
        "BUBBLE_LEGEND": bubble_legend(),
        "MONTHLY": monthly_bars(),
        "SPARK": sparkline(),
        "DONUT_BIG": donut("donut", percent("positive"), "正面", 10),
        "DONUT_MINI": donut("mini-donut", "情緒", "", 13, big_label=True),
        "TREATMENTS": treatment_rows(),
        "TREAT_MINI": treatment_mini(),
    }


def main() -> None:
    vals = values()
    for name in ("poster2", "poster3"):
        tpl = HERE / f"{name}.tpl.html"
        if not tpl.exists():
            continue
        html = tpl.read_text(encoding="utf-8")
        for key, value in vals.items():
            html = html.replace("{{" + key + "}}", value)
        left = html.count("{{")
        (HERE / f"{name}.html").write_text(html, encoding="utf-8")
        print(name, "ok", f"(未替換 {left} 處)" if left else "")


if __name__ == "__main__":
    main()
