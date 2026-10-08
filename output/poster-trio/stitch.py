"""把 render.py --final 產生的分塊截圖拼成整張 300 dpi PNG，並依校方規定命名。

用系統 Python 執行（需要 Pillow）：
    python output\\poster-trio\\stitch.py

檔名規定：115405－海報1、115405－海報2、115405－海報3、115405－Logo（PNG 與 PDF 各一份）。
"""
import json
import shutil
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None  # 海報 3 在 300 dpi 約 1.1 億像素，超過 Pillow 預設警戒值

FINAL = Path(__file__).parent / "final"
NAMES = {"poster1": "115405－海報1", "poster2": "115405－海報2", "poster3": "115405－海報3"}
DPI = 300


def stitch(poster: str) -> None:
    tiles = json.loads((FINAL / f"_tiles_{poster}.json").read_text())
    images = [Image.open(FINAL / t).convert("RGB") for t in tiles]
    width = images[0].width
    canvas = Image.new("RGB", (width, sum(im.height for im in images)), "white")
    y = 0
    for im in images:
        canvas.paste(im, (0, y))
        y += im.height
    out = FINAL / f"{NAMES[poster]}.png"
    canvas.save(out, dpi=(DPI, DPI), optimize=True)
    shutil.move(FINAL / f"{poster}.pdf", FINAL / f"{NAMES[poster]}.pdf")
    for t in tiles:
        (FINAL / t).unlink()
    (FINAL / f"_tiles_{poster}.json").unlink()
    print(out.name, canvas.size, f"{canvas.width / DPI * 2.54:.1f} x {canvas.height / DPI * 2.54:.1f} cm")


if __name__ == "__main__":
    for name in NAMES:
        if (FINAL / f"_tiles_{name}.json").exists():
            stitch(name)
