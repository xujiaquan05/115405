"""重繪圖6-15：AI問答在Dashboard範圍內混合檢索的分支循序（115/10/12程式修正後）。

沿用 uniform_manual.py 的 seq 繪圖函式與配色，只替換事件內容。
"""
import math, re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

WORK = Path(__file__).parent
INK = '#23364D'; BLUE = '#EAF2FA'; FONT = 'C:/Windows/Fonts/msjh.ttc'
U = WORK / 'uniform-figures'; U.mkdir(exist_ok=True)

src = (WORK / 'uniform_manual.py').read_text(encoding='utf8')
code = src[src.index('def ft(n)'):src.index('def sequence(name')]
g = dict(Image=Image, ImageDraw=ImageDraw, ImageFont=ImageFont, math=math, re=re, INK=INK, BLUE=BLUE, FONT=FONT, U=U)
exec(code, g)

actors = ['問答畫面', 'qa路由', 'rag_service', '快取／DB', 'Gemini']
events = [
    (0, 1, 'POST ask＋脈絡', False),
    (1, 3, '驗證帳號與額度', False),
    (1, 2, 'answer_question', False),
    (2, 3, '查RAM快取', False),
    (3, 2, '命中回答', True),
    (2, 4, '解析問題意圖', False),
    (2, 3, 'Dashboard範圍內混合檢索（RRF）', False),
    (2, 4, '依檢索文章生成', False),
    (4, 2, '回答及檢索來源', True),
    (2, 4, '依Dashboard脈絡生成', False),
    (4, 2, '脈絡回答', True),
    (2, 1, '統一結果', True),
    (1, 3, 'record_qa_usage／commit', False),
    (1, 0, '回答、來源、cached', True),
]
frames = [(4, 10, 'alt', [(4, '[快取命中且允許使用]'), (5, '[未命中：先解析問題並在Dashboard範圍內檢索]'), (9, '[檢索結果為空時改依Dashboard脈絡]')])]
g['seq']('seq_qa_v2', actors, events, frames)
print(U / 'seq_qa_v2.png')
