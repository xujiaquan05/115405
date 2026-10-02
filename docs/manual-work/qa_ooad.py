from pathlib import Path
from PIL import Image,ImageDraw
from pypdf import PdfReader
import json
p=Path(__file__).parent
files=sorted((p/'ooad-render').glob('page-*.png'))
for offset in range(0,len(files),4):
 group=files[offset:offset+4];ims=[Image.open(f) for f in group]
 w=max(i.width for i in ims);h=max(i.height for i in ims)
 canvas=Image.new('RGB',(w*2,(h+25)*2),'#dddddd');d=ImageDraw.Draw(canvas)
 for j,(f,im) in enumerate(zip(group,ims)):
  x=j%2*w;y=j//2*(h+25);d.text((x+8,y+5),f.stem,fill='black');canvas.paste(im,(x,y+25))
 canvas.save(p/'ooad-render'/f'review-{offset//4+1:02}.png')
r=PdfReader(p/'ooad-review.pdf');texts=[pg.extract_text() for pg in r.pages]
(p/'ooad-page-text.json').write_text(json.dumps(texts,ensure_ascii=False),encoding='utf-8')
print('Pages',len(texts),'PNGs',len(files),'Sheets',(len(files)+3)//4)
print('Short',[(i+1,len(t)) for i,t in enumerate(texts) if len(t)<70])
print('Fields',[(i+1,t[:80]) for i,t in enumerate(texts) if '更新中' in t or 'Error!' in t])
for i,t in enumerate(texts):
 if any(z in t for z in ['第6章 設計模型','第7章 實作模型','第8章 資料庫設計','第9章 程式','第10章 測試模型']):print(i+1,t[:110])
