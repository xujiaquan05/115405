"""Deterministic UML diagrams and schema-derived overview, embedded by builder."""
_original_txt=txt
def txt(d,xy,text,size=34,width=400,center=True):
    return _original_txt(d,(xy[0]+width/2 if center else xy[0],xy[1]),text,size,width,center)
def dash(d,a,b,fill='#64748B',width=2):
    dx,dy=b[0]-a[0],b[1]-a[1]; length=math.hypot(dx,dy)
    for n in range(0,int(length),15):
        t=n/length;u=min(n+8,length)/length
        d.line((a[0]+dx*t,a[1]+dy*t,a[0]+dx*u,a[1]+dy*u),fill=fill,width=width)

def ua(d,a,b,label='',dotted=False,size=28):
    (dash if dotted else lambda d,a,b:d.line((a,b),fill='#334155',width=3))(d,a,b)
    dx,dy=b[0]-a[0],b[1]-a[1];l=max(1,math.hypot(dx,dy));ux,uy=dx/l,dy/l
    pts=[(b[0]-20*ux-9*uy,b[1]-20*uy+9*ux),b,(b[0]-20*ux+9*uy,b[1]-20*uy-9*ux)]
    d.line(pts,fill='#334155',width=3)
    if label:txt(d,((a[0]+b[0])/2-180,(a[1]+b[1])/2-40),label,size,360,True)

def sequence(name,actors,events,frames=()):
    h=240+len(events)*104;im,d=canvas(h);xs=[110+i*(1580/(len(actors)-1)) for i in range(len(actors))]
    for x,label in zip(xs,actors):
        d.rectangle((x-100,20,x+100,125),fill='#EFF6FF',outline='#334155',width=2)
        txt(d,(x-95,35),label,27,190,True);dash(d,(x,125),(x,h-35))
    for k,(a,b,label,ret) in enumerate(events):
        y=190+k*104
        if not ret:d.rectangle((xs[b]-7,y-12,xs[b]+7,y+34),fill='#CBD5E1',outline='#475569',width=2)
        ua(d,(xs[a],y),(xs[b],y),'',ret)
        txt(d,(min(xs[a],xs[b])+12,y-30),label,28,max(160,abs(xs[a]-xs[b])-24),False)
    for start,end,kind,label,divs in frames:
        top=122+start*104;bottom=235+end*104
        d.rectangle((12,top,1788,bottom),outline='#475569',width=2)
        d.rectangle((12,top,100,top+34),fill='white',outline='#475569',width=2)
        txt(d,(18,top+2),kind,26,78,False);txt(d,(120,top+3),label,25,1500,False)
        for row,guard in divs:
            yy=122+row*104;dash(d,(12,yy),(1788,yy));txt(d,(120,yy+2),guard,25,1500,False)
    im.save(FIG/(name+'.png'))

sequence('ssd_query',['使用者',':MeBOD'],[(0,1,'searchDashboard(關鍵字、篩選)',False),(1,0,'儀表板資料',True),(0,1,'askQuestion(問題、脈絡)',False),(1,0,'回答與來源',True),(1,0,'401或額度拒絕',True)],[(3,4,'alt','[已登入且有額度]',[(4,'[未登入或額度不足]')])])
sequence('ssd_crawl',['管理員',':MeBOD'],[(0,1,'startCrawl(平台、看板)',False),(1,0,'started=true',True),(1,0,'進度事件（WebSocket）',True),(1,0,'完成事件及可查日誌',True),(1,0,'409工作忙碌',True)],[(1,4,'alt','[取得租約]',[(4,'[租約被占用]')])])
sequence('seq_login',['登入畫面','auth路由','auth_service','User／DB'],[(0,1,'POST login',False),(1,2,'authenticate_user',False),(2,3,'讀取帳號及驗證狀態',False),(3,2,'帳號資料',True),(2,3,'重設失敗狀態並提交',False),(2,1,'LoginResult(ok)',True),(1,3,'更新last_login_at',False),(1,0,'JWT Cookie及帳號資料',True),(2,1,'invalid／locked',True),(1,0,'401／423',True)],[(4,9,'alt','[驗證成功]',[(8,'[驗證失敗或仍鎖定]')])])
sequence('seq_qa',['問答畫面','qa路由','rag_service','快取／DB','Gemini'],[(0,1,'POST ask',False),(1,3,'驗證帳號與額度',False),(1,2,'answer_question',False),(2,3,'查RAM快取',False),(3,2,'命中回答',True),(2,4,'依dashboard_context生成',False),(4,2,'脈絡回答',True),(2,3,'關鍵字＋向量檢索',False),(2,4,'依檢索證據生成',False),(4,2,'回答及來源',True),(2,1,'統一結果',True),(1,3,'record_qa_usage／commit',False),(1,0,'回答、來源、cached',True)],[(4,9,'alt','[快取命中且允許使用]',[(5,'[未命中且有dashboard_context]'),(7,'[未命中且無dashboard_context]')])])
sequence('seq_crawl',['管理員','管理路由','背景工作','DB／租約','來源網站'],[(0,1,'啟動指定看板',False),(1,3,'取鎖＋稽核',False),(1,2,'登記BackgroundTasks',False),(1,0,'started=true',True),(2,3,'續租',False),(2,4,'取得文章與留言',False),(2,3,'更新文章及日誌',False),(2,3,'續租後補評與向量',False),(2,3,'finally釋放owner租約',False)],[(4,6,'loop','[每個選定看板]',[])])

def umlbox(d,r,title,attrs,ops=(),stereo=''):
    x,y,w,h=r;d.rectangle((x,y,x+w,y+h),fill='white',outline='#334155',width=3)
    txt(d,(x+10,y+10),(stereo+'\n' if stereo else '')+title,31,w-20,True)
    sep=y+(95 if stereo else 60);d.line((x,sep,x+w,sep),fill='#334155',width=2)
    for i,a in enumerate(attrs):txt(d,(x+14,sep+10+i*40),a,27,w-28,False)
    sy=sep+20+len(attrs)*40;d.line((x,sy,x+w,sy),fill='#334155',width=2)
    for i,a in enumerate(ops):txt(d,(x+14,sy+8+i*38),a,26,w-28,False)

im,d=canvas(950)
for r,t,a in [((650,260,510,345),'Article',['+ id: Integer','+ unique_id: String','+ title: String','+ platform_id: Integer']),((30,40,440,230),'Platform',['+ id: Integer','+ name: String']),((1330,40,440,230),'Board',['+ id: Integer','+ platform_id: Integer']),((40,680,470,235),'Comment',['+ id: Integer','+ article_id: Integer']),((1280,680,490,235),'ArticleChunk',['+ article_id: Integer','+ chunk_index: Integer'])]:umlbox(d,r,t,a)
for a,b,la,lb in [((469,190),(650,330),'1','0..*'),((1330,190),(1160,330),'0..1','0..*'),((650,570),(510,730),'1','0..*'),((1160,570),(1280,730),'1','0..*')]:
 d.line((a,b),fill='#334155',width=3)
 dx,dy=b[0]-a[0],b[1]-a[1]
 txt(d,(a[0]+dx*.22-40,a[1]+dy*.22-35),la,27,80)
 txt(d,(a[0]+dx*.78-40,a[1]+dy*.78+10),lb,27,80)
txt(d,(570,805),'屬性節錄；操作區未列業務方法\nORM關聯不是繼承',28,660)
im.save(FIG/'design_classes.png')
im,d=canvas(860)
umlbox(d,(490,30,700,250),'BrowserCrawler',['瀏覽器共用基底'],['共用瀏覽器處理'])
for x,t in [(30,'DcardCrawler'),(610,'Mobile01Crawler'),(1190,'ThreadsCrawler')]:
 umlbox(d,(x,490,550,240),t,['平台解析責任'],['爬取與整理文章'])
 d.line((x+275,490,x+275,390,840,390,840,302),fill='#334155',width=3)
d.polygon([(840,280),(825,305),(855,305)],fill='white',outline='#334155',width=3)
txt(d,(80,770),'PTTCrawler：獨立類別，沒有繼承BrowserCrawler。',32,1640)
im.save(FIG/'crawler_classes.png')

def node(d,x,y,w,h,title,body,kind='node'):
 d.polygon([(x,y),(x+20,y-20),(x+w+20,y-20),(x+w+20,y+h-20),(x+w,y+h),(x+w,y),(x,y)],fill='#E2E8F0',outline='#334155')
 d.rectangle((x,y,x+w,y+h),fill='#F8FAFC',outline='#334155',width=3)
 txt(d,(x+15,y+15),'«'+kind+'»\n'+title,32,w-30)
 d.rectangle((x+20,y+115,x+w-20,y+h-20),fill='white',outline='#64748B',width=2)
 txt(d,(x+35,y+135),body,30,w-70)
im,d=canvas(1100)
node(d,50,50,650,280,'用戶端／瀏覽器','«artifact»\nVue dist')
node(d,1000,50,730,340,'應用主機','«executionEnvironment»\nPython / Uvicorn\n«artifact» FastAPI app')
node(d,1020,710,700,280,'資料主機','«executionEnvironment»\nPostgreSQL')
node(d,50,710,660,280,'外部服務','Gemini API／社群網站')
ua(d,(700,220),(1000,220),'HTTPS／WSS')
ua(d,(1350,390),(1350,710),'SQL')
ua(d,(1040,390),(540,710),'HTTPS')
txt(d,(55,410),'正式環境建議：反向代理與TLS\n開發環境可另啟Vite\n實際位置依部署設定',31,680)
im.save(FIG/'deployment.png')
im,d=canvas(1050)
positions={'views':(30,40),'routers':(1120,40),'services':(1120,390),'models':(1120,750),'core':(560,750),'crawlers':(30,390)}
for name,(x,y) in positions.items():
 d.rectangle((x,y,x+160,y+45),fill='#DBEAFE',outline='#334155',width=2);d.rectangle((x,y+45,x+520,y+230),fill='#F8FAFC',outline='#334155',width=3);txt(d,(x+20,y+92),name,36,480)
for a,b in [('views','routers'),('routers','services'),('services','models'),('services','core'),('crawlers','services')]:
 x,y=positions[a];xx,yy=positions[b]
 if y==yy:ua(d,(x+520,y+140),(xx,yy+140),'«use»',True)
 else:ua(d,(x+260,y+230),(xx+260,yy),'«use»',True)
im.save(FIG/'packages.png')
im,d=canvas(850)
for r,t,a in [((40,50,590,230),'Web UI',['Vue頁面與狀態']),((1090,50,650,230),'API應用',['HTTP路由與服務']),((1090,570,650,230),'資料存取',['SQLAlchemy與PostgreSQL']),((40,570,650,230),'背景處理',['排程、爬蟲、模型呼叫'])]:umlbox(d,r,t,a,stereo='«component»')
ua(d,(630,160),(1090,160),'HTTP／WS')
ua(d,(1400,280),(1400,570),'SQL')
ua(d,(690,685),(1090,685),'持久化介面')
ua(d,(1090,270),(690,580),'工作啟動')
im.save(FIG/'components.png')

def states(name,labels,edges):
 im,d=canvas(1100);coords=[(100,140),(1090,140),(1090,730),(100,730)]
 d.ellipse((320,30,350,60),fill='#111827');ua(d,(335,60),(335,140))
 for (x,y),label in zip(coords,labels):d.rounded_rectangle((x,y,x+610,y+200),30,fill='#EFF6FF',outline='#334155',width=3);txt(d,(x+15,y+70),label,35,580)
 for a,b,label in edges:
  x,y=coords[a];xx,yy=coords[b]
  if y==yy:aa=(x+610 if xx>x else x,y+100);bb=(xx if xx>x else xx+610,yy+100)
  else:aa=(x+305,y+200 if yy>y else y);bb=(xx+305,yy if yy>y else yy+200)
  ua(d,aa,bb,'');mx=(aa[0]+bb[0])/2;my=(aa[1]+bb[1])/2
  txt(d,(mx-250,my-95),label,27,500)
 im.save(FIG/(name+'.png'))
states('lock_state',['無有效租約','本次owner持有','租約已到期','新owner持有'],[(0,1,'acquire [成功] / 設owner'),(1,2,'時間超過expires_at'),(2,3,'acquire [條件更新成功]'),(3,0,'release [owner相符]')])
states('article_state',['尚未入庫','已入庫待分析','分析資料齊備','正文已變更'],[(0,1,'create [通過過濾] / commit'),(1,2,'補評及向量建立成功'),(2,3,'update [正文不同] / 失效'),(3,1,'提交新內容 / 等待補處理')])

# A3 overview: all real foreign keys with explicit relationship IDs.
data=json.loads((WORK/'schema.json').read_text(encoding='utf-8'));by={t['table']:t for t in data}
im=Image.new('RGB',(3300,2050),'white');d=ImageDraw.Draw(im)
txt(d,(30,15),'MeBOD 關聯資料庫總覽',54,3240)
txt(d,(40,88),'18張ORM資料表＋版本表　　實線＝實體FK　　R編號對照外鍵表　　PK主鍵／FK外鍵／UQ唯一鍵',30,3200)
pos={'platforms':(40,200),'boards':(760,200),'articles':(760,780),'authors':(40,780),'comments':(40,1400),'article_chunks':(760,1400),'crawl_logs':(760,1710),'plans':(1670,200),'users':(2390,200),'analysis_history':(1670,780),'usage_counters':(2390,780),'watch_keywords':(1670,1120),'alerts':(2390,1120),'audit_logs':(2390,1450),'analysis_results':(1670,1450),'settings':(40,1710),'system_locks':(1670,1770),'rate_limit_hits':(2390,1770)}
sizes={}; colsmap={}
for name,(x,y) in pos.items():
 cols=[c for c in by[name]['columns'] if c['pk'] or c['fk'] or c['unique']]
 for c in by[name]['columns']:
  if len(cols)>=5:break
  if c not in cols:cols.append(c)
 if name in ['crawl_logs']:cols=[c for c in cols if c['pk'] or c['fk']]
 if name in ['settings','system_locks','rate_limit_hits']:cols=cols[:2]
 colsmap[name]=cols;sizes[name]=(600,60+len(cols)*38+12)
rels=[]
for t in sorted(data,key=lambda z:z['table']):
 for c in t['columns']:
  for fk in c['fk']:rels.append((t['table'],c,fk))
# Routes use numbered labels and orthogonal connectors in reserved gutters.
port_counts={}
for child,c,fk in rels:
 parent=fk['target'].split('.')[0];port_counts[parent]=port_counts.get(parent,0)+1
used_ports={}
for i,(child,c,fk) in enumerate(rels,1):
 parent=fk['target'].split('.')[0];x,y=pos[parent];xx,yy=pos[child];w,h=sizes[parent];ww,hh=sizes[child]
 used_ports[parent]=used_ports.get(parent,0)+1
 py=y+58+used_ports[parent]*(h-65)/(port_counts[parent]+1)
 cy=yy+78+colsmap[child].index(c)*38
 if x!=xx:
  a=(x+w if xx>x else x,py);b=(xx if xx>x else xx+ww,cy);mid=(a[0]+b[0])/2+i*6-42
  pts=[a,(mid,a[1]),(mid,b[1]),b]
 else:
  side=x+w+25+i*8;a=(x+w,py);b=(xx+ww,cy);pts=[a,(side,a[1]),(side,b[1]),b]
 d.line(pts,fill='#64748B',width=3)
 # Labels explicitly supply multiplicity and ID; dictionary provides field endpoints.
 ax,ay=a;bx,byy=b
 # Multiplicities are printed inside the FK row to prevent connector-label collisions.
for name,(x,y) in pos.items():
 w,h=sizes[name];color='#E0F2FE' if name in ['platforms','boards','articles','authors','comments','article_chunks','crawl_logs'] else '#DCFCE7' if name in ['users','plans','analysis_history','usage_counters','watch_keywords','alerts','audit_logs'] else '#F1F5F9'
 d.rectangle((x,y,x+w,y+h),fill='white',outline='#334155',width=2);d.rectangle((x,y,x+w,y+54),fill=color,outline='#334155',width=2);txt(d,(x+12,y+9),name,33,w-24,False)
 for k,c in enumerate(colsmap[name]):
  flags='/'.join(z for z,yes in [('PK',c['pk']),('FK',bool(c['fk'])),('UQ',c['unique'])] if yes)
  rid=next((i for i,(ch,cc,ff) in enumerate(rels,1) if ch==name and cc['name']==c['name']),None)
  suffix=f" [R{rid:02} {'0..1' if c['nullable'] else '1'}]" if rid else ''
  txt(d,(x+12,y+63+k*38),(flags+' '+c['name']+suffix).strip(),28,w-24,False)
d.rectangle((40,1940,1360,2020),fill='#F1F5F9',outline='#334155',width=2);txt(d,(55,1956),'alembic_version　PK version_num　（遷移版本）',30,1280,False)
txt(d,(1490,1980),'完整欄位、NULL與刪除規則見8-1外鍵表及8-2資料字典',28,1750,False)
im.save(FIG/'er_overview.png')
txt=_original_txt
