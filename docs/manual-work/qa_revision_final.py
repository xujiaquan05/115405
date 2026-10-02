from pathlib import Path
from PIL import Image, ImageDraw
from pypdf import PdfReader
import json
root=Path(__file__).resolve().parent
pages=sorted((root/'revision-final-render').glob('page-*.png'))
for start in range(0,len(pages),4):
    group=pages[start:start+4]
    w,h=Image.open(group[0]).size
    sheet=Image.new('RGB',(w*2,(h+24)*2),'#dddddd')
    draw=ImageDraw.Draw(sheet)
    for i,p in enumerate(group):
        x=(i%2)*w;y=(i//2)*(h+24)
        draw.text((x+10,y+5),p.stem,fill='black')
        sheet.paste(Image.open(p),(x,y+24))
    sheet.save(root/'revision-final-render'/f'review-{start//4+1:02}.png')
pdf=PdfReader(root/'revision-final.pdf')
texts=[p.extract_text() for p in pdf.pages]
(root/'revision-final-page-text.json').write_text(json.dumps(texts,ensure_ascii=False),encoding='utf-8')
print('PDF pages',len(texts),'PNG pages',len(pages),'review sheets',(len(pages)+3)//4)
print('Short pages:',[(i+1,len(t)) for i,t in enumerate(texts) if len(t)<75])
print('Unresolved fields:',[(i+1,t[:100]) for i,t in enumerate(texts) if 'Error!' in t or '錯誤! 尚未' in t or '更新中' in t])
