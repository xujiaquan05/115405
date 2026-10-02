"""Draw physical ER diagrams from the extracted project ORM metadata."""
schema_data=json.loads((WORK/'schema.json').read_text(encoding='utf-8'))
by_name={t['table']:t for t in schema_data}

def entity(d,name,x,y,w=490):
    cols=[c for c in by_name[name]['columns'] if c['pk'] or c['fk'] or c['unique']]
    if not cols:cols=by_name[name]['columns'][:2]
    h=75+len(cols)*46
    d.rectangle((x,y,x+w,y+h),fill='white',outline='#315C80',width=3)
    d.rectangle((x,y,x+w,y+62),fill='#EAF2F8',outline='#315C80',width=3)
    pictogram(d,x+10,y+3,'database')
    txt(d,(x+80,y+16),name,32,w-95,False)
    for i,c in enumerate(cols):
        keys='/'.join(k for k,yes in [('PK',c['pk']),('FK',bool(c['fk'])),('UQ',c['unique'])] if yes)
        text=(keys+'  '+c['name']).strip()
        txt(d,(x+15,y+76+i*46),text,28,w-25,False)
    return (x,y,w,h)

def er_line(d,points,nullable=False):
    d.line(points,fill='#315C80',width=3)
    # First endpoint is the referenced parent: one, or zero-or-one for nullable FK.
    def mark(p,q,many=False,optional=False):
        dx,dy=q[0]-p[0],q[1]-p[1];mag=math.hypot(dx,dy);ux,uy=dx/mag,dy/mag
        def pos(a,b):return (p[0]+ux*a-uy*b,p[1]+uy*a+ux*b)
        if many:
            for b in [-13,0,13]:d.line((pos(0,b),pos(25,0)),fill='#315C80',width=3)
        else:d.line((pos(13,-13),pos(13,13)),fill='#315C80',width=3)
        if optional:
            cx,cy=pos(40,0);d.ellipse((cx-8,cy-8,cx+8,cy+8),fill='white',outline='#315C80',width=3)
        else:d.line((pos(31,-13),pos(31,13)),fill='#315C80',width=3)
    mark(points[0],points[1],optional=nullable)
    mark(points[-1],points[-2],many=True,optional=True)

def er_diagram(name,positions,edges,h,subtitle):
    im,d=canvas(h)
    for points,nullable in edges:er_line(d,points,nullable)
    for table_name,xy in positions.items():entity(d,table_name,*xy)
    txt(d,(900,h-110),subtitle,29,1720)
    txt(d,(900,h-65),'PK 主鍵   FK 外鍵   UQ 唯一鍵   ○ 可無   | 一筆   分叉 多筆',28,1720)
    im.save(FIG/(name+'.png'))

# Separate physical tables; no combined entities and no invented FK links.
er_diagram('er_content',{
    'platforms':(40,30),'boards':(655,30),'authors':(1270,30),
    'articles':(655,465),'comments':(40,1020),'article_chunks':(1270,1020)},[
    ([(530,135),(655,135)],False),
    ([(285,197),(285,380),(730,380),(730,465)],False),
    ([(900,197),(900,465)],True),
    ([(1515,197),(1515,380),(1080,380),(1080,465)],True),
    ([(655,710),(285,710),(285,1020)],False),
    ([(1145,710),(1515,710),(1515,1020)],False),
],1340,'內容領域實體關聯圖  僅顯示識別鍵與關聯欄位；完整型別見資料字典')

er_diagram('er_users',{
    'plans':(40,30),'users':(655,30),'audit_logs':(1270,30),
    'analysis_history':(40,540),'usage_counters':(1270,540),
    'watch_keywords':(40,1000),'alerts':(1270,1000)},[
    ([(530,130),(655,130)],False),
    ([(1145,130),(1270,130)],True),
    ([(730,243),(730,430),(285,430),(285,540)],False),
    ([(1080,243),(1080,430),(1515,430),(1515,540)],False),
    ([(850,243),(850,880),(285,880),(285,1000)],True),
    ([(970,243),(970,880),(1515,880),(1515,1000)],True),
],1320,'帳號領域實體關聯圖  關聯端點是否可空依實際 FK 欄位定義')

er_diagram('er_ops',{
    'platforms':(40,30),'boards':(1270,30),'crawl_logs':(655,440),
    'analysis_results':(40,870),'settings':(1270,870),
    'system_locks':(40,1180),'rate_limit_hits':(1270,1180)},[
    ([(285,197),(285,330),(760,330),(760,440)],True),
    ([(1515,197),(1515,330),(1040,330),(1040,440)],True),
],1560,'維運與共用資料  platforms 與 boards 為前圖參照；下方四表無宣告 FK')
