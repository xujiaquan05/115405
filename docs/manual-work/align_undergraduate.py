from pathlib import Path
import re, math
from copy import deepcopy
from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.shared import Cm, Pt
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH

W=Path(__file__).parent
OUT=W.parent/'MeBOD_115年系統手冊_大學部物件導向修訂版.docx'
doc=Document(W.parent/'MeBOD_115年系統手冊_大學部核對底稿.docx')
F=lambda n:ImageFont.truetype('C:/Windows/Fonts/kaiu.ttf',n)
figdir=W/'undergraduate-figures';figdir.mkdir(exist_ok=True)

def activity(name, actions, question, yes, no, ending):
    im=Image.new('RGB',(1600,1330),'white');d=ImageDraw.Draw(im)
    def text(x,y,s,size=34):
        for line in s.split('\n'):
            b=d.textbbox((0,0),line,font=F(size));d.text((x-(b[2]-b[0])/2,y),line,font=F(size),fill='black');y+=size+10
    def arrow(a,b):
        d.line([a,b],fill='black',width=4);angle=math.atan2(b[1]-a[1],b[0]-a[0]);l=17
        d.polygon([b,(b[0]-l*math.cos(angle-.5),b[1]-l*math.sin(angle-.5)),(b[0]-l*math.cos(angle+.5),b[1]-l*math.sin(angle+.5))],fill='black')
    d.ellipse((782,10,818,46),fill='black');arrow((800,46),(800,80))
    for i,s in enumerate(actions):
        y=80+i*145;d.rounded_rectangle((380,y,1220,y+105),radius=25,outline='black',width=3,fill='#F0F4F8');text(800,y+17,s)
        arrow((800,y+105),(800,y+145))
    y=80+len(actions)*145
    d.polygon([(800,y),(1060,y+100),(800,y+200),(540,y+100)],outline='black',fill='white',width=3);text(800,y+62,question)
    for x,s,label in [(380,yes,'[是]'),(1220,no,'[否]')]:
        edge=(540,y+100) if x==380 else (1060,y+100)
        d.line([edge,(x,y+100)],fill='black',width=4);arrow((x,y+100),(x,y+255));text(x+80,y+158,label,30)
        d.rounded_rectangle((x-330,y+255,x+330,y+385),radius=25,outline='black',width=3,fill='#F0F4F8');text(x,y+277,s,32)
        d.line([(x,y+385),(x,y+455)],fill='black',width=4);arrow((x,y+455),(775 if x<800 else 825,y+455))
    d.polygon([(800,y+430),(825,y+455),(800,y+480),(775,y+455)],fill='white',outline='black',width=3)
    arrow((800,y+480),(800,y+563));text(1130,y+505,ending,30)
    d.ellipse((776,y+563,824,y+611),outline='black',width=4);d.ellipse((786,y+573,814,y+601),fill='black')
    im.crop((0,0,1600,y+640)).save(figdir/f'{name}.png')

activity('login',['使用者輸入帳號與密碼','系統檢查頻率 帳號狀態與密碼'],'驗證通過','設定登入 Cookie\n顯示帳號與儀表板','顯示 401 423 或 429\n保留重新輸入機會','本次登入操作結束')
activity('query',['輸入關鍵字 天數與平台看板','公開查詢並呈現統計與文章'],'要求匯出','驗證登入與方案\n通過才裁切天數及下載','保留查詢畫面\n可檢視文章與統計','本次查詢操作結束')
activity('history',['開啟個人歷史畫面','前端確認目前登入狀態'],'已登入','讀取本人的歷史\n刪除時再檢查 id 與 user_id','顯示登入提示\n不送出私人歷史請求','本次歷史操作結束')
activity('monitor',['會員輸入監測關鍵字','檢查本人的重複詞與方案組數'],'允許新增','保存本人監測詞\n後續依門檻建立預警','回應重複或額度原因\n不新增監測資料','本次新增監測操作結束')
activity('qa',['先驗證登入 頻率與方案額度','依問題 脈絡及最近六筆歷史查快取'],'有效快取命中','直接取出快取回答\n不再次呼叫模型生成','有脈絡則直接生成\n無脈絡則混合檢索後生成','正常返回後記錄用量')
activity('crawl',['管理員或排程驗證啟動條件','以 UUID 嘗試取得爬取租約'],'取得租約','爬取 更新並持續續租\n依工作類型後處理及釋放','本次不啟動爬取\n手動請求回應 409','詳第6章工作失敗及恢復')
activity('admin',['管理員開啟帳號或系統設定','後端驗證身分 權限及輸入'],'允許異動','儲存允許的異動\n依端點寫入稽核並更新畫面','回應驗證或權限錯誤\n不執行受保護的異動','本次管理操作結束')

def use_cases():
    im=Image.new('RGB',(1800,1500),'white');d=ImageDraw.Draw(im)
    d.rectangle((540,20,1260,1390),outline='black',width=3)
    def text(x,y,s,size=34):
        b=d.textbbox((0,0),s,font=F(size));d.text((x-(b[2]-b[0])/2,y),s,font=F(size),fill='black')
    text(900,30,'MeBOD 系統邊界',38)
    cases=['UC01 登入與登出','UC02 查詢與匯出','UC03 輿情問答','UC05 歷史與監測','UC06 帳號與系統設定','UC04 爬取與維護']
    ys=[100+i*210 for i in range(6)]
    for x,y,links in [(160,250,[1]),(160,780,[0,1,2,3]),(1640,600,[0,1,2,3,4,5]),(1640,1170,[5])]:
        for idx in links:d.line((x+50 if x<900 else x-50,y+50,600 if x<900 else 1200,ys[idx]+70),fill='#555555',width=3)
    for s,y in zip(cases,ys):
        d.ellipse((600,y,1200,y+140),fill='#F0F4F8',outline='black',width=3);text(900,y+47,s,34)
    for x,y,label in [(160,250,'訪客'),(160,780,'一般帳號'),(1640,600,'管理員'),(1640,1170,'排程器')]:
        d.ellipse((x-23,y-60,x+23,y-14),fill='white',outline='black',width=3);d.line((x,y-14,x,y+65),fill='black',width=3);d.line((x-50,y+20,x+50,y+20),fill='black',width=3);d.line((x,y+65,x-40,y+120),fill='black',width=3);d.line((x,y+65,x+40,y+120),fill='black',width=3);text(x,y+135,label)
    text(900,1420,'訪客僅能查詢；匯出、問答及監測仍須通過帳號方案檢查',29)
    im.save(figdir/'usecase.png')
use_cases()

def analysis_classes():
    im=Image.new('RGB',(1800,1160),'white');d=ImageDraw.Draw(im)
    labels=[['«boundary»\n登入介面','«control»\n登入控制','«entity»\n使用者'],['«boundary»\n查詢與問答介面','«control»\n查詢與回答控制','«entity»\n文章'],['«boundary»\n個人歷史介面','«control»\n歷史管理控制','«entity»\n分析歷史'],['«boundary»\n監測設定介面','«control»\n監測管理控制','«entity»\n監測詞與預警']]
    for row,group in enumerate(labels):
        y=40+row*275
        for col,s in enumerate(group):
            x=45+col*600;d.rectangle((x,y,x+480,y+170),outline='black',width=3,fill='#F0F4F8')
            for j,line in enumerate(s.split('\n')):
                b=d.textbbox((0,0),line,font=F(36));d.text((x+240-(b[2]-b[0])/2,y+30+j*55),line,font=F(36),fill='black')
            if col<2:d.line((x+480,y+85,x+600,y+85),fill='black',width=3)
    im.save(figdir/'analysis_detail.png')
analysis_classes()

def find(text):
    return next(p for p in doc.paragraphs if p.text==text)
def insert(before,text='',style='Normal'):
    return before.insert_paragraph_before(text,style)
def fig(before,name,title):
    p=insert(before);p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.keep_with_next=True;p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(figdir/f'{name}.png'),width=Cm(16))
    insert(before,title,'Figure Caption')
def table(before,headers,rows,widths=None):
    # Reuse an existing table's formatting contract, without its content.
    t=doc.add_table(rows=1,cols=len(headers));t.autofit=False
    original=doc.tables[0]
    t._tbl.remove(t._tbl.tblPr);t._tbl.insert(0,deepcopy(original._tbl.tblPr))
    widths=widths or [18/len(headers)]*len(headers)
    for col,w in zip(t.columns,widths):col.width=Cm(w)
    for i,row in enumerate([headers]+rows):
        cells=t.rows[0].cells if i==0 else t.add_row().cells
        for cell,val,w in zip(cells,row,widths):
            cell.width=Cm(w);p=cell.paragraphs[0];p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.space_after=Pt(4)
            r=p.add_run(val);r.bold=i==0;r.font.size=Pt(14)
            if i==0:
                sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'E7EDF3');cell._tc.get_or_add_tcPr().append(sh)
        pr=t.rows[i]._tr.get_or_add_trPr();pr.append(OxmlElement('w:cantSplit'))
        if i==0:pr.append(OxmlElement('w:tblHeader'))
    before._p.addprevious(t._tbl)
    insert(before)
    return t

# Exact undergraduate outline numbering, retaining the detailed material.
p=find('6-1 物件導向分析與設計的方法')
insert(p,'6-1 循序圖','Heading 2')
for p in doc.paragraphs:
    if p.style.name=='Heading 2' and re.match(r'6-[1-8] ',p.text) and p.text!='6-1 循序圖':
        n=p.text.split()[0].split('-')[1];p.text=re.sub(r'^6-\d+',f'6-1-{n}',p.text);p.style='Heading 3'
    elif re.match(r'^6-3-\d ',p.text):
        p.text=p.text.replace('6-3-','6-1-3-',1);p.style='Normal';p.runs[0].bold=True
    elif p.text=='6-9 設計類別與責任分配':p.text='6-2 設計類別圖與責任分配'
    elif p.text=='7-1 部署節點與執行環境':p.text='7-1 佈署圖與執行環境'
    elif p.text=='7-2 套件與相依方向':p.text='7-2 套件圖與相依方向'
    elif p.text=='7-3 元件與介面責任':p.text='7-3 元件圖與介面責任'
    elif p.text=='7-5 租約狀態機與競爭處理':p.text='7-4 狀態機';insert(p,'')
    elif p.text=='7-6 文章資料的狀態與恢復':p.text='7-4-2 文章狀態與恢復';p.style='Heading 3'
    elif p.text=='7-7 多行程與失敗邊界':p.text='7-6 多行程與失敗邊界'
    elif p.text=='8-1 資料庫總體模型與閱讀順序':p.text='8-1 資料庫關聯表與限制'
    elif p.text=='8-2 表格及其欄位定義':p.text='8-2 表格及其 Meta data'
start=find('7-4 啟動 請求與關閉程序');start.text='7-5 啟動 請求與關閉程序'
stop=find('7-4 狀態機');dest=find('7-6 多行程與失敗邊界')
el=start._p;move=[]
while el is not stop._p:
    move.append(el);el=el.getnext()
for el in move:dest._p.addprevious(el)
insert(find('7-4-2 文章狀態與恢復'),'')
first=find('7-4 狀態機')._p.getnext()
from docx.text.paragraph import Paragraph
for caption,name in [('問答活動圖','qa'),('爬取活動圖','crawl'),('系統角色與使用個案','usecase')]:
    p=next(p for p in doc.paragraphs if p.style.name=='Figure Caption' and p.text.endswith(caption))
    pic=Paragraph(p._p.getprevious(),doc._body);pic.clear();pic.add_run().add_picture(str(figdir/f'{name}.png'),width=Cm(16))
insert(Paragraph(first,doc._body),'7-4-1 租約狀態與競爭處理','Heading 3')
for t in doc.tables:
    for row in t.rows:
        for c in row.cells:
            for p in c.paragraphs:
                p.text=p.text.replace('本章6-2與6-3','本章6-1-2與6-1-3').replace('本章6-4至6-8','本章6-1-4至6-1-8').replace('6-9及第7章','6-2及第7章')

# All five documented use cases now have activity coverage.
fig(find('UC02 儀表板搜尋與匯出'),'login','圖5-X UC01 登入活動圖')
fig(find('UC03 輿情問答'),'query','圖5-X UC02 查詢與匯出活動圖')
anchor=find('5-4 分析類別圖')
fig(anchor,'history','圖5-X UC05 個人歷史活動圖')
insert(anchor,'刪除歷史時，找不到本人資料即回404；成功刪除後重新整理清單。登入失效則顯示登入提示。這些活動描述使用者與系統間的流程，資料庫交易與詳細訊息順序另見第6章。')
fig(anchor,'monitor','圖5-X UC05 監測詞建立活動圖')
insert(anchor,'監測詞的擁有者檢查已實作；預警的手動檢查與已讀異動仍有跨帳號隔離缺口，詳見6-1-8。活動圖的新增成功不代表所有預警操作已通過安全驗收。')
insert(anchor,'UC06 帳號與系統設定','Heading 3')
insert(anchor,'主要角色為管理員，前置條件為有效管理員帳號。管理員開啟帳號或系統設定畫面，讀取目前值、輸入變更並確認送出。後端依端點驗證角色與欄位，通過才提交異動，並依實作寫入操作稽核；前端重新讀取資料顯示結果。未登入回401、權限不足回403，欄位錯誤則呈現對應驗證訊息。一般帳號不能藉由自行呼叫API取得管理權限；完整畫面操作見12-10及12-11。')
fig(anchor,'admin','圖5-X UC06 帳號與系統設定活動圖')
anchor=find('第6章 設計模型')
fig(anchor,'analysis_detail','圖5-X 使用個案對應的分析類別與協作')
insert(anchor,'分析階段以概念類別呈現各個使用案例的邊界、控制與實體協作，實線表示參與關聯，並非呼叫時間順序。使用者、文章及分析歷史等概念在設計階段對應實際ORM類別；控制概念則可由多個路由與服務函式共同實作。此圖不表示每個框都已存在同名Python類別，實際類別與資料多重性見6-2及第8章。')

# Correct a legacy activity description that contradicted the detailed scheduler analysis.
for p in doc.paragraphs:
    if p.text.startswith('管理員或排程器啟動工作前取得租約鎖。'):
        p.text='管理員或排程器啟動爬取前取得租約鎖，按平台與看板取得資料並更新文章與留言。工作需續租，失去租約則停止受保護工作。手動與每日排程的後處理及釋放時機不同，詳見6-1-7；不可將每日情緒、向量與預警等全部後處理視為仍持有爬取鎖。'

# Fillable team records; unknown names and proportions remain explicit.
anchor=find('4-3 上傳 GitHub 紀錄')
insert(anchor,'表4-X 組員工作與貢獻度登錄','Table Caption')
table(anchor,['身分及學號姓名','實際工作內容','貢獻度'],[['組長：待填','依本人完成產出填寫，100字以內','待填 %'],['組員：待填','依本人完成產出填寫，100字以內','待填 %'],['其他組員：按實際人數增列','由全體確認工作範圍與證據','待填 %'],['合計','成員確認後填入','100 %']],[5,10,3])
insert(anchor,'具名分工表須由團隊填入學號與姓名，並以●表示每項唯一主要負責人、〇表示最多兩位協作人員。前表為責任角色，不代替具名簽認。')
anchor=find('第5章 需求模型')
insert(anchor,'GitHub繳交證據須補各成員帳號、對應學號姓名、期間及貢獻頁面截圖，並保留可查詢的提交網址。上述本機提交摘要不證明已推送遠端，也不代表全體成員的個別貢獻。')

# Native bookmark / PAGEREF disclosure, so pagination remains maintainable.
for n in range(1,15):
    p=next(p for p in doc.paragraphs if p.style.name=='Heading 1' and p.text.startswith(f'第{n}章 '))
    start=OxmlElement('w:bookmarkStart');start.set(qn('w:id'),str(900+n));start.set(qn('w:name'),f'UGChapter{n}')
    end=OxmlElement('w:bookmarkEnd');end.set(qn('w:id'),str(900+n));p._p.append(start);p._p.append(end)
    following=p._p.getnext()
    while following is not None:
        if following.tag==qn('w:p'):
            note=Paragraph(following,doc._body)
            if note.style.name=='Normal' and note.text.strip():
                note.add_run('〔AI02〕')
                if n in [3,5,6,9]:note.add_run('〔AI01〕')
                break
        following=following.getnext()

old=find('附錄B 人工智慧使用說明');old.text='附錄B 人工智慧揭露索引'
el=old._p.getnext();end=find('附錄C 交付與維護檢核')._p
while el is not end:
    nex=el.getnext();el.getparent().remove(el);el=nex
insert(find('附錄C 交付與維護檢核'),'人工智慧使用工具、範圍、頁碼及內文序號統一列於第14章。Claude僅出現在既有文件的歷史敘述，尚待團隊確認，未列為本次已確認的使用工具。')
anchor=find('附錄')
insert(anchor,'14-1 人工智慧輔助使用說明','Heading 2')
insert(anchor,'使用情形：■使用人工智慧科技做為輔助作品產出之工具　□未使用。內文以〔AI01〕與〔AI02〕標示相應工具；頁碼由Word交互參照更新。')
insert(anchor,'表14-X 人工智慧工具使用範圍與頁碼','Table Caption')
t=table(anchor,['序號與工具','使用範圍及說明','頁碼'],[['AI01 Google Gemini','系統執行時的情緒、意圖、向量與問答功能，詳第3、5、6、9章。',''],['AI02 Codex','協助程式檢查與文件撰寫、UML與資料表整理；涵蓋全文。程式測試結果僅適用第10章所列日期與範圍。','']],[3.8,9.5,4.7])
def pageref(p,name):
    fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),f'PAGEREF {name} \\h');r=OxmlElement('w:r');tx=OxmlElement('w:t');tx.text='更新中';r.append(tx);fld.append(r);p._p.append(fld)
p=t.cell(1,2).paragraphs[0]
for i,n in enumerate([3,5,6,9]):
    if i:p.add_run('、')
    pageref(p,f'UGChapter{n}')
p.add_run('起')
p=t.cell(2,2).paragraphs[0];p.add_run('1 至 ')
pageref(p,'UGLast');p.add_run('，全文')

# Separate formal review records from engineering self-review.
anchor=find('附錄B 人工智慧揭露索引')
insert(anchor,'表附-X 初評與複評意見修正登錄','Table Caption')
table(anchor,['審查階段與日期','評審建議事項','修正情形及位置'],[['初評：待填','依評審原文登錄','待填修正章節、頁碼與驗證結果'],['複評：待填','依評審原文登錄','待填修正章節、頁碼與驗證結果']],[4,7,7])

# A concise evidence-based conformance matrix, not an unsupported pass certificate.
p=doc.add_paragraph('附錄D 大學部物件導向大綱核對','Heading 2')
doc.add_paragraph('本表依115年系統手冊中「大學部－系統手冊大綱（物件導向）」核對。初評以第1至8章為主，複評需完整章節且至少50頁。分析物件圖、設計物件圖、時序圖在原文以「甚至」列為延伸；本版使用必要的分析類別、設計類別與狀態機。')
anchor=doc.add_paragraph('以下資料仍須由團隊補齊或確認，不能以本手冊取代：封面姓名、具名分工與貢獻度、各組員GitHub截圖、正式評審意見，以及最終繳交附件。')
insert(anchor,'表附-X 大學部物件導向必備內容核對','Table Caption')
table(anchor,['原大綱要求','本手冊位置','核對結果'],[
['封面與三項目錄','封面、目錄、圖目錄、表目錄','具備；姓名待填'],
['第1至4章','1-1至4-3','內容具備；具名紀錄待填'],
['5-1 功能與非功能需求','5-1','分開列示'],
['5-2 使用個案图','5-2','具備角色與個案'],
['5-3 活動圖描述個案','5-3','六項UC均有活動圖涵蓋'],
['5-4 分析類別圖','5-4','邊界、控制、實體責任'],
['6-1 循序或通訊圖','6-1','系統與詳細循序圖'],
['6-2 設計類別圖','6-2','ORM關聯與爬蟲繼承'],
['7-1至7-4 實作模型','7-1至7-4','佈署、套件、元件、狀態機'],
['8-1 關聯與限制','8-1及8-4至8-6','總圖、外鍵、交易與限制'],
['8-2 Meta data','8-2','逐表欄位、型別、鍵與NULL'],
['9-1與9-2 程式元件','9-1與9-2','元件及附屬元件規格'],
['10-1與10-2 測試模型','第10章','方法、案例、結果及限制'],
['操作與使用手冊','第11及12章','安裝管理、畫面與轉移'],
['感想與參考資料','第13及14章','具備；第14章含AI揭露'],
['附錄評審修正','附錄A','登錄表具備；待正式意見']],[5.5,4,8.5])
doc.add_paragraph('格式核對：中文標楷體，英文Times New Roman；章18點、節16點、內文及目錄14點；圖名在圖下、表名在表上。資料庫總覽保留A3橫向折頁以利閱讀，屬相對於範本A4版面的例外，送印前應確認教師是否接受；圖內文字依圖幅配置。')
doc.add_paragraph('最終附件核對：VPP或VPD原生模型檔尚未提供；本手冊圖片不能替代。PostgreSQL應交付可還原備份與遷移，MDF及LDF屬其他資料庫格式，替代方式須向教師確認。簡報PDF、系統簡介PDF、手冊PDF或Markdown、軟體元件及可完整安裝的交付包仍需按最新公告整理。第11章指令說明尚不等同已驗收的安裝程式。')
p=doc.add_paragraph('核對日期：中華民國115年9月29日。')
bs=OxmlElement('w:bookmarkStart');bs.set(qn('w:id'),'999');bs.set(qn('w:name'),'UGLast');be=OxmlElement('w:bookmarkEnd');be.set(qn('w:id'),'999');p._p.append(bs);p._p.append(be)

# Caption sequences and strict text sizing, avoiding the old 11pt dictionaries.
chapter='0';fig_n=table_n=0
for p in doc.paragraphs:
    if p.style.name=='Heading 1':
        m=re.match(r'第(\d+)章',p.text);chapter=m.group(1) if m else '附';fig_n=table_n=0
    if p.style.name=='Figure Caption':fig_n+=1;p.text=re.sub(r'^圖\S+\s*',f'圖{chapter}-{fig_n} ',p.text)
    if p.style.name=='Table Caption':table_n+=1;p.text=re.sub(r'^表\S+\s*',f'表{chapter}-{table_n} ',p.text)
    if p.text=='中華民國115年9月28日':p.text='中華民國115年9月29日'
    if p.style.name=='Code':
        # Quoted source code remains content-identical; line wrapping is visual.
        p.paragraph_format.keep_with_next=False
        for r in p.runs:r.font.name='Times New Roman';r.font.size=Pt(14)
for t in doc.tables:
    for row in t.rows:
        for c in row.cells:
            for p in c.paragraphs:
                for r in p.runs:r.font.size=Pt(14);r.font.name='Times New Roman'
doc.core_properties.subject='大學部 系統手冊 物件導向'
doc.styles['Normal'].paragraph_format.space_after=Pt(4)
doc.save(OUT)
print(OUT)
