"""產生海報用素材：QR Code（向量 SVG）與介面截圖裁切。

截圖一律取自 docs/demo-work/admin-male/screens（2026/10/07 實際系統畫面），
只做裁切，不修改畫面內容。
"""
from pathlib import Path

from PIL import Image, ImageFilter
from reportlab.graphics.barcode import qrencoder

ROOT = Path(__file__).resolve().parents[2]
SCREENS = ROOT / "docs/demo-work/admin-male/screens"
OUT = Path(__file__).parent / "assets"
OUT.mkdir(exist_ok=True)

SITE_URL = "https://mebod.clouda.dpdns.org"


def qr_svg(text: str, path: Path, color: str = "#1E1B4B") -> None:
    """輸出 QR Code 為 SVG，放大列印也不會糊。"""
    # 由小到大找第一個裝得下網址的版本，模組越少，印出來每格越大越好掃。
    for version in range(1, 11):
        try:
            qr = qrencoder.QRCode(version, qrencoder.QRErrorCorrectLevel.M)
            qr.addData(text)
            qr.make()
            break
        except Exception:
            continue
    n = qr.getModuleCount()
    quiet = 2
    size = n + quiet * 2
    cells = [
        f'<rect x="{c + quiet}" y="{r + quiet}" width="1.02" height="1.02"/>'
        for r in range(n)
        for c in range(n)
        if qr.isDark(r, c)
    ]
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        f'shape-rendering="crispEdges"><rect width="{size}" height="{size}" fill="#fff"/>'
        f'<g fill="{color}">{"".join(cells)}</g></svg>',
        encoding="utf-8",
    )


# (輸出檔名, 來源截圖, 裁切框 left, top, right, bottom)
CROPS = [
    ("shot-answer.png", "08-answer.png", 488, 380, 1236, 652),
    ("shot-sources.png", "09-sources.png", 488, 176, 1236, 505),
    ("shot-report.png", "11-report.png", 262, 156, 1148, 455),
    ("shot-topics.png", "04-sentiment.png", 186, 180, 1316, 590),
    ("shot-trend.png", "03-trend.png", 186, 198, 1316, 578),
    ("shot-laptop.png", "02-search.png", 0, 0, 1412, 891),
]


def upscale(image: Image.Image, factor: int = 2) -> Image.Image:
    """以 Lanczos 放大並輕微銳化。

    原始截圖約 1,400 px 寬，印在 37 cm 寬時只有約 95 dpi；
    交給瀏覽器即時放大會出現鋸齒，先在這裡放大較平滑。不會憑空增加細節。
    """
    big = image.resize((image.width * factor, image.height * factor), Image.LANCZOS)
    return big.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))


def main() -> None:
    qr_svg(SITE_URL, OUT / "qr.svg")
    for name, source, *box in CROPS:
        upscale(Image.open(SCREENS / source).convert("RGB").crop(tuple(box))).save(OUT / name)
        print(name, tuple(box))
    hero = ROOT / "output/pdf/poster-assets/MeBOD_beauty_data_illustration.png"
    upscale(Image.open(hero).convert("RGB")).save(OUT / "hero.png")


if __name__ == "__main__":
    main()
