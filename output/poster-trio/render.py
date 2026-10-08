"""把海報 HTML 輸出成 PDF（向量）與 PNG。

需用 backend/venv 的 Python 執行（裡面才有 Playwright 與 Chromium）：
    backend\\venv\\Scripts\\python.exe output\\poster-trio\\render.py poster1 --dpi 40 --tag v01
    backend\\venv\\Scripts\\python.exe output\\poster-trio\\render.py poster1 --final

一般預覽只輸出單張 PNG；--final 另外輸出 300 dpi 的分塊截圖，
再由 stitch.py（系統 Python，有 Pillow）拼成整張，
因為 Chromium 單張截圖超過 16384 px 會失敗，海報 3 在 300 dpi 下高達 22677 px。
"""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
SIZES_CM = {"poster1": (91, 26), "poster2": (91, 61), "poster3": (42, 192), "logo": (31, 10)}
CSS_PX_PER_CM = 96 / 2.54
TILE_PX = 3000


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("poster", choices=SIZES_CM)
    parser.add_argument("--dpi", type=int, default=40)
    parser.add_argument("--tag", default="draft")
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()

    width_cm, height_cm = SIZES_CM[args.poster]
    width_px = round(width_cm * CSS_PX_PER_CM)
    height_px = round(height_cm * CSS_PX_PER_CM)
    dpi = 300 if args.final else args.dpi
    scale = dpi / 96
    url = (HERE / f"{args.poster}.html").resolve().as_uri()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": width_px, "height": height_px}, device_scale_factor=scale
        )
        page.goto(url)
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(400)

        # 版面檢查：任何文字元素超出其容器、或超出頁面範圍，都列出來。
        problems = page.evaluate(
            """() => {
              const out = [];
              const W = document.documentElement.clientWidth, H = document.documentElement.clientHeight;
              for (const el of document.querySelectorAll('body *')) {
                const r = el.getBoundingClientRect();
                if (!r.width || !r.height) continue;
                if (r.right > W + 1 || r.bottom > H + 1 || r.left < -1 || r.top < -1)
                  out.push('超出頁面: ' + el.tagName + '.' + el.className + ' ' + (el.textContent||'').trim().slice(0,20));
                if (el.scrollWidth > el.clientWidth + 2 && getComputedStyle(el).overflow !== 'visible')
                  out.push('內容溢出: ' + el.className + ' ' + (el.textContent||'').trim().slice(0,20));
              }
              return out.slice(0, 30);
            }"""
        )
        for line in problems:
            print("  !", line)

        # 四邊實際留白（cm）：所有可見元素的外框，與頁面邊緣的距離。
        margins = page.evaluate(
            """() => {
              let l = 1e9, t = 1e9, r = 0, b = 0;
              for (const el of document.querySelectorAll('.wrap > *, body > :not(.wrap):not(.hero):not(.bg)')) {
                const x = el.getBoundingClientRect();
                if (!x.width || !x.height) continue;
                l = Math.min(l, x.left); t = Math.min(t, x.top); r = Math.max(r, x.right); b = Math.max(b, x.bottom);
              }
              const W = document.documentElement.clientWidth, H = document.documentElement.clientHeight;
              return [l, t, W - r, H - b];
            }"""
        )
        print("  margins cm (L,T,R,B):", [round(v / CSS_PX_PER_CM, 2) for v in margins])

        if args.final:
            out_dir = HERE / "final"
            out_dir.mkdir(exist_ok=True)
            page.pdf(
                path=str(out_dir / f"{args.poster}.pdf"),
                width=f"{width_cm}cm",
                height=f"{height_cm}cm",
                print_background=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            )
            if args.poster == "logo":
                # Logo 尺寸小，一張截圖即可；保留透明背景，方便放到任何底色上。
                (out_dir / "logo.pdf").replace(out_dir / "115405－Logo.pdf")
                page.screenshot(path=str(out_dir / "115405－Logo.png"), omit_background=True)
                print("logo done")
                browser.close()
                return
            tiles = []
            step = TILE_PX / scale
            y = 0.0
            index = 0
            while y < height_px:
                h = min(step, height_px - y)
                name = f"_tile_{args.poster}_{index:02d}.png"
                page.screenshot(
                    path=str(out_dir / name),
                    clip={"x": 0, "y": y, "width": width_px, "height": h},
                )
                tiles.append(name)
                y += step
                index += 1
            (out_dir / f"_tiles_{args.poster}.json").write_text(json.dumps(tiles))
            print("final pdf + tiles:", len(tiles))
        else:
            out = HERE / "review" / f"{args.poster}-{args.tag}.png"
            page.screenshot(path=str(out), full_page=False)
            print(out.name)

        browser.close()


if __name__ == "__main__":
    main()
