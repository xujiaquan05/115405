from pathlib import Path
from PIL import Image, ImageDraw
from pypdf import PdfReader
import json
work=Path(__file__).parent
out=work/'undergraduate-render';out.mkdir(exist_ok=True)
files=sorted(out.glob('page-*.png'))
for offset in range(0,len(files),4):
    group=files[offset:offset+4];ims=[Image.open(p) for p in group]
    width=max(im.width for im in ims);height=max(im.height for im in ims)
    sheet=Image.new('RGB',(width*2,(height+25)*2),'#dddddd');d=ImageDraw.Draw(sheet)
    for i,(p,im) in enumerate(zip(group,ims)):
        x=i%2*width;y=i//2*(height+25)
        d.text((x+6,y+5),p.stem,fill='black');sheet.paste(im,(x,y+25))
    sheet.save(out/f'review-{offset//4+1:02}.png')
r=PdfReader(work/'undergraduate-final.pdf');texts=[p.extract_text() for p in r.pages]
(work/'undergraduate-page-text.json').write_text(json.dumps(texts,ensure_ascii=False),encoding='utf-8')
print('Pages',len(texts),'PNGs',len(files))
print('Unresolved fields',[(i+1,t[:90]) for i,t in enumerate(texts) if '更新中' in t or 'Error!' in t or '錯誤!' in t])
print('Sparse',[(i+1,len(t)) for i,t in enumerate(texts) if len(t)<100])
for i,t in enumerate(texts):
    if 'AI01 Google' in t or '附錄D ' in t:print(i+1,t)
