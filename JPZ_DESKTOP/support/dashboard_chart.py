"""Lightweight native chart; all buckets retain the selected period's totals."""
from datetime import date, timedelta
import math
import tkinter as tk
from support.theme import card, DENIM


def buckets(rows, start=None, end=None, days=None):
    from support.loyalty import thai_day
    today = date.fromisoformat(thai_day())
    parsed = [(date.fromisoformat(r['day']), r) for r in rows if r['day']]
    first = date.fromisoformat(start) if start else today-timedelta(days=days) if days else min((d for d, _ in parsed), default=today)
    last = date.fromisoformat(end) if end else max(today, max((d for d, _ in parsed), default=today))
    span = max(1, (last-first).days+1)
    width = max(1, math.ceil(span/14))
    result = []
    for offset in range(0, span, width):
        lo = first+timedelta(days=offset); hi = min(last, lo+timedelta(days=width-1))
        result.append(dict(start=lo, end=hi, revenue=0.0, orders=0))
    for day, row in parsed:
        if first <= day <= last:
            target = result[min(len(result)-1, (day-first).days//width)]
            target['revenue'] += float(row['revenue'] or 0)
            target['orders'] += int(row['orders'])
    return result


def create(app, parent, stats, start=None, end=None, days=None):
    panel = card(parent); panel.pack(fill='x', pady=(8,14))
    header = tk.Frame(panel, bg='white'); header.pack(fill='x', padx=18, pady=(14,6))
    app.label(header, app.ui('แนวโน้มร้าน','Store trends'), 15, True).pack(side='left')
    mode = {'key':'revenue'}; buttons=[]
    canvas = tk.Canvas(panel, bg='white', height=240, highlightthickness=0)
    points = buckets(stats['daily'], start, end, days)
    detail = app.label(panel, '', 10, fg='#5D6975', wraplength=850)
    def hint(point=None):
        if point:
            interval = point['start'].strftime('%d/%m/%Y')
            if point['start'] != point['end']: interval += ' – '+point['end'].strftime('%d/%m/%Y')
            detail.configure(text=f"{interval} · "+app.ui('ยอดขาย','Sales')+f" ฿{point['revenue']:,.2f} · "+app.ui('คำสั่งซื้อ','Orders')+f" {point['orders']:,}")
        else:
            detail.configure(text=app.ui('ยอดขายเฉพาะที่ชำระแล้ว · คำสั่งซื้อรวมทุกสถานะ · ชี้แท่งกราฟเพื่อดูรายละเอียด','Sales include paid orders; order counts include all statuses. Hover over a bar for details.'))
    def draw(event=None):
        canvas.delete('all'); w=max(280,canvas.winfo_width()); left=72; right=w-18; top=20; bottom=193
        key=mode['key']; peak=max((p[key] for p in points),default=0)
        ceiling=max(4,math.ceil(peak*1.15/4)*4)
        for n in range(5):
            y=bottom-(bottom-top)*n/4; value=ceiling*n/4
            canvas.create_line(left,y,right,y,fill='#E9EEF3')
            label=f'{value/1000000:.1f}M' if value>=1000000 else f'{value/1000:.1f}k' if value>=1000 else f'{value:.0f}'
            canvas.create_text(left-10,y,text=label,anchor='e',fill='#5D6975',font=app.font(9))
        stride=(right-left)/len(points)
        for i,p in sorted(enumerate(points),key=lambda pair:pair[1][key]):
            x=left+stride*(i+.5); y=bottom-(bottom-top)*p[key]/ceiling
            tag=f'bar{i}'; bw=max(3,stride*.62)
            y=y if p[key] else bottom-2
            canvas.create_line(x,y,x,bottom,fill=DENIM if key=='revenue' else '#2A8C82',width=bw,tags=tag,capstyle='butt')
            canvas.tag_bind(tag,'<Enter>',lambda e,point=p:hint(point))
            canvas.tag_bind(tag,'<Leave>',lambda e:hint())
            if i%max(1,math.ceil(len(points)/(6 if w<650 else 14)))==0:
                canvas.create_text(x,bottom+18,text=p['start'].strftime('%d/%m'),fill='#5D6975',font=app.font(9))
        canvas.create_text(left,4,text=app.ui('บาท','THB') if key=='revenue' else app.ui('คำสั่งซื้อ','Orders'),anchor='nw',fill='#5D6975',font=app.font(9))
        if not peak:canvas.create_text((left+right)/2,85,text=app.ui('ยังไม่มีข้อมูลในช่วงที่เลือก','No data in the selected period'),fill='#5D6975',font=app.font(12,True))
        for k,button in buttons:button.configure(fg_color=DENIM if key==k else '#F1F3F5',text_color='white' if key==k else DENIM)
    def switch(key):mode['key']=key;hint();draw()
    for key,th,en in [('orders','คำสั่งซื้อ','Orders'),('revenue','ยอดขาย','Sales')]:
        button=app.button(header,app.ui(th,en),lambda k=key:switch(k),compact=True);button.pack(side='right',padx=3);buttons.append((key,button))
    canvas.pack(fill='x',padx=12);detail.pack(anchor='w',padx=18,pady=(0,12))
    panel.bind('<Configure>',lambda e:detail.configure(wraplength=max(200,e.width-40)))
    canvas.bind('<Configure>',draw);hint()
    return dict(canvas=canvas,points=points,switch=switch,detail=detail,mode=mode)
