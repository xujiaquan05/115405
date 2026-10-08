"""把三張海報依展板位置拼成示意圖，檢查整體配色與視覺動線。"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw

R = Path(__file__).parent / "review"
tag = sys.argv[1]
S = 8  # 每公分幾個像素
board = Image.new("RGB", (152 * S, 200 * S), "#E9E7EF")
d = ImageDraw.Draw(board)
def put(name, x, y, w, h):
    im = Image.open(R / name).convert("RGB").resize((w * S, h * S), Image.LANCZOS)
    board.paste(im, (x * S, y * S))
d.rectangle((2*S, 2*S, 97*S, 32*S), outline="#D07A2E", width=3)
put(sys.argv[2], 4, 4, 91, 26)
d.rectangle((14*S, 36*S, 64*S, 62*S), fill="#111")
d.text((30*S, 48*S), "SCREEN", fill="#fff")
d.rectangle((2*S, 66*S, 97*S, 131*S), outline="#D07A2E", width=3)
put(sys.argv[3], 4, 68, 91, 61)
d.rectangle((0, 132*S, 98*S, 200*S), fill="#CFCAD8")
d.rectangle((102*S, 2*S, 148*S, 198*S), outline="#D07A2E", width=3)
put(sys.argv[4], 104, 4, 42, 192)
board.save(R / f"booth-{tag}.png")
print("ok")
