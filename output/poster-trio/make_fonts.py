"""從系統的 Noto Sans TC 變數字型切出各字重的靜態 TrueType 檔。

為什麼要切：Chromium 把變數字型嵌進 PDF 時一律轉成 Type3，
部分印刷輸出機處理 Type3 會變慢或失真；靜態字型則以標準 CID 字型嵌入。
字型檔每個約 7 MB，不放進版本控制，重新產生即可：
    pip install fonttools
    python output\\poster-trio\\make_fonts.py

Noto Sans TC 採 SIL Open Font License，允許嵌入與再散布。
"""
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

SOURCE = "C:/Windows/Fonts/NotoSansTC-VF.ttf"
OUT = Path(__file__).parent / "assets" / "fonts"
WEIGHTS = (400, 500, 600, 700, 800, 900)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for weight in WEIGHTS:
        font = instancer.instantiateVariableFont(TTFont(SOURCE), {"wght": weight}, updateFontNames=False)
        # 改名，避免與系統已安裝的變數字型同名而被瀏覽器混用
        for record in font["name"].names:
            if record.nameID in (1, 4, 16):
                record.string = f"MeBOD Noto TC {weight}"
            if record.nameID == 6:
                record.string = f"MeBODNotoTC-{weight}"
        font.save(OUT / f"NotoSansTC-{weight}.ttf")
        print(weight, "ok")


if __name__ == "__main__":
    main()
