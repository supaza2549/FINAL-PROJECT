"""ยอดขายตามทรงและรายละเอียดสต็อก ใช้เฉพาะคำสั่งซื้อที่ชำระแล้ว"""
from datetime import date
import db
from support import admin_data

def period_clause(days=None,start=None,end=None):
    if start is not None or end is not None:
        if start is None or end is None or date.fromisoformat(start)>date.fromisoformat(end):raise ValueError('Invalid date range.')
        return "date(o.created_at,'+7 hours') BETWEEN ? AND ?",(start,end)
    if days is not None:return "o.created_at>=datetime('now',?)",(f'-{int(days)} days',)
    return '1=1',()

# J67 | คำนวณยอดขายและสต็อกแยกทรงตามวันที่เลือก

def summary(actor,days=None,start=None,end=None):
    condition,args=period_clause(days,start,end);c=db.conn()
    try:
        admin_data.require_admin(c,actor);c.execute('BEGIN')
        sold={r['fit']:int(r['units']) for r in c.execute(f"SELECT p.fit,SUM(i.quantity) units FROM order_items i JOIN products p ON p.id=i.product_id JOIN orders o ON o.id=i.order_id WHERE o.payment_status='paid' AND o.order_status NOT IN ('refunded','cancelled') AND {condition} GROUP BY p.fit",args)}
        stock={r['fit']:int(r['stock']) for r in c.execute('SELECT p.fit,SUM(v.stock) stock FROM variants v JOIN products p ON p.id=v.product_id WHERE p.active=1 GROUP BY p.fit')}
        fits=set(admin_data.FITS)|set(sold)|set(stock)
        return sorted([dict(fit=fit,units=sold.get(fit,0),stock=stock.get(fit,0)) for fit in fits],key=lambda r:(-r['units'],r['fit']))
    finally:c.close()

# J68 | แดชบอร์ดแถบเปรียบเทียบยอดขายตามทรง

def render(app,parent,rows,days=None,start=None,end=None):
    import tkinter as tk
    box=tk.Frame(parent,bg='white');box.pack(fill='x',pady=(18,12))
    app.label(box,app.ui('ขายดีตามทรงยีนส์ / เตรียมสต็อก','Sales by fit / stock planning'),20,True,fg='#243E55').pack(anchor='w',pady=(0,8))
    app.label(box,app.ui('ยอดขายเป็นจำนวนตัวจากรายการชำระแล้ว ไม่รวมคำสั่งซื้อที่ยกเลิกหรือคืนเงิน','Units from paid orders, excluding cancelled or refunded orders.'),12,fg='#42576A',wraplength=1100,justify='left').pack(anchor='w',pady=(0,10))
    graph=tk.Canvas(box,height=max(140,len(rows)*42+25),bg='#F6F8FA',highlightthickness=0);graph.pack(fill='x',pady=6)
    last_width=[0]
    def draw(event=None):
        width=graph.winfo_width()
        if width<200 or width==last_width[0]:return
        last_width[0]=width;graph.delete('all');peak=max([r['units'] for r in rows]+[1]);x=200 if width>700 else 145;available=max(40,width-x-120)
        for i,r in enumerate(rows):
            y=18+i*42;graph.create_text(16,y+13,text=app.fit_label(r['fit']),anchor='w',fill='#243E55',font=app.font(12,True))
            graph.create_rectangle(x,y,x+available,y+26,fill='#E4E9EE',outline='')
            if r['units']:graph.create_rectangle(x,y,x+available*r['units']/peak,y+26,fill='#243E55' if i==0 else '#70889C',outline='')
            graph.create_text(width-18,y+13,text=f"{r['units']:,} "+app.ui('ตัว','units'),anchor='e',fill='#17212B',font=app.font(13,True))
    graph.bind('<Configure>',draw)
    if not any(r['units'] for r in rows):app.label(box,app.ui('ยังไม่มียอดขายที่ยืนยันชำระในช่วงที่เลือก','No paid sales in the selected period.'),13,True,fg='#42576A').pack(anchor='w',pady=8)
    app._dashboard_ui['fit_sales']=dict(rows=rows,graph=graph)
