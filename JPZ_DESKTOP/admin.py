from support.theme import check_field
from support.theme import select_field
# หน้าจัดการร้านสำหรับบัญชีที่มีสิทธิ์แอดมินเท่านั้น
# จัดการสินค้า สต็อกแยกสี/ไซซ์ ลูกค้า คำสั่งซื้อ ส่วนลด QR และช่องทางติดต่อ
# ไม่มีเมนูสำรองข้อมูลหรือเครื่องมือฐานข้อมูลในหน้าจอแอดมิน

"""Python/Tkinter back office with searchable tables and guarded operations."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import sqlite3
import os
from pathlib import Path
from support import admin_data as data
import db
from support import loyalty
from support import catalogue
import receipt as receipts
from support.theme import ctk,card,field,DENIM,BORDER
from support.tables import AdminTable

class AdminMixin:
    # เลือกข้อความภาษาไทยหรืออังกฤษตามภาษาที่ผู้ใช้เลือก
    def ui(self,th,en): return th if self.lang=='TH' else en

    # เปิดหน้าจัดการร้านสำหรับบัญชีแอดมิน
    def admin(self,push=True):
        self.navigate('admin',self._admin,push=push)

    # เปิดหน้าจัดการสินค้าและสต็อก
    def admin_stock(self,push=True):
        self.navigate('admin_stock',self._admin_stock,push=push)


    # ใช้หน้าสินค้าและสต็อกร่วมกัน
    def _admin_stock(self):
        return self._admin('products')

    # ตรวจสิทธิ์แอดมินและสร้างเมนูจัดการร้าน
    # J38 | เมนูแอดมิน
    def admin_shell(self):
        if not self.user or self.user.get('role')!='admin':
            raise PermissionError('Administrator access required.')
        # ตรวจสิทธิ์ผู้ดูแลทั้งในฐานข้อมูลและบัญชีที่เข้าสู่ระบบ
        data.query(self.user['id'],'SELECT 1')
        self._admin_screen_active=True
        self.clear()
        top=ctk.CTkFrame(self,fg_color=DENIM,corner_radius=0,height=72)
        top.pack(fill='x'); top.pack_propagate(False)
        self.label(top,'JPZ. / STORE ADMIN',13,True,fg='white').pack(side='left',padx=25,pady=18)
        language_box=tk.Frame(top,bg='white')
        language_box.pack(side='right',padx=12,pady=12)
        self.lang_switch(language_box)
        self.button(top,self.tr('logout'),self.logout,dark=True).pack(side='right',padx=10)
        body=tk.Frame(self,bg='white'); body.pack(fill='both',expand=True)
        side=ctk.CTkFrame(body,fg_color='#F1F3F5',corner_radius=0,width=230); side.pack(side='left',fill='y'); side.pack_propagate(False)
        tabs=[('dashboard','ภาพรวม','Overview'),('orders','คำสั่งซื้อ','Orders'),('products','สินค้าและสต็อก','Products / inventory'),('customers','บัญชีผู้ใช้','User accounts'),('rewards','ส่วนลดรายวัน','Daily discounts'),('payment','รับชำระ / QR','Payment / QR'),('contact','ช่องทางติดต่อ','Contact')]
        self.label(side,self.ui('จัดการร้าน','STORE'),11,True,fg='#555555').pack(anchor='w',padx=16,pady=15)
        for key,th,en in tabs:
            self.button(side,self.ui(th,en),lambda x=key:self.open_admin_tab(x),dark=getattr(self,'admin_tab','dashboard')==key,compact=True).pack(fill='x',padx=8,pady=5)
        self.button(side,self.tr('admin_account'),self.admin_profile,dark=getattr(self,'admin_tab','')=='account',compact=True).pack(fill='x',padx=8,pady=10)
        self.button(side,self.ui('ดูหน้าร้าน','View storefront'),lambda:self.home(push=False),compact=True).pack(fill='x',padx=8,pady=10)
        content=tk.Frame(body,bg='white'); content.pack(side='left',fill='both',expand=True,padx=28,pady=22)
        style=ttk.Style(self)
        style.theme_use('clam')
        style.configure('JPZ.Treeview',font=self.font(11),rowheight=48,background='white',fieldbackground='white',foreground='#111111')
        style.configure('JPZ.Treeview.Heading',font=self.font(11,True),background='#F1F3F5',foreground='#243E55',padding=(12,14),relief='flat')
        style.map('JPZ.Treeview',background=[('selected',DENIM)],foreground=[('selected','white')])
        style.configure('TNotebook',background='white',borderwidth=0)
        style.configure('TNotebook.Tab',font=self.font(11,True),padding=(18,10),background='#E9EEF3')
        style.map('TNotebook.Tab',background=[('selected',DENIM)],foreground=[('selected','white')])
        style.configure('TCombobox',padding=7,font=self.font(11))
        return content

    # เลือกเมนูแอดมินและทำเครื่องหมายเมนูที่กำลังใช้งาน
    def open_admin_tab(self,tab):
        self.admin_tab=tab
        self.navigate('admin',self._admin,tab,push=False)

    # เลือกฟังก์ชันแสดงเนื้อหาตามเมนูแอดมิน
    def _admin(self,tab=None):
        selected=tab or getattr(self,'admin_tab','dashboard')
        self.admin_tab={'stock':'products','categories':'products','data':'products','audit':'dashboard'}.get(selected,selected)
        b=self.admin_shell()
        handlers={'dashboard':self.admin_dashboard,'orders':self.admin_orders,'products':self.admin_products,
                  'customers':self.admin_customers,'rewards':self.admin_rewards,
                  'payment':self.admin_payment,'contact':self.admin_contact}
        handlers[self.admin_tab](b)

    # สร้างหัวข้อหน้าจัดการร้านตามภาษาที่เลือก
    def heading(self,parent,th,en,sub_th='',sub_en=''):
        self.label(parent,self.ui(th,en),24,True,fg=DENIM).pack(anchor='w')
        if sub_th: self.label(parent,self.ui(sub_th,sub_en),12,fg='#777777',wraplength=950,justify='left').pack(anchor='w',pady=(8,18))

    # สร้างตารางแอดมินพร้อมหัวตารางและแถบเลื่อน
    def table(self,parent,columns,height=12,compact=False):
        frame=tk.Frame(parent,bg='white'); frame.pack(fill='both',expand=True,pady=0 if compact else 8)
        tree=AdminTable(frame,columns=[k for k,label,width in columns],show='headings',height=height,style='JPZ.Treeview')
        sy=ttk.Scrollbar(frame,orient='vertical',command=tree.yview)
        sx=ttk.Scrollbar(frame,orient='horizontal',command=tree.xview)
        tree.configure(yscrollcommand=lambda *a:tree.scrolled(sy.set,*a),xscrollcommand=lambda *a:tree.scrolled(sx.set,*a))
        tree.grid(row=0,column=0,sticky='nsew');sy.grid(row=0,column=1,sticky='ns');sx.grid(row=1,column=0,sticky='ew')
        frame.rowconfigure(0,weight=1);frame.columnconfigure(0,weight=1)
        import tkinter.font as tkfont
        heading_font=tkfont.Font(self,font=self.font(11,True))
        for key,label,width in columns:
            tree.heading(key,text=label,anchor='center',command=lambda k=key:self.sort_table(tree,k))
            minimum=max(90,heading_font.measure(label)+28)
            tree.column(key,width=max(width,minimum),minwidth=minimum,stretch=True,anchor='e' if key in ('total','before_vat','before','revenue','price','qty','stock','units','count','orders') else 'w')
        return tree

    # เรียงข้อมูลในตารางตามคอลัมน์ที่กด
    def sort_table(self,tree,key):
        descending=getattr(tree,'_sort',None)==(key,False)
        def sortval(i):
            value=tree.set(i,key)
            try:return (0,float(value.replace(',','')))
            except ValueError:return (1,value.casefold())
        for pos,i in enumerate(sorted(tree.get_children(),key=sortval,reverse=descending)): tree.move(i,'',pos)
        tree._sort=(key,descending)
        tree.restripe()

    # สร้างช่องค้นหาและเรียกการกรองเมื่อข้อความเปลี่ยน
    def search_bar(self,b,refresh,export=None):
        bar=tk.Frame(b,bg='white');bar.pack(fill='x',pady=5)
        self.label(bar,self.ui('ค้นหา','Search'),9,True).pack(side='left',padx=(0,8))
        term=tk.StringVar()
        search=field(bar);search.configure(textvariable=term,width=300);search.pack(side='left')
        term.trace_add('write',lambda *args:refresh(term.get()))

        return bar,term


    # แสดงสรุปข้อมูลร้าน ยอดขาย และคำสั่งซื้อ
    # J39 | ภาพรวมแอดมินและรายงาน
    def admin_dashboard(self,b):
        b=self.scroll_content(b)
        self.heading(b,'ภาพรวมร้าน','Store overview','ยอดขายจากคำสั่งซื้อที่ยืนยันชำระเงินแล้ว ไม่รวมคำสั่งซื้อที่คืนเงิน','Sales count approved payments and exclude refunded orders.')
        bar=tk.Frame(b,bg='white');bar.pack(fill='x')
        period=getattr(self,'admin_period',None)
        for days,th,en in [(None,'ทั้งหมด','All time'),(7,'7 วัน','7 days'),(30,'30 วัน','30 days'),(90,'90 วัน','90 days')]:
            def choose(x=days):self.admin_period=x;self.admin_calendar=None;self._admin('dashboard')
            self.button(bar,self.ui(th,en),choose,dark=period==days and not getattr(self,'admin_calendar',None),compact=True).pack(side='left',padx=(0,6))
        from datetime import date
        import calendar
        chosen=getattr(self,'admin_calendar',None)
        dates=tk.Frame(b,bg='white');dates.pack(fill='x',pady=10)
        today=date.fromisoformat(loyalty.thai_day());all_text=self.ui('ทั้งหมด','All')
        year=tk.StringVar(value=str(chosen[0]) if chosen else all_text)
        month=tk.StringVar(value=f'{chosen[1]:02d}' if chosen and chosen[1] else all_text)
        day=tk.StringVar(value=f'{chosen[2]:02d}' if chosen and chosen[2] else all_text)
        recorded_years=data.query(self.user['id'],"SELECT DISTINCT CAST(strftime('%Y',created_at,'+7 hours') AS INTEGER) year FROM orders WHERE created_at IS NOT NULL")
        years=sorted(set(range(max(1,today.year-5),min(9999,today.year+10)+1))|{r['year'] for r in recorded_years if r['year']}|({chosen[0]} if chosen else set()))
        pickers=[];date_holders=[]
        for caption,variable,options in [(self.ui('ปี','Year'),year,[all_text]+[str(y) for y in years]),(self.ui('เดือน','Month'),month,[all_text]+[f'{m:02d}' for m in range(1,13)]),(self.ui('วัน','Day'),day,[all_text]+[f'{d:02d}' for d in range(1,32)])]:
            holder=tk.Frame(dates,bg='white');date_holders.append(holder)
            self.label(holder,caption,11,True).pack(side='left',padx=(0,8))
            picker=select_field(holder,textvariable=variable,values=options,state='normal' if variable is year else 'readonly',width=16);picker.pack(side='left',fill='x',expand=True);pickers.append(picker)
        error=self.label(b,'',11,fg='#BB2020');error.pack(anchor='w')
        def select_date():
            try:
                raw=year.get().strip()
                if raw==all_text:
                    if month.get()!=all_text or day.get()!=all_text:raise ValueError(self.ui('เลือกปีก่อนเลือกเดือนหรือวัน','Choose a year before choosing a month or day.'))
                    self.admin_calendar=None;self.admin_period=None;self._admin('dashboard');return
                if not raw.isascii() or not raw.isdigit() or not 1<=int(raw)<=9999:raise ValueError(self.ui('กรอกปี ค.ศ. ตั้งแต่ 1 ถึง 9999 เช่น 2027','Enter a year from 1 to 9999, e.g. 2027.'))
                y=int(raw);m=int(month.get()) if month.get()!=all_text else None;d=int(day.get()) if day.get()!=all_text else None
                if d and not m:raise ValueError(self.ui('เลือกเดือนก่อนเลือกวัน','Choose a month before choosing a day.'))
                if d:date(y,m,d)
                self.admin_calendar=(y,m,d);self.admin_period=None;self._admin('dashboard')
            except ValueError as exc:error.configure(text=str(exc))
        apply_holder=tk.Frame(dates,bg='white');date_holders.append(apply_holder)
        self.button(apply_holder,self.ui('ดูข้อมูล','Apply date'),select_date,compact=True).pack(anchor='w')
        def arrange_dates(event):
            columns=4 if event.width>=980 else 2 if event.width>=520 else 1
            for col in range(4):dates.columnconfigure(col,weight=int(col<columns))
            for index,holder in enumerate(date_holders):holder.grid(row=index//columns,column=index%columns,sticky='ew',padx=(0,16),pady=4)
        dates.bind('<Configure>',arrange_dates)
        start=end=None
        if chosen:
            y,m,d=chosen
            if d:start=end=date(y,m,d).isoformat()
            elif m:start=date(y,m,1).isoformat();end=date(y,m,calendar.monthrange(y,m)[1]).isoformat()
            else:start=date(y,1,1).isoformat();end=date(y,12,31).isoformat()
        stats=data.dashboard(self.user['id'],period,start,end,include_activity=False)
        from support import fit_sales
        fit_rows=fit_sales.summary(self.user['id'],period,start,end)
        self._dashboard_ui=dict(year=year,month=month,day=day,apply=select_date,stats=stats,error=error,pickers=pickers,dates=dates)

        range_text=(start if start==end else start+' ถึง '+end) if start else self.ui(f'ย้อนหลัง {period} วัน',f'Last {period} days') if period else self.ui('ทั้งหมด','All time')
        self.label(b,self.ui('ข้อมูลช่วง: ','Selected period: ')+range_text+self.ui(' · วันที่คำสั่งซื้อ เวลาไทย',' · order date, Thai time'),13,True,fg='#243E55').pack(anchor='w',pady=(4,8))

        metrics=[('ยอดขายสุทธิ','Net sales',f"฿{stats['revenue']:,.2f}"),('คำสั่งซื้อ','Orders',stats['orders']),
                 ('รอตรวจชำระเงิน','Payment review',stats['review']),('รอจัดส่ง','Preparing',stats['preparing']),
                 ('ลูกค้าทั้งหมด','Total customers',stats['customers']),('สต็อกทั้งหมด','Total units',stats['stock']),
                 ('ยอดบันทึกคืนเงิน','Refund records',f"฿{stats['refunds']:,.2f}")]
        cards=tk.Frame(b,bg='white');cards.pack(fill='x',pady=14)
        metric_cards=[]
        for i,(th,en,value) in enumerate(metrics):
            color=DENIM if i==0 else '#F1F3F5'
            metric=ctk.CTkFrame(cards,fg_color=color,corner_radius=14,border_width=1,border_color=BORDER)
            metric_cards.append(metric)
            caption=self.label(metric,self.ui(th,en),10,fg='#DAE5ED' if i==0 else '#5D6975',wraplength=190,justify='left');caption.pack(anchor='w',padx=16,pady=(14,4))
            self.label(metric,f'{value:,}' if isinstance(value,int) else str(value),23,True,fg='white' if i==0 else DENIM).pack(anchor='w',padx=16,pady=(0,14))
            metric.bind('<Configure>',lambda event,label=caption:label.configure(wraplength=max(90,event.width-32)))
        def arrange_metrics(event):
            count=4 if event.width>=1000 else 3 if event.width>=760 else 2 if event.width>=460 else 1
            for col in range(4):cards.columnconfigure(col,weight=int(col<count),uniform='metrics' if col<count else '')
            for i,metric in enumerate(metric_cards):metric.grid(row=i//count,column=i%count,sticky='nsew',padx=4,pady=4)
        cards.bind('<Configure>',arrange_metrics)
        self._dashboard_ui.update(cards=metric_cards,content=b)
        self.label(b,self.ui('ช่วงเวลาที่เลือกใช้กับยอดขายและคำสั่งซื้อ ส่วนลูกค้าและสต็อกแสดงจำนวนปัจจุบัน','The selected period applies to sales and orders. Customers and stock show current totals.'),11,fg='#5D6975',wraplength=1000,justify='left').pack(anchor='w',pady=(2,5))
        fit_sales.render(self,b,fit_rows,period,start,end)
        report_header=tk.Frame(b,bg='white');report_header.pack(fill='x',pady=(8,6))
        report_style=ttk.Style(self);report_style.layout('JPZ.Reports.TNotebook.Tab',[])
        notebook=ttk.Notebook(b,style='JPZ.Reports.TNotebook',height=330);notebook.pack(fill='x',pady=(0,18))
        report_tables=[]
        daily=tk.Frame(notebook,bg='white');top=tk.Frame(notebook,bg='white')
        notebook.add(daily,text=self.ui('ยอดรายวัน (เวลาไทย)','Daily sales (Thai time)'))
        notebook.add(top,text=self.ui('สินค้าขายดี','Top products'))
        t=self.table(daily,[('day',self.ui('วันที่','Date'),160),('orders',self.ui('คำสั่งซื้อ','Orders'),120),('revenue',self.ui('ยอดขายสุทธิ','Net sales'),180),('before',self.ui('ก่อน VAT','Before VAT'),160)],6,compact=True);report_tables.append(t)
        for r in stats['daily']:t.insert('','end',values=(r['day'],r['orders'],f"{r['revenue']:,.2f}",f"{db.vat_breakdown(r['revenue'])['before_vat']:,.2f}"))
        if not stats['daily']:t.insert('','end',values=(self.ui('ยังไม่มีคำสั่งซื้อ','No orders yet'),'—','0.00','0.00'))
        t=self.table(top,[('name',self.ui('สินค้า','Product'),260),('units',self.ui('จำนวน','Units'),90),('revenue',self.ui('ยอดสุทธิแบ่งส่วนลด','Net sales with allocated discount'),220),('before',self.ui('ก่อน VAT','Before VAT'),160)],6,compact=True);report_tables.append(t)
        for r in stats['top']:t.insert('','end',values=(r['name'],r['units'],f"{r['revenue']:,.2f}",f"{db.vat_breakdown(r['revenue'])['before_vat']:,.2f}"))
        for kind,table in zip(('daily','top'),report_tables):
            table._report_kind=kind;table._report_context=dict(start=start,end=end,days=period)
        report_buttons=[]
        for index,(th,en) in enumerate([('ยอดรายวัน','Daily sales'),('สินค้าขายดี','Top products')]):
            report_buttons.append(self.button(report_header,self.ui(th,en),lambda i=index:notebook.select(i),dark=index==0,compact=True))
        def arrange_reports(event=None):
            selected=notebook.index(notebook.select())
            columns=2 if report_header.winfo_width()>=520 else 1
            for col in range(2):report_header.columnconfigure(col,weight=int(col<columns))
            for index,button in enumerate(report_buttons):
                button.configure(fg_color=DENIM if index==selected else '#F1F3F5',text_color='white' if index==selected else '#243E55')
                button.grid(row=index//columns,column=index%columns,sticky='ew',padx=(0,6),pady=3)
        report_header.bind('<Configure>',arrange_reports);notebook.bind('<<NotebookTabChanged>>',arrange_reports)
        self._dashboard_ui.update(report_tables=report_tables,report_buttons=report_buttons,report_header=report_header,notebook=notebook)

    # แสดงคำสั่งซื้อทั้งหมดสำหรับตรวจการชำระและจัดส่ง
    # J40 | จัดการคำสั่งซื้อ
    def admin_orders(self,b):
        self.heading(b,'จัดการคำสั่งซื้อ','Order management','ค้นหาชื่อลูกค้า วันที่ หรือหมายเลขคำสั่งซื้อ เก็บประวัติทุกสถานะ','Search customer, date or order number. All order history is retained.')
        filters=tk.Frame(b,bg='white');filters.pack(fill='x',pady=8)
        variables={};tree=None;rows=[]
        for index,(key,th,en) in enumerate([('name','ชื่อลูกค้า','Customer name'),('date','วันที่ DD/MM/YYYY หรือ YYYY-MM-DD','Date DD/MM/YYYY or YYYY-MM-DD'),('number','หมายเลขคำสั่งซื้อ (ค้นหาบางส่วนได้)','Order number (partial accepted)')]):
            box=tk.Frame(filters,bg='white');box.grid(row=0,column=index,sticky='ew',padx=6);filters.columnconfigure(index,weight=1)
            entry=self.entry(box,self.ui(th,en));variable=tk.StringVar();entry.configure(textvariable=variable);variables[key]=variable
        tree=self.table(b,[('sequence',self.ui('ออเดอร์ที่','Order sequence'),90),('id',self.ui('หมายเลขคำสั่งซื้อ','Order number'),255),('date',self.ui('วันที่ (เวลาไทย)','Date (Thailand)'),145),('name',self.ui('ลูกค้า','Customer'),160),('total',self.ui('ยอดสุทธิ','Net total'),110),('before_vat',self.ui('ก่อน VAT','Before VAT'),110),('payment',self.ui('ชำระเงิน','Payment'),140),('status',self.ui('สถานะ','Status'),130),('tracking',self.ui('เลขพัสดุ','Tracking'),140)])
        tree._report_kind='orders'
        search_notice=self.label(b,'',11,fg='#5D6975');search_notice.pack(anchor='w',pady=6)
        def refresh(*args):
            nonlocal rows
            rows=db.orders();position=tree.yview()[0];tree.delete(*tree.get_children())
            name=variables['name'].get().strip().casefold();day=variables['date'].get().strip();number=variables['number'].get().strip().casefold()
            for r in rows:
                if name and name not in r['customer_name'].casefold():continue
                if number and ''.join(number.split()) not in db.order_number(r).casefold():continue
                from support import order_search
                if not order_search.date_matches(day,r['created_at']):continue
                tree.insert('','end',iid=str(r['id']),values=(r['order_sequence'],db.order_number(r),receipts.local_time(r['created_at']),r['customer_name'],f"{r['total']:,.2f}",f"{db.vat_breakdown(r['total'])['before_vat']:,.2f}",self.status_label(r['payment_status']),self.status_label(r['order_status']),r['tracking']))
                palette={'paid':('#256A43','#E6F2EB'),'completed':('#256A43','#E6F2EB'),'under_review':('#875B16','#FFF0D9'),'waiting_payment':('#875B16','#FFF0D9'),'preparing':('#275778','#E8F0F7'),'shipped':('#62478D','#EFE9F7'),'refunded':('#62478D','#EFE9F7'),'cancelled':('#A02A36','#F9E7EA'),'rejected':('#A02A36','#F9E7EA')}
                neutral=('#5D6975','#EDF0F3')
                tree.set_status_colors(str(r['id']),{'payment':palette.get(r['payment_status'],neutral),'status':palette.get(r['order_status'],neutral)})
            tree.yview_moveto(position)
            count=len(tree.get_children());search_notice.configure(text=self.ui(f'พบ {count} คำสั่งซื้อ',f'{count} orders found') if count else self.ui('ไม่พบคำสั่งซื้อที่ตรงกับตัวกรอง ล้างตัวกรองเพื่อดูทั้งหมด','No orders match the filters. Clear filters to view all orders.'))
        for variable in variables.values():variable.trace_add('write',refresh)
        def open_selected():
            if tree.selection():self.order_dialog(next(r for r in rows if str(r['id'])==tree.selection()[0]))
        actions=tk.Frame(b,bg='white');actions.pack(fill='x')
        def clear():
            for variable in variables.values():variable.set('')
        self.button(actions,self.ui('ล้างตัวกรอง','Clear filters'),clear,compact=True).pack(side='left')
        self.button(actions,self.ui('รีเฟรช','Refresh'),refresh,compact=True).pack(side='left',padx=8)
        tree.bind('<Double-1>',lambda e:open_selected());self.button(actions,self.ui('เปิดรายละเอียด','Open details'),open_selected,dark=True).pack(side='right')
        self._orders_search_ui=dict(variables=variables,tree=tree,refresh=refresh)
        refresh()

    # เปิดรายละเอียดคำสั่งซื้อเพื่อยืนยันชำระ ยกเลิก หรือปรับการจัดส่ง
    # J63 | รายละเอียดคำสั่งซื้อฝั่งแอดมิน
    def order_dialog(self,o):
        win=tk.Toplevel(self);win.title(self.ui('หมายเลขคำสั่งซื้อ','Order number')+f" {db.order_number(o)}");win.configure(bg='white');win.attributes('-fullscreen',True)
        win.bind('<MouseWheel>',lambda event:(self.scroll_wheel(event),'break')[1])
        footer=tk.Frame(win,bg='white');footer.pack(side='bottom',fill='x',padx=24,pady=12)
        self.button(footer,self.ui('ปิดรายละเอียด','Close details'),win.destroy,dark=True).pack(side='right')
        win.bind('<Escape>',lambda event:(win.destroy(),'break')[1]);self._admin_order_window=win
        scroll_body=self.scroll_content(win)
        content=tk.Frame(scroll_body,bg='white');content.pack(fill='x',padx=24,pady=18)
        summary=card(content);summary.pack(fill='x',pady=(0,16))
        inner=tk.Frame(summary,bg='white');inner.pack(fill='x',padx=20,pady=18)
        self.label(inner,self.ui('รายละเอียดคำสั่งซื้อ','Order details'),11,True,fg='#5D6975').pack(anchor='w')
        number=self.label(inner,db.order_number(o),20,True,fg=DENIM,wraplength=850);number.pack(anchor='w',pady=(6,12))
        receiver=self.label(inner,f"{o['customer_name']} · {o['phone']}\n{o['address']} {o.get('postal_code','')}",11,wraplength=850,justify='left');receiver.pack(anchor='w',pady=(0,8))
        self.order_badges(inner,o).pack(anchor='w',pady=5)
        self.label(inner,self.ui('ยอดสุทธิ','Net total')+f"  ฿{o['total']:,.2f}",22,True,fg=DENIM).pack(anchor='w',pady=(8,0))
        self.label(inner,self.ui('ออเดอร์ที่','Order sequence')+f" {o['order_sequence']}",10,fg='#5D6975').pack(anchor='w',pady=(6,0))
        inner.bind('<Configure>',lambda event:[label.configure(wraplength=max(200,event.width-8)) for label in (number,receiver)])
        items=data.order_items(self.user['id'],o['id'])
        t=self.table(content,[('name',self.ui('สินค้า','Product'),240),('color',self.tr('color'),130),('size',self.tr('size'),70),('qty',self.tr('quantity'),80),('price',self.ui('ราคา/ชิ้น','Unit price'),110),('before_vat',self.ui('ก่อน VAT/ชิ้น','Before VAT / unit'),120)],4)
        t._report_kind='order_items';t._report_context=dict(order_id=o['id'])
        for r in items:t.insert('','end',values=(r['name'],self.color_label(r['color']),db.size_label(r['size']),r['quantity'],f"{r['price']:,.2f}",f"{db.vat_breakdown(r['price'])['before_vat']:,.2f}"))
        self.price_before_vat(content,o['total'])
        self.label(content,self.ui(f"สินค้า ฿{o['subtotal']:,.2f}  •  ส่วนลด ฿{o['discount_amount']:,.2f}  •  ยอดสุทธิ ฿{o['total']:,.2f}",
                                   f"Subtotal ฿{o['subtotal']:,.2f} • Discount ฿{o['discount_amount']:,.2f} • Total ฿{o['total']:,.2f}"),10,True).pack(anchor='w',pady=10)
        tracking=self.entry(content,self.ui('เลขพัสดุ / ขนส่ง','Tracking number / carrier'));tracking.insert(0,o['tracking'])
        note=self.entry(content,self.ui('หมายเหตุ / เหตุผลแก้ไขสถานะ / เหตุผลคืนเงินและเลขอ้างอิง','Note / status correction reason / refund reason and transfer reference'));note.insert(0,o['admin_note'])
        from support import returns
        import json
        requests=data.query(self.user['id'],'SELECT * FROM return_requests WHERE order_id=?',(o['id'],))
        if requests:
            request=requests[0]
            self.label(content,self.ui('คำขอคืนสินค้า','Return request'),19,True).pack(anchor='w',pady=(16,6))
            return_status={'pending':self.ui('รอตรวจสอบ','Pending review'),'approved':self.ui('ร้านรับคำขอแล้ว','Approved'),'rejected':self.ui('ปฏิเสธคำขอ','Rejected'),'refunded':self.ui('บันทึกคืนเงินแล้ว','Refund recorded')}
            self.label(content,f"{return_status.get(request['status'],request['status'])} · {request['reason']}\n{request['bank']} / {request['account_name']} / {request['account_number']}",12,wraplength=1100).pack(anchor='w',pady=6)
            for returned in json.loads(request['items']):self.label(content,f"{returned['name']} / {self.color_label(returned['color'])} / {db.size_label(returned['size'])} × {returned['quantity']}",11,wraplength=1100).pack(anchor='w',pady=4)
            request_actions=tk.Frame(content,bg='white');request_actions.pack(anchor='w',pady=8)
            def review_request(value):
                try:
                    returns.review(self.user['id'],o['id'],value,note.get());win.destroy();self.order_dialog(receipts.order_for(o['user_id'],o['id']))
                except (ValueError,PermissionError) as exc:messagebox.showerror('JPZ',str(exc),parent=win)
            self.button(request_actions,self.ui('รับคำขอคืนสินค้า','Approve return request'),lambda:review_request('approved'),compact=True).pack(side='left')
            self.button(request_actions,self.ui('ปฏิเสธคำขอ','Reject return request'),lambda:review_request('rejected'),compact=True).pack(side='left',padx=8)
        elif o.get('refund_bank'):
            self.label(content,self.ui('บัญชีรับเงินคืน','Refund account')+f"\n{o['refund_bank']} / {o['refund_name']} / {o['refund_account']}",12,wraplength=1100).pack(anchor='w',pady=10)
        payment=db.latest_payment(o['id'])
        if payment:self.button(content,self.ui('ดูหลักฐานชำระเงิน','View payment receipt'),lambda:self.receipt_dialog(payment),compact=True).pack(anchor='w',pady=8)
        manual_reference=None;manual_checked=tk.BooleanVar(value=False);not_shipped=tk.BooleanVar(value=False)
        if o['payment_status']=='paid':
            check_field(content,text=self.ui('ยืนยันยังไม่ได้จัดส่งจริง · ใช้แก้สถานะที่กดผิดกลับเป็นรอตรวจสอบ','Confirm goods have not actually shipped · for correcting a mistaken status'),variable=not_shipped).pack(anchor='w',pady=10)
        if payment and o['payment_status']=='under_review':
            manual_reference=self.entry(content,self.ui('เลขอ้างอิงจากสลิป · ระบบตรวจเลขซ้ำ','Slip transaction reference · duplicate check'))
            check_field(content,text=self.ui('ฉันตรวจยอดเงินเข้าบัญชีร้านจริงแล้ว','I checked the actual incoming payment in the store bank account'),variable=manual_checked).pack(anchor='w',pady=10)
            self.label(content,self.ui('เลขไม่ซ้ำไม่ได้ยืนยันการโอน ต้องตรวจยอด บัญชี และเวลาเงินเข้าก่อนกดยืนยัน','A unique reference is not proof of payment. Check amount, account and transfer time before approval.'),11,fg='#786D5B',wraplength=1000).pack(anchor='w',pady=6)
            self._manual_payment_ui=dict(reference=manual_reference,checked=manual_checked)
        if payment and o['payment_status']=='under_review':
            from support import slip_verification
            import threading,queue
            verify_status=self.label(content,'',12,fg='#5D6975',wraplength=1000,justify='left');verify_status.pack(anchor='w',pady=6)
            verify_status.bind('<Configure>',lambda event:verify_status.configure(wraplength=max(180,content.winfo_width()-24)))
            def verify_slip():
                if not slip_verification.configured():
                    verify_status.configure(text=self.ui('EasySlip ยังไม่ได้ตั้งค่า ตรวจเงินเข้าและยืนยันสลิปเองได้ด้านล่าง','EasySlip is not configured. Check the bank payment and approve manually below.'),fg='#786D5B');return
                verify_button.configure(state='disabled');verify_status.configure(text=self.ui('กำลังตรวจเลขอ้างอิง ยอดเงิน บัญชีผู้รับ และสลิปซ้ำ…','Checking transaction reference, amount, receiver and duplicate slip…'),fg='#5D6975')
                result=queue.Queue();actor=self.user['id']
                def run():
                    try:result.put((True,slip_verification.verify_and_approve(actor,o['id'])))
                    except Exception as exc:result.put((False,str(exc) if isinstance(exc,(ValueError,PermissionError)) else self.ui('ตรวจสลิปไม่สำเร็จ ยังไม่ยืนยันชำระ','Slip verification failed; payment remains unapproved.')))
                def poll():
                    if not win.winfo_exists():return
                    try:ok,message=result.get_nowait()
                    except queue.Empty:win.after(100,poll);return
                    verify_button.configure(state='normal')
                    if ok:
                        win.destroy();self.order_dialog(receipts.order_for(o['user_id'],o['id']))
                    else:verify_status.configure(text=message,fg='#BB2020')
                threading.Thread(target=run,daemon=True).start();win.after(100,poll)
            verify_button=self.button(content,self.ui('ตรวจสลิปอัตโนมัติ / EasySlip','Verify slip / EasySlip'),verify_slip,dark=True,compact=True)
            if slip_verification.configured():verify_button.pack(anchor='w',pady=8)
        verified=data.query(self.user['id'],'SELECT trans_ref FROM verified_slips WHERE order_id=?',(o['id'],))
        manual_approval=receipts.approval(o['id'])
        if manual_approval and manual_approval['method']=='manual' and o['payment_status']=='paid':self.label(content,self.ui('แอดมินยืนยันเงินเข้า · เลขอ้างอิง: ','Bank payment confirmed by admin · Reference: ')+manual_approval['trans_ref'],12,True).pack(anchor='w',pady=6)
        if verified:self.label(content,self.ui('เลขอ้างอิงที่ตรวจแล้ว: ','Verified transaction: ')+verified[-1]['trans_ref'],12,True).pack(anchor='w',pady=6)
        if o['payment_status']=='paid':
            delivery=receipts.delivery(o['id']);mail_status=(delivery or {}).get('status','pending')
            caption=self.ui('อีเมลใบเสร็จยังไม่ได้เปิดใช้','Receipt email is not enabled') if not receipts.configured() else self.ui('ส่งใบเสร็จทางอีเมลแล้ว','Receipt emailed') if mail_status=='sent' else self.ui('ส่งอีเมลไม่สำเร็จ','Receipt email failed') if mail_status=='failed' else self.ui('ใบเสร็จรอส่งอีเมล','Receipt email pending')
            mail_label=self.label(content,caption,11,fg='#5D6975');mail_label.pack(anchor='w',pady=6)
            if (verified or receipts.approval(o['id'])) and receipts.configured():
                def retry_receipt():
                    try:receipts.retry(self.user['id'],o['id'])
                    except (ValueError,PermissionError) as exc:mail_label.configure(text=str(exc),fg='#BB2020')
                retry_button=self.button(content,self.ui('ลองส่งใบเสร็จอีกครั้ง','Retry receipt email'),retry_receipt,compact=True);retry_button.pack(anchor='w',pady=(0,6))
                def refresh_mail():
                    if not win.winfo_exists():return
                    delivery=receipts.delivery(o['id']) or {};status=delivery.get('status','pending')
                    text=self.ui('ส่งใบเสร็จทางอีเมลแล้ว','Receipt emailed') if status=='sent' else self.ui('ส่งอีเมลไม่สำเร็จ','Receipt email failed') if status=='failed' else self.ui('ใบเสร็จรอส่งอีเมล','Receipt email pending')
                    mail_label.configure(text=text);retry_button.configure(state='normal' if status=='failed' else 'disabled');win.after(1000,refresh_mail)
                refresh_mail()
        buttons=tk.Frame(content,bg='white');buttons.pack(fill='x',pady=12)
        actions=[('approve','ยืนยันชำระเงิน','Approve payment'),('reject','ปฏิเสธหลักฐาน','Reject receipt'),('review','เปลี่ยนเป็นกำลังตรวจสอบ','Return to review'),('prepare','รอจัดส่ง','Preparing'),('ship','จัดส่ง','Ship'),('complete','สำเร็จ','Complete'),('cancel','ยกเลิก','Cancel'),('refund','คืนเงินทั้งคำสั่งซื้อ','Refund entire order'),('note','บันทึก','Save note')]
        from support import product_promotions
        self.label(content,product_promotions.label(o.get('discount_kind','daily'),self.lang)+f" · VAT 7% รวมในราคา ฿{o.get('vat_amount',0):,.2f}",11).pack(anchor='w',pady=5)
        allowed={'note'}
        if payment and o['payment_status'] in ('waiting_payment','rejected','cancelled','paid'):allowed.add('review')
        if o['payment_status']=='under_review' and o['order_status']!='cancelled':
            allowed.update(['approve','reject'])
            from support import slip_verification
            # ผู้ดูแลสามารถตรวจเงินเข้าด้วยตนเอง แม้ตั้งค่าบริการไว้แล้ว
        if o['payment_status']=='paid':
            allowed.add('refund')
            if o['order_status']=='preparing':allowed.add('ship')
            if o['order_status']=='shipped':allowed.add('complete')
        elif o['order_status']=='waiting_payment':allowed.add('cancel')
        def perform(action):
            if action=='approve' and not manual_checked.get():
                messagebox.showerror('JPZ',self.ui('ตรวจเงินเข้าและติ๊กยืนยันก่อนรับชำระ','Check incoming funds and tick the confirmation before approval.'),parent=win);return
            if action!='note':
                prompt=self.ui('ยืนยันดำเนินการกับคำสั่งซื้อนี้?','Confirm this order action?')
                if action=='refund':prompt=self.ui('คุณโอนคืนเงินจริงภายนอกแอปแล้วใช่ไหม? ระบบนี้บันทึกการคืนเงิน ไม่โอนเงินให้','Have you refunded the customer externally? This action records the refund ; it does not transfer money.')
                if action=='review':prompt=self.ui('เปลี่ยนกลับเป็นรอตรวจสอบ? หากยืนยันชำระผิด ระบบจะคืนสต็อกและหยุดคิวใบเสร็จ แต่เรียกคืนอีเมลที่ส่งไปแล้วไม่ได้ กรุณากรอกเหตุผลในหมายเหตุ','Return to review? Mistaken approval will restore stock and stop queued receipts. An email already sent cannot be recalled. Enter a reason in the note field.')
                if not messagebox.askyesno('JPZ',prompt,parent=win):return
            try:
                data.change_order(self.user['id'],o['id'],action,tracking.get(),note.get(),reference=manual_reference.get() if action=='approve' and manual_reference else None,not_shipped_confirmed=not_shipped.get())
                if action == 'approve':receipts.start_worker()
                win.destroy();self._admin('orders')
            except (ValueError,PermissionError,sqlite3.Error) as exc:messagebox.showerror('JPZ',str(exc),parent=win)
        self._admin_order_buttons={}
        for i,(key,th,en) in enumerate(actions):
            btn=self.button(buttons,self.ui(th,en),lambda x=key:perform(x),dark=key=='approve',compact=True)
            self._admin_order_buttons[key]=btn
            btn.configure(state='normal' if key in allowed else 'disabled')
            btn.grid(row=i//4,column=i%4,padx=3,pady=3,sticky='ew')
        self._admin_order_actions={key for key,th,en in actions}

    # เปิดเอกสารใบเสร็จของคำสั่งซื้อที่แอดมินเลือก
    def receipt_dialog(self,pay):
        win=tk.Toplevel(self);win.title('หลักฐานชำระเงิน');win.geometry('650x740')
        body=self.scroll_content(win)
        try:self.file_picture(body,pay['receipt_path'],610,650)
        except (OSError,ValueError) as exc:self.label(body,'เปิดภาพไม่ได้: '+str(exc),12).pack(pady=15)
        self.label(body,'ส่งเมื่อ '+receipts.local_time(pay['uploaded_at'])+' (เวลาไทย)',11).pack(pady=10)


    # หนึ่งแถวต่อรุ่น เลือกสีและไซซ์ในแผงเดียวเพื่อดูรูปและแก้สต็อกจริง
    def product_list(self,b):
        from support import inventory_ui
        return inventory_ui.show(self,b)

    def legacy_product_list(self,b):
        from support import gallery
        from PIL import ImageOps
        self.label(b,self.ui('เลือกรุ่นสินค้า แล้วเลือกสีและไซซ์เพื่อดูหรือปรับจำนวน','Select a product, then choose a color and size to manage stock.'),11,fg='#5D6975',justify='left').pack(anchor='w',pady=10)
        bar=tk.Frame(b,bg='white');bar.pack(fill='x',pady=8)
        self.label(bar,self.ui('ทรงยีนส์','Jeans fit'),11,True).pack(side='left')
        fit_map={self.ui('ทุกทรง','All fits'):''};fit_map.update({self.fit_label(key):key for key in data.FITS})
        fit=select_field(bar,values=list(fit_map),state='readonly',width=15);fit.set(next(iter(fit_map)));fit.pack(side='left',padx=8)
        self.label(bar,self.ui('ค้นหาชื่อ / รหัสสินค้า','Search name / SKU'),11).pack(side='left',padx=(10,4))
        search=tk.StringVar();query=field(bar);query.configure(textvariable=search,width=230);query.pack(side='left',padx=6)
        self.button(bar,self.ui('+ เพิ่มสินค้า','+ Add product'),lambda:self.product_dialog(),dark=True,compact=True).pack(side='right')
        split=tk.PanedWindow(b,orient='horizontal',bg='white',sashwidth=8);split.pack(fill='both',expand=True)
        left=tk.Frame(split,bg='white',width=350);right=tk.Frame(split,bg='white')
        split.add(left,minsize=300,width=350);split.add(right,minsize=360)
        panel=self.scroll_content(left)
        name=self.label(panel,self.ui('เลือกสินค้าในตาราง','Select a product'),16,True,wraplength=310,anchor='w',justify='left');name.pack(fill='x',padx=12,pady=8)
        photo=tk.Label(panel,bg='#F1F3F5');photo.pack(fill='x',padx=12,pady=6)
        photo_note=self.label(panel,'',10,fg='#5D6975',wraplength=300,justify='left',anchor='w');photo_note.pack(fill='x',padx=12,pady=2)
        colors=tk.Frame(panel,bg='white');colors.pack(fill='x',padx=12,pady=5)
        self.label(panel,self.ui('ไซซ์','Size'),11,True).pack(anchor='w',padx=12,pady=(8,3))
        sizes=select_field(panel,state='readonly',width=12);sizes.pack(fill='x',padx=12,pady=3)
        current=self.label(panel,'',15,True,anchor='w');current.pack(fill='x',padx=12,pady=10)
        counts=tk.Frame(panel,bg='white');counts.pack(fill='x',padx=12,pady=3)
        self.label(panel,self.ui('จำนวนที่ต้องการปรับ (ตัว)','Quantity to adjust (items)'),11).pack(anchor='w',padx=12,pady=(8,3))
        amount=field(panel);amount.insert(0,'1');amount.pack(fill='x',padx=12)
        actions=tk.Frame(panel,bg='white');actions.pack(fill='x',padx=12,pady=8)
        notice=self.label(panel,'',11,anchor='w',justify='left',wraplength=305);notice.pack(fill='x',padx=12,pady=6)
        counts.pack_forget();counts.pack(fill='x',padx=12,pady=6)
        tree=self.table(right,[('code',self.ui('รหัสสินค้า','SKU'),95),('name',self.ui('สินค้า','Product'),220),('fit',self.ui('ทรงยีนส์','Fit'),100),('stock',self.ui('จำนวนรวม','Total stock'),90),('price',self.ui('ราคารวม VAT','Price incl. VAT'),100),('before_vat',self.ui('ก่อน VAT','Before VAT'),100)],height=8)
        state={'product':None,'color':None,'size':None,'variant':None,'rows':{}}
        self._inventory_ui={'tree':tree,'state':state,'sizes':sizes,'amount':amount,'notice':notice,'stock':current,'photo':photo,'colors':colors,'search':search,'fit':fit}
        palette={'black':'#191919','dark_indigo':'#23344D','raw_indigo':'#263D59','washed_blue':'#6E93AC','light_blue':'#B1CDDF','vintage_blue':'#64869B','grey':'#8B8D90'}
        # อ่านสต็อกใหม่ทุกครั้งที่เลือกสี ไซซ์ หรือบันทึก ไม่ใช้ยอดที่ค้างในหน้าจอ
        def render(color=None,size=None):
            product=state['product']
            if not product:return
            variants=db.variants(product['id']);options=sorted({v['color'] for v in variants})
            state['color']=color if color in options else state['color'] if state['color'] in options else options[0] if options else None
            chosen=state['color'];available=[v for v in variants if v['color']==chosen]
            keys=sorted({v['size'] for v in available});wanted=size if size is not None else state['size']
            state['size']=wanted if wanted in keys else keys[0] if keys else None
            state['variant']=next((v for v in available if v['size']==state['size']),None)
            name.configure(text=product['name'])
            visibility_button.configure(text=self.ui('ซ่อนสินค้า','Hide product') if product['active'] else self.ui('แสดงสินค้า','Show product'))
            image=gallery.preview(product['id'],chosen,'FRONT') if chosen else None
            fallback=False
            if image is None:
                sources=data.query(self.user['id'],"SELECT color FROM product_gallery WHERE product_id=? AND view='FRONT' ORDER BY color",(product['id'],))
                for source in sources:
                    image=gallery.preview(product['id'],source['color'],'FRONT')
                    if image is not None:fallback=True;break
            photo_note.configure(text=self.ui('ภาพรุ่นสินค้า · สีนี้ยังไม่มีรูปแยก','Product photo · no separate photo for this color') if fallback else '')
            if image is not None:
                picture=gallery.to_photo(ImageOps.pad(image,(280,180),color='#F1F3F5'),master=self);photo.configure(image=picture,text='',height=180);photo._image=picture
            else:photo.configure(image='',text=self.ui('ยังไม่มีรูปสำหรับสีนี้','No photo for this color'),height=8);photo._image=None
            for child in colors.winfo_children():child.destroy()
            for index,option in enumerate(options):
                selected=option==chosen
                button=self.button(colors,self.color_label(option),lambda value=option:render(value),dark=selected,compact=True)
                button.grid(row=index//2,column=index%2,padx=3,pady=3,sticky='ew');button._inventory_color=option
                # สี่เหลี่ยมสีช่วยให้แยกสีได้โดยไม่ต้องอ่านชื่ออย่างเดียว
                chip=tk.Canvas(button,width=14,height=14,bg=palette.get(option,'#777777'),highlightthickness=1,highlightbackground='#B6C0C9');chip.place(x=6,rely=.5,anchor='w')
                chip.bind('<Button-1>',lambda event,value=option:render(value));button.configure(text='   '+self.color_label(option))
            sizes.configure(values=[db.size_label(key) for key in keys]);sizes.set(db.size_label(state['size']) if keys else '')
            variant=state['variant'];stock=variant['stock'] if variant else None
            current.configure(text=self.ui('ยังไม่มีสีและไซซ์ กรุณาเพิ่มก่อน','Add a color and size first') if stock is None else self.ui('หมด' if stock==0 else f'คงเหลือ {stock} ตัว','Sold out' if stock==0 else f'{stock} items in stock'),fg='#BB2020' if stock is not None and stock<5 else '#243E55')
            for child in counts.winfo_children():child.destroy()
            for index,v in enumerate(available):
                text=db.size_label(v['size'])+': '+(self.ui('หมด','Sold out') if not v['stock'] else str(v['stock']))
                stock_chip=self.button(counts,text,lambda value=v['size']:render(size=value),dark=v['size']==state['size'],compact=True)
                if v['stock']<5:stock_chip.configure(text_color='#BB2020' if v['size']!=state['size'] else '#FFD5D5')
                stock_chip.grid(row=index//2,column=index%2,padx=2,pady=2)
            for button in stock_buttons:button.configure(state='normal' if variant else 'disabled')
        def select(event=None):
            if not tree.selection():return
            pid=int(tree.selection()[0]);product=state['rows'].get(pid)
            if not product:return
            if not state['product'] or state['product']['id']!=pid:state.update(color=None,size=None);notice.configure(text='')
            state['product']=product;render()
        def refresh(*args):
            selected=str(state['product']['id']) if state['product'] else None
            rows=db.products(include_archived=True);state['rows']={r['id']:r for r in rows}
            totals={r['product_id']:r['stock'] for r in data.query(self.user['id'],'SELECT product_id,SUM(stock) stock FROM variants GROUP BY product_id')}
            term=search.get().strip().casefold();selected_fit=fit_map[fit.get()]
            tree.delete(*tree.get_children())
            for r in rows:
                if (not selected_fit or r['fit']==selected_fit) and term in (r['code']+' '+r['name']).casefold():
                    stock_total=totals.get(r['id'],0)
                    tree.insert('','end',iid=str(r['id']),tags=('low_stock',) if stock_total<5 else (),values=(r['code'],r['name']+(self.ui(' (ซ่อน)',' (archived)') if not r['active'] else ''),self.fit_label(r['fit']),stock_total,f"{r['price']:,.2f}",f"{db.vat_breakdown(r['price'])['before_vat']:,.2f}"))
            entries=tree.get_children()
            if entries:tree.selection_set(selected if selected in entries else entries[0]);select()
            else:
                state.update(product=None,color=None,size=None,variant=None);name.configure(text=self.ui('ไม่พบสินค้า','No products found'));photo.configure(image='',text='');photo._image=None
                for host in (colors,counts):
                    for child in host.winfo_children():child.destroy()
                sizes.set('');sizes.configure(values=[]);current.configure(text='')
                for button in stock_buttons:button.configure(state='disabled')
        # ปรับจำนวนผ่านธุรกรรมที่ตรวจสิทธิ์แอดมินและไม่อนุญาตให้สต็อกติดลบ
        def adjust(mode):
            if not state['variant']:return
            try:
                raw=amount.get().strip()
                if not raw.isascii() or not raw.isdecimal():raise ValueError(self.ui('กรอกจำนวนเต็มตั้งแต่ 0 ขึ้นไป','Enter a whole number of zero or more.'))
                quantity=int(raw)
                if mode=='remove' and quantity>db.variant_stock(state['product']['id'],state['color'],state['size']):raise ValueError(self.ui('จำนวนที่ลดมากกว่าสินค้าคงเหลือ','Cannot remove more than the available stock.'))
                data.adjust_stock(self.user['id'],state['variant']['id'],quantity,mode);refresh();notice.configure(text=self.ui('บันทึกจำนวนแล้ว','Stock saved.'),fg='#26734D')
            except (ValueError,PermissionError,sqlite3.Error) as exc:notice.configure(text=str(exc),fg='#BB2020')
        stock_buttons=[]
        for mode,th,en in [('add','+ เพิ่ม','+ Add'),('remove','− ลด','− Remove'),('set','ตั้งจำนวน','Set stock')]:
            button=self.button(actions,self.ui(th,en),lambda value=mode:adjust(value),dark=mode=='add',compact=True);button.pack(side='left',padx=2);stock_buttons.append(button)
        tools=tk.Frame(panel,bg='white');tools.pack(fill='x',padx=12,pady=10)
        def call(handler):
            if state['product']:handler(state['product'])
        for index,(th,en,handler) in enumerate([('แก้ไขสินค้า','Edit product',self.product_dialog),('เพิ่มสี / ไซซ์','Add color / size',self.variant_dialog),('รูปสินค้า','Product photos',self.gallery_dialog),('ตารางไซซ์','Measurements',self.admin_size_dialog),('โปรโมชั่นสินค้า','Product promotion',self.product_promotion_dialog)]):
            self.button(tools,self.ui(th,en),lambda fn=handler:call(fn),compact=True).grid(row=index//2,column=index%2,padx=3,pady=3,sticky='ew')
        def remove():
            product=state['product']
            if not product:return
            if not messagebox.askyesno('JPZ',self.ui('ลบสินค้านี้ออกจากระบบ?','Delete this product from the store?')):return
            try:catalogue.delete_product(self.user['id'],product['id']);state.update(product=None,color=None,size=None);refresh()
            except (ValueError,PermissionError,sqlite3.Error) as exc:messagebox.showerror('JPZ',str(exc))
        def toggle_visibility():
            product=state['product']
            if not product:return
            try:
                catalogue.set_product_visibility(self.user['id'],product['id'],0 if product['active'] else 1)
                refresh();notice.configure(text=self.ui('บันทึกการแสดงสินค้าแล้ว','Product visibility saved.'),fg='#26734D')
            except (ValueError,PermissionError,sqlite3.Error) as exc:notice.configure(text=str(exc),fg='#BB2020')
        visibility_button=self.button(panel,self.ui('ซ่อนสินค้า','Hide product'),toggle_visibility,compact=True);visibility_button.pack(anchor='w',padx=12,pady=(10,5))
        delete_button=self.button(panel,self.ui('ลบสินค้า','Delete product'),remove,compact=True);delete_button.configure(text_color='#AD2731');delete_button.pack(anchor='w',padx=12,pady=(0,10))
        self._inventory_ui.update(visibility=visibility_button,delete=delete_button)
        sizes.bind('<<ComboboxSelected>>',lambda event:render(size=db.size_key(sizes.get())))
        tree.bind('<<TreeviewSelect>>',select);tree.bind('<Double-1>',lambda event:sizes.focus_set())
        fit.bind('<<ComboboxSelected>>',refresh)
        pending=[None]
        def schedule(*args):
            if pending[0]:self.after_cancel(pending[0])
            pending[0]=self.after(180,lambda:refresh() if tree.winfo_exists() else None)
        search.trace_add('write',schedule)
        self._inventory_ui.update(refresh=refresh,render=render,adjust=adjust)
        refresh()

    # เปิดฟอร์มข้อมูลสินค้าและตัวเลือกสี
    def product_promotion_dialog(self,p):
        from support import product_promotions
        data.query(self.user['id'],'SELECT 1')
        offer=product_promotions.setting(p['id'])
        win=tk.Toplevel(self);win.title(self.ui('โปรโมชั่นสินค้า','Product promotion'));win.geometry('650x640');win.minsize(560,580);win.configure(bg='white');win.transient(self)
        win.bind('<Escape>',lambda event:(win.destroy(),'break')[1])
        footer=tk.Frame(win,bg='white');footer.pack(side='bottom',fill='x',padx=24,pady=18)
        body=self.scroll_content(win);body.configure(bg='white')
        form=tk.Frame(body,bg='white');form.pack(fill='x',padx=24,pady=20)
        self.label(form,p['name'],21,True,wraplength=550,justify='left').pack(anchor='w',pady=(0,8))
        self.label(form,self.ui(f"ราคาปกติ ฿{p['price']:,.2f}",f"Regular base price ฿{p['price']:,.2f}"),13,fg='#5D6975').pack(anchor='w',pady=(0,15))
        enabled=tk.BooleanVar(value=bool(offer['enabled']))
        check_field(form,text=self.ui('เปิดโปรโมชั่นสินค้านี้','Enable this product offer'),variable=enabled,bg='white',font=self.font(12)).pack(anchor='w',pady=8)
        names={self.ui('ลดเป็นเปอร์เซ็นต์','Percentage discount'):'percent',self.ui('ตั้งราคาพิเศษ','Special base price'):'price'}
        kind=select_field(form,values=list(names),state='readonly');kind.set(next(label for label,key in names.items() if key==offer['kind']));kind.pack(fill='x',pady=12)
        value=self.entry(form,self.ui('เปอร์เซ็นต์ / ราคาพิเศษ (บาท)','Percentage / special base price (THB)'));value.insert(0,f"{offer['value']:g}")
        self.label(form,self.ui('ราคาพิเศษยังบวกราคาเพิ่มตามไซซ์ที่ตั้งไว้\nระบบเลือกส่วนลดรายสินค้ารวมทั้งคำสั่งซื้อหรือส่วนลดรายวันที่คุ้มกว่า ไม่ลดซ้อน','Special base prices keep configured size surcharges.\nThe order uses the better total discount: product offers or daily promotion, without stacking.'),12,wraplength=550,justify='left',fg='#5D6975').pack(anchor='w',pady=18)
        error=self.label(form,'',12,fg='#BB2020',wraplength=550,justify='left');error.pack(fill='x',pady=8)
        def save():
            try:
                product_promotions.save(self.user['id'],p['id'],names[kind.get()],value.get(),enabled.get());win.destroy();self._admin('stock')
            except (ValueError,PermissionError,sqlite3.Error) as exc:error.configure(text=str(exc))
        self.button(footer,self.ui('ยกเลิก','Cancel'),win.destroy).pack(side='left')
        save_button=self.button(footer,self.tr('save'),save,dark=True);save_button.pack(side='right')
        self._product_promotion_ui=dict(window=win,enabled=enabled,kind=kind,value=value,error=error,save=save_button)

    # J64 | เพิ่มและแก้ไขสินค้า
    def product_dialog(self,product=None):
        win=tk.Toplevel(self);win.title(self.ui('แก้ไขสินค้า' if product else 'เพิ่มสินค้า','Edit product' if product else 'Add product'));win.configure(bg='white');win.state('zoomed');win.minsize(520,440)
        footer=tk.Frame(win,bg='white',height=112);footer.pack(side='bottom',fill='x',padx=20,pady=12);footer.pack_propagate(False)
        footer_actions=tk.Frame(footer,bg='white');footer_actions.pack(side='bottom',fill='x',pady=6)
        error=self.label(footer,'',11,fg='#BB2020',wraplength=620);error.pack(anchor='w',pady=(0,6))
        form=self.scroll_content(win)
        self.label(form,self.ui('แก้ไขสินค้า' if product else 'เพิ่มสินค้า','Edit product' if product else 'Add product'),24,True).pack(anchor='w',padx=20,pady=(20,12))
        defaults=dict(name='',code='',price=1290,fit='baggy',style='clean',color='washed_blue',waist=32,hip=42,thigh=26,rise=12,inseam=32,leg_opening=19,active=1,category_id=None)
        from support import sizing
        defaults.update(sizing.reference_base(defaults['fit']))
        defaults.update(product or {})
        labels={'name':('ชื่อสินค้า','Product name'),'code':('รหัสสินค้า','SKU'),'price':('ราคา (บาท)','Price (THB)'),
                'fit':('ทรง','Fit'),'style':('สไตล์','Style'),'color':('สีของยีนส์','Jeans color'),
                'waist':('เอว (นิ้ว)','Waist (inches)'),'hip':('สะโพก (นิ้ว)','Hip (inches)'),
                'thigh':('ต้นขา (นิ้ว)','Thigh (inches)'),'rise':('เป้า (นิ้ว)','Rise (inches)'),
                'inseam':('ความยาวขา (นิ้ว)','Inseam (inches)'),'leg_opening':('ปลายขา (นิ้ว)','Leg opening (inches)'),
                'active':('แสดงขาย: 1 / ซ่อน: 0','Active: 1 / archived: 0'),'category_id':('หมวดสินค้า','Category')}
        if product:self.product_picture(form,product,product['color'],'FRONT',height=230)
        photos={};photo_controls={}
        photo_section=tk.Frame(form,bg='white');photo_section.pack(fill='x',padx=20,pady=(0,16))
        self.label(photo_section,self.ui('รูปสินค้า · เพิ่มพร้อมสินค้าในครั้งเดียว','Product photos · save together with the product'),17,True,wraplength=850,justify='left').pack(anchor='w',pady=(8,6))
        self.label(photo_section,self.ui('เลือกรูปได้ตอนนี้ รูปจะถูกบันทึกเมื่อกดบันทึกสินค้า ใช้กับสีที่เลือกด้านล่าง','Select photos now; they are saved with the product for the color selected below.'),11,fg='#5D6975',wraplength=850,justify='left').pack(anchor='w',pady=(0,12))
        photo_grid=tk.Frame(photo_section,bg='white');photo_grid.pack(fill='x')
        from PIL import Image,ImageTk,ImageOps
        views=[('FRONT','ด้านหน้า','Front'),('BACK','ด้านหลัง','Back'),('DETAIL','เต็มตัว','Full view'),('TEXTURE','รายละเอียด','Details')]
        photo_holders=[]
        def select_photo(view,path=None):
            path=path or filedialog.askopenfilename(parent=win,title=self.ui('เลือกรูปสินค้า','Choose product photo'),filetypes=[('JPG / PNG / WebP','*.jpg *.jpeg *.png *.webp')])
            if not path:return
            try:
                with Image.open(path) as original:image=ImageOps.exif_transpose(original).convert('RGB');image.thumbnail((200,160))
                image=ImageTk.PhotoImage(image,master=self);widget=photo_controls[view]['preview'];widget.configure(image=image,text='',height=160,width=200);widget._image=image
                photos[view]=path;photo_controls[view]['filename'].configure(text=Path(path).name);error.configure(text='')
            except (OSError,ValueError,Image.DecompressionBombError):error.configure(text=self.ui('เปิดรูปไม่ได้ กรุณาเลือกไฟล์รูปภาพที่ถูกต้อง','Cannot open this photo. Choose a valid image file.'))
        def remove_photo(view):
            photos.pop(view,None);widget=photo_controls[view]['preview'];widget.configure(image='',text=self.ui('ยังไม่เลือกรูปใหม่','No new photo selected'));widget._image=None;photo_controls[view]['filename'].configure(text='')
        for view,th,en in views:
            holder=tk.Frame(photo_grid,bg='#F6F8FA',highlightbackground='#D8DFE6',highlightthickness=1);photo_holders.append(holder)
            self.label(holder,self.ui(th,en),12,True,bg='#F6F8FA').pack(anchor='w',padx=12,pady=(10,6))
            preview=tk.Label(holder,text=self.ui('ยังไม่เลือกรูปใหม่','No new photo selected'),bg='#F6F8FA',height=3);preview.pack(padx=12,pady=8)
            filename=self.label(holder,'',10,bg='#F6F8FA',wraplength=200);filename.pack(padx=12)
            controls=tk.Frame(holder,bg='#F6F8FA');controls.pack(padx=12,pady=10)
            choose=self.button(controls,self.ui('เลือกรูป','Choose photo'),lambda v=view:select_photo(v),compact=True);choose.pack(side='left')
            self.button(controls,self.ui('เอาออก','Remove'),lambda v=view:remove_photo(v),compact=True).pack(side='left',padx=6)
            photo_controls[view]=dict(preview=preview,filename=filename,choose=choose)
        def photo_layout(event):
            columns=4 if event.width>=1080 else 2 if event.width>=540 else 1
            for column in range(4):photo_grid.columnconfigure(column,weight=int(column<columns))
            for index,holder in enumerate(photo_holders):holder.grid(row=index//columns,column=index%columns,sticky='nsew',padx=6,pady=6)
        photo_grid.bind('<Configure>',photo_layout)
        entries={};field_rows={}
        for key in data.PRODUCT_FIELDS:
            if key=='category_id':continue
            row=tk.Frame(form,bg='white');row.pack(fill='x',padx=20,pady=8)
            field_rows[key]=row
            self.label(row,self.ui(*labels[key]),11,True).pack(anchor='w',pady=(0,5))
            if key in ('fit','style','color','active'):
                values={'fit':data.FITS,'style':data.STYLES,'color':data.COLORS,'active':('1','0')}[key]
                entry=select_field(row,values=values,state='readonly');entry.set(str(defaults[key]));entry.pack(fill='x')
            else:
                entry=tk.Entry(row,font=self.font(10));entry.insert(0,str(defaults[key]));entry.pack(fill='x')
            entries[key]=entry
        initial_quantity=initial_size=None
        stock_entries={};size_drafts={};size_buttons={};selected_size=tk.IntVar(value=32)
        if product:
            size_drafts={row['size']:dict(row) for row in sizing.rows(product['id'])}
        for key in sizing.FIELDS:field_rows[key].pack_forget()
        size_section=tk.Frame(form,bg='#F6F8FA',highlightbackground='#D8DFE6',highlightthickness=1)
        size_section.pack(fill='x',padx=20,pady=12,before=field_rows['active'])
        self.label(size_section,self.ui('สัดส่วนกางเกงแยกแต่ละไซซ์','Garment measurements by size'),17,True,bg='#F6F8FA').pack(anchor='w',padx=16,pady=(14,6))
        size_caption=self.label(size_section,'',13,True,bg='#F6F8FA',fg='#243E55');size_caption.pack(anchor='w',padx=16,pady=6)
        self.label(size_section,self.ui('เลือกไซซ์แล้วเปิดหน้ากรอกสัดส่วน ข้อมูลของแต่ละไซซ์บันทึกแยกกัน\nไซซ์ที่ยังไม่กรอกใช้ค่าประมาณ และระบุว่าเป็นข้อมูลประมาณการ','Choose a size and open its measurements. Each size is saved separately.\nSizes you have not entered retain estimated measurements.'),11,bg='#F6F8FA',wraplength=850,justify='left').pack(anchor='w',padx=16,pady=6)
        size_choices=tk.Frame(size_section,bg='#F6F8FA');size_choices.pack(fill='x',padx=12,pady=8)
        def mark_size(size):
            selected_size.set(size)
            size_caption.configure(text=self.ui('ไซซ์ที่เลือก: ','Selected size: ')+db.size_label(size)+f' / W{size}')
            for value,button in size_buttons.items():button.configure(fg_color='#243E55' if value==size else '#FFFFFF',text_color='white' if value==size else '#243E55')
        def keep_size(size,row,quantity):
            size_drafts[size]=dict(row)
            if quantity is not None:
                stock_entries[size].delete(0,'end');stock_entries[size].insert(0,str(quantity))
            if size==32:
                for key in sizing.FIELDS:entries[key].delete(0,'end');entries[key].insert(0,str(row[key]))
            mark_size(size)
            size_status.configure(text=self.ui('เก็บข้อมูลแล้ว: ','Applied: ')+db.size_label(size)+f' / W{size}'+self.ui(' · รอกดบันทึกสินค้าและรูป',' · save the product to finish'))
        def open_size(size=None):
            size=selected_size.get() if size is None else size;mark_size(size)
            base={key:entries[key].get() for key in sizing.FIELDS}
            values=size_drafts.get(size) or dict(zip(sizing.FIELDS,sizing.grade(base,size)),estimated=True)
            self.product_size_draft_dialog(win,entries['name'].get() or self.ui('สินค้าใหม่','New product'),size,values,bool(values.get('estimated',True)),keep_size,stock=stock_entries[size].get() if size in stock_entries else None)
        for index,(size,label) in enumerate(db.SIZE_LABELS.items()):
            button=self.button(size_choices,f'{label} / W{size}',lambda value=size:open_size(value),compact=True)
            button.grid(row=index//5,column=index%5,sticky='ew',padx=4,pady=4);size_buttons[size]=button
        for column in range(5):size_choices.columnconfigure(column,weight=1)
        size_status=self.label(size_section,'',11,bg='#F6F8FA',fg='#247450',wraplength=850);size_status.pack(anchor='w',padx=16,pady=(4,14));mark_size(32)
        if not product:
            stock_section=tk.Frame(form,bg='white');stock_section.pack(fill='x',before=size_section)
            self.label(stock_section,self.ui('จำนวนสินค้าแต่ละไซซ์','Stock by size'),16,True).pack(anchor='w',padx=20,pady=(18,8))
            stock_caption=self.label(stock_section,'',11,fg='#5D6975',wraplength=610,justify='left');stock_caption.pack(anchor='w',padx=20,pady=(0,10))
            def stock_color(*args):stock_caption.configure(text=self.ui('กำลังกรอกสต็อกไซซ์ ','Editing stock for ')+db.size_label(selected_size.get())+f' / W{selected_size.get()} · '+self.ui('สี ','Color ')+self.color_label(entries['color'].get()))
            selected_size.trace_add('write',stock_color)
            entries['color'].bind('<<ComboboxSelected>>',stock_color);stock_color()
            blocks=tk.Frame(stock_section,bg='white');blocks.pack(fill='x',padx=20,pady=8)
            for index,(size,label) in enumerate(db.SIZE_LABELS.items()):
                block=tk.Frame(blocks,bg='#F6F8FA',highlightbackground='#D8DFE6',highlightthickness=1)
                block.grid(row=index//3,column=index%3,sticky='ew',padx=5,pady=5)
                self.label(block,f'{label} / W{size}',11,True,bg='#F6F8FA').pack(padx=8,pady=(10,6))
                entry=self.entry(block,'');entry.insert(0,'0');entry.pack_configure(fill='x',padx=10,pady=(0,12));stock_entries[size]=entry
                entry.bind('<FocusIn>',lambda event,value=size:mark_size(value),add=True)
                self.button(block,self.ui('กรอกสัดส่วนไซซ์นี้','Measurements for this size'),lambda value=size:open_size(value),compact=True).pack(fill='x',padx=10,pady=(0,12))
            for column in range(3):blocks.grid_columnconfigure(column,weight=1,uniform='initial_stock')
            initial_quantity=stock_entries[32]
            initial_size=tk.StringVar(value='L')
            def fit_reference(event):
                for key,value in sizing.reference_base(entries['fit'].get()).items():
                    if 32 not in size_drafts:entries[key].delete(0,'end');entries[key].insert(0,str(value))
            entries['fit'].bind('<<ComboboxSelected>>',fit_reference)
            self.label(stock_section,self.ui('ใส่จำนวนของแต่ละไซซ์ แล้วกดบันทึกครั้งเดียว ไซซ์ที่ยังไม่มีสินค้าให้ใส่ 0','Enter quantities for each size and save once. Use 0 for sizes without stock.'),11,wraplength=610,justify='left').pack(padx=20,pady=12)
        def save():
            try:
                values={key:entry.get() for key,entry in entries.items()}
                # คงค่าเดิมไว้เพื่อรองรับฐานข้อมูลเก่า โดยไม่มีหมวดสินค้าในหน้าจอ
                values['category_id']=defaults['category_id']
                stocks={size:int(entry.get()) for size,entry in stock_entries.items()} if stock_entries else None
                pid=catalogue.save_product_with_images(self.user['id'],values,photos,product['id'] if product else None,stocks=stocks,measurements=size_drafts)
                self._inventory_selected=pid;getattr(self,'_inventory_card_colors',{}).update({pid:values['color']})
                win.destroy();self._admin('products')
            except (ValueError,PermissionError,sqlite3.Error,OSError) as exc:error.configure(text=str(exc))
        self.button(footer_actions,self.ui('ยกเลิก','Cancel'),win.destroy).pack(side='left')
        save_button=self.button(footer_actions,self.ui('บันทึกสินค้าและรูป','Save product and photos'),save,dark=True);save_button.pack(side='right')
        win.bind('<Escape>',lambda event:win.destroy())
        footer.bind('<Configure>',lambda event:error.configure(wraplength=max(180,event.width-20)))
        self._product_dialog_ui={'window':win,'entries':entries,'stock':initial_quantity,'size':initial_size,'stocks':stock_entries,'save':save_button,'error':error,'photos':photos,'photo_controls':photo_controls,'select_photo':select_photo,'remove_photo':remove_photo,'form':form,'footer':footer,'size_drafts':size_drafts,'selected_size':selected_size,'size_buttons':size_buttons,'open_size':open_size,'size_caption':size_caption,'size_status':size_status}


    # เปิดฟอร์มข้อมูลรุ่นย่อยตามสีและไซซ์
    def variant_dialog(self,selected_product=None):
        products=db.products(include_archived=True)
        if not products:return
        win=tk.Toplevel(self);win.title('JPZ / COLOR & SIZE');win.geometry('580x580');win.minsize(480,500);win.configure(bg='white')
        footer=tk.Frame(win,bg='white');footer.pack(side='bottom',fill='x',padx=20,pady=16)
        form=self.scroll_content(win)
        names={f"{p['code']} / {p['name']}":p for p in products}
        self.label(form,self.ui('สินค้า','Product'),10,True).pack(anchor='w')
        product=select_field(form,values=list(names),state='readonly');product.set(next((label for label,value in names.items() if selected_product and value['id']==selected_product['id']),next(iter(names))));product.pack(fill='x',pady=(3,10))
        self.label(form,self.tr('color'),10,True).pack(anchor='w')
        color=select_field(form,state='readonly');color.pack(fill='x',pady=(3,10))
        color_map={self.color_label(key):key for key in data.COLORS}
        def update_colors(event=None):
            selected=names[product.get()]
            palette=[self.color_label(key) for key in data.COLORS]
            color.configure(values=palette);color.set(self.color_label(selected['color']))
        product.bind('<<ComboboxSelected>>',update_colors);update_colors()
        self.label(form,self.tr('size'),10,True).pack(anchor='w')
        size=select_field(form,values=list(db.SIZE_LABELS.values()),state='readonly');size.set('L');size.pack(fill='x',pady=(3,10))
        stock=self.entry(form,self.tr('stock'));stock.insert(0,'0')
        error=self.label(form,'',11,fg='#BB2020',wraplength=500,justify='left');error.pack(fill='x',pady=8)
        def save():
            try:
                data.add_variant(self.user['id'],names[product.get()]['id'],color_map[color.get()],db.size_key(size.get()),int(stock.get()))
                win.destroy();self._admin('stock')
            except (ValueError,PermissionError,sqlite3.Error) as exc:error.configure(text=str(exc))
        self.button(footer,self.ui('ยกเลิก','Cancel'),win.destroy).pack(side='left')
        save_button=self.button(footer,self.tr('save'),save,dark=True);save_button.pack(side='right')
        self._variant_dialog_ui=dict(window=win,product=product,color=color,color_map=color_map,size=size,stock=stock,save=save_button,error=error)

    # แสดงบัญชีลูกค้า ข้อมูลติดต่อ และประวัติคำสั่งซื้อ
    # J42 | จัดการบัญชีลูกค้า / แบน
    def admin_customers(self,b):
        self.heading(b,'จัดการบัญชีผู้ใช้','User accounts','ดูบัญชีที่สมัคร ค้นหาชื่อหรืออีเมล และกำหนดสิทธิ์ลูกค้าหรือแอดมิน','Review registered accounts, search name or email, and assign customer or administrator access.')
        bar=tk.Frame(b,bg='white');bar.pack(fill='x',pady=6)
        search=tk.StringVar(value=getattr(self,'_user_search_text',''))
        entry=self.entry(bar,self.ui('ค้นหาชื่อ / อีเมล / เบอร์โทร','Search name / email / phone'));entry.configure(textvariable=search)
        rows=[]
        tree=self.table(b,[('id','ID',70),('name',self.ui('ชื่อ','Name'),200),('email',self.ui('อีเมล','Email'),250),('phone',self.ui('เบอร์สมัคร','Registered phone'),140),('role',self.ui('สิทธิ์','Role'),130),('created',self.ui('สมัครเมื่อ (เวลาไทย)','Registered (Thai time)'),170),('orders',self.ui('คำสั่งซื้อ','Orders'),100),('account_status',self.ui('สถานะบัญชี','Account status'),150)])
        tree._report_kind='accounts'
        notice=self.label(b,'',11,fg='#BB2020',wraplength=1100,justify='left');notice.pack(anchor='w',pady=5)
        def selected():return next((r for r in rows if tree.selection() and str(r['id'])==tree.selection()[0]),None)
        buttons=tk.Frame(b,bg='white');buttons.pack(fill='x',pady=10)
        def update_buttons(event=None):
            user=selected()
            promote.configure(state='normal' if user and user['active'] and user['role']!='admin' else 'disabled')
            demote.configure(state='normal' if user and user['active'] and user['role']!='customer' else 'disabled')
            remove_button.configure(state='normal' if user and user['active'] and user['role']=='customer' else 'disabled')
            unban_button.configure(state='normal' if user and not user['active'] and user['role']=='customer' else 'disabled')
            history_button.configure(state='normal' if user else 'disabled')
        def refresh(*args):
            nonlocal rows
            current=tree.selection();position=tree.yview()[0]
            rows=data.query(self.user['id'],"SELECT u.*, (SELECT COUNT(*) FROM orders o WHERE o.user_id=u.id) order_count FROM users u ORDER BY id DESC")
            needle=search.get().strip().casefold();self._user_search_text=search.get()
            tree.delete(*tree.get_children())
            for row in rows:
                name=(row['first_name']+' '+row['last_name']).strip()
                phone=row.get('registered_phone') or row.get('phone') or ''
                if needle and needle not in (' '.join((name,row['email'],phone,str(row['id'])))).casefold():continue
                role=self.ui('แอดมิน','Admin') if row['role']=='admin' else self.ui('ลูกค้า / ยูสเซอร์','Customer / User')
                account_status=self.ui('ใช้งานได้','Active') if row['active'] else self.ui('ถูกแบน','Banned')
                tree.insert('','end',iid=str(row['id']),values=(row['id'],name,row['email'],phone,role,receipts.local_time(row['created_at']),row['order_count'],account_status))
                tree.set_status_colors(str(row['id']),{'account_status':('#256A43','#E6F2EB') if row['active'] else ('#A02A36','#F9E7EA')})
            if current and tree.exists(current[0]):tree.selection_set(current[0])
            tree.yview_moveto(position);update_buttons()
        def assign(role):
            user=selected()
            if not user:return
            title=self.ui('แอดมิน','Admin') if role=='admin' else self.ui('ลูกค้า / ยูสเซอร์','Customer / User')
            prompt=self.ui(f"เปลี่ยนสิทธิ์ {user['first_name']} {user['last_name']} ({user['email']}) เป็น {title}?",f"Change {user['first_name']} {user['last_name']} ({user['email']}) to {title}?")
            if role=='admin':prompt+='\n'+self.ui('บัญชีนี้จะจัดการสินค้า คำสั่งซื้อ และสิทธิ์บัญชีอื่นได้','This account can manage products, orders and other account roles.')
            if not messagebox.askyesno('JPZ',prompt):return
            try:
                data.change_user_role(self.user['id'],user['id'],role)
                self.user=db.user(self.user['id'])
                if self.user['role']!='admin':
                    self.page_history=[];self.home(push=False);return
                refresh();notice.configure(text=self.ui('บันทึกสิทธิ์แล้ว','Access updated.'),fg='#24633D')
            except (ValueError,PermissionError,sqlite3.Error) as exc:notice.configure(text=str(exc),fg='#BB2020')
        def history():
            customer=selected()
            if not customer:return
            win=tk.Toplevel(self);win.title('ประวัติลูกค้า');win.state('zoomed');win.bind('<Escape>',lambda event:win.destroy());footer=tk.Frame(win,bg='white');footer.pack(side='bottom',fill='x');self.button(footer,self.ui('ปิด','Close'),win.destroy).pack(side='right',padx=20,pady=8);content=self.scroll_content(win)
            def wrap_history(event):
                for child in content.winfo_children():
                    targets=child.winfo_children() if isinstance(child,tk.Frame) else [child]
                    for label in targets:
                        if isinstance(label,tk.Label):label.configure(wraplength=max(180,event.width-64),justify='left')
            content.bind('<Configure>',wrap_history)
            self.label(content,customer['first_name']+' '+customer['last_name'],22,True).pack(anchor='w',padx=20,pady=15)
            for title,key in [('อีเมล','email'),('โทรศัพท์','phone'),('ชื่อผู้รับ','delivery_name'),('ที่อยู่','address'),('รหัสไปรษณีย์','postal_code')]:self.label(content,f'{title}: {customer[key]}',12,wraplength=850).pack(anchor='w',padx=20,pady=5)
            for order in db.orders(customer['id']):
                row=tk.Frame(content,bg='#F3F3F3');row.pack(fill='x',padx=20,pady=8)
                self.label(row,f"ออเดอร์ที่ {order['order_sequence']} · หมายเลขคำสั่งซื้อ {db.order_number(order)} · {receipts.local_time(order['created_at'])} · ฿{order['total']:,.2f}",12,True,bg='#F3F3F3').pack(anchor='w',padx=12,pady=8)
                self.label(row,f"{self.order_status_text(order)}\n{order['customer_name']} / {order['phone']}\n{order['address']} / รหัสไปรษณีย์ {order['postal_code']}",12,bg='#F3F3F3',wraplength=800,justify='left').pack(anchor='w',padx=12,pady=8)
                for item in data.order_items(self.user['id'],order['id']):self.label(row,f"{item['name']} · {self.color_label(item['color'])} / {db.size_label(item['size'])} / {item['quantity']} ตัว",11,bg='#F3F3F3').pack(anchor='w',padx=12,pady=3)
                self.button(row,'เปิดคำสั่งซื้อ',lambda o=order:self.order_dialog(o),compact=True).pack(anchor='w',padx=12,pady=8)
        def remove():
            customer=selected()
            if customer and messagebox.askyesno('JPZ',self.ui('แบนบัญชีลูกค้านี้? ชื่อ ข้อมูล และคำสั่งซื้อยังอยู่ ปลดแบนภายหลังได้','Ban this customer? Their profile and orders are retained; the account can be unbanned later.')):
                try:db.deactivate_customer(self.user['id'],customer['id']);refresh()
                except (ValueError,PermissionError) as exc:notice.configure(text=str(exc),fg='#BB2020')
        def unban():
            customer=selected()
            if customer and messagebox.askyesno('JPZ',self.ui('ปลดแบนบัญชีลูกค้านี้ให้เข้าสู่ระบบได้อีกครั้ง?','Unban this customer and allow login again?')):
                try:db.reactivate_customer(self.user['id'],customer['id']);refresh();notice.configure(text=self.ui('ปลดแบนแล้ว ลูกค้าใช้บัญชีเดิมเข้าสู่ระบบได้','Account unbanned. The customer can sign in with the same account.'),fg='#256A43')
                except (ValueError,PermissionError) as exc:notice.configure(text=str(exc),fg='#BB2020')
        promote=self.button(buttons,self.ui('ตั้งเป็นแอดมิน','Make admin'),lambda:assign('admin'),dark=True);promote.pack(side='left',padx=(0,8))
        demote=self.button(buttons,self.ui('ตั้งเป็นยูสเซอร์','Make user'),lambda:assign('customer'));demote.pack(side='left',padx=(0,8))
        history_button=self.button(buttons,self.ui('ประวัติบัญชี / คำสั่งซื้อ','Account / order history'),history);history_button.pack(side='left',padx=(0,8))
        refresh_button=self.button(buttons,self.ui('รีเฟรช','Refresh'),refresh)
        remove_button=self.button(buttons,self.ui('แบนบัญชีลูกค้า','Ban customer'),remove)
        unban_button=self.button(buttons,self.ui('ปลดแบน','Unban'),unban,dark=True)
        customer_actions=[promote,demote,history_button,refresh_button,remove_button,unban_button]
        for action in customer_actions:action.pack_forget()
        def arrange_actions(event):
            columns=6 if event.width>=1550 else 4 if event.width>=1080 else 3 if event.width>=740 else 2 if event.width>=500 else 1
            for col in range(6):buttons.columnconfigure(col,weight=int(col<columns))
            for index,action in enumerate(customer_actions):action.grid(row=index//columns,column=index%columns,sticky='ew',padx=4,pady=4)
        buttons.bind('<Configure>',arrange_actions)
        # จัดพื้นที่ปุ่มด้านล่างก่อนให้ตารางขยายใช้พื้นที่ที่เหลือ
        buttons.pack_configure(side='bottom',before=tree.master)
        notice.pack_configure(side='bottom',before=tree.master)
        tree.bind('<<TreeviewSelect>>',update_buttons);tree.bind('<Double-1>',lambda event:history())
        search.trace_add('write',refresh)
        self._users_ui=dict(tree=tree,search=search,refresh=refresh,promote=promote,demote=demote,notice=notice,history=history_button,ban=remove_button,unban=unban_button)
        refresh()


    # ตั้งค่าส่วนลดรายวันของร้าน
    # J43 | ตั้งค่าส่วนลดรายวัน
    def admin_rewards(self,b):
        b=self.scroll_content(b)
        self.heading(b,'ส่วนลดรายวัน','Daily discounts','กำหนดเงื่อนไขแต่ละบล็อก ระบบสุ่มวันละหนึ่งบล็อกตามเวลาไทย','Set each block. One block is selected daily in Thai time.')
        config=loyalty.settings();promo=loyalty.daily()
        self.label(b,self.ui(f"วันนี้ {promo['day']} ลด {promo['percent']}% · ซื้อขั้นต่ำ ฿{promo['minimum']:g} · ลดไม่เกิน ฿{promo['cap']:g}",f"Today {promo['day']}: {promo['percent']}% off · minimum ฿{promo['minimum']:g} · capped at ฿{promo['cap']:g}"),14,True,wraplength=1100).pack(anchor='w',pady=12)
        enabled=tk.BooleanVar(value=config['enabled'])
        check_field(b,text=self.ui('เปิดส่วนลดรายวัน','Enable daily discount'),variable=enabled,bg='white',font=self.font(12)).pack(anchor='w',pady=(0,12))
        self.label(b,self.ui('แต่ละบล็อกมีโอกาสถูกสุ่มเท่ากัน','Every block has an equal chance of selection.'),11,fg='#5D6975').pack(anchor='w',pady=(0,12))
        grid=tk.Frame(b,bg='white');grid.pack(fill='x')
        blocks=[];columns=[3]
        controls=tk.Frame(b,bg='white');controls.pack(fill='x',pady=16)
        status=self.label(b,'',11,fg='#BB2020',wraplength=1100);status.pack(anchor='w',pady=6)
        def preview(*args):
            import math
            status.configure(text='')
            for block in blocks:
                try:
                    values={k:float(v.get()) for k,v in block['variables'].items()}
                    if not all(math.isfinite(v) and v>=0 for v in values.values()) or not values['percent'].is_integer() or not 1<=values['percent']<=50 or values['cap']<=0:raise ValueError()
                    block['preview'].pack_forget()
                except (ValueError,TypeError):
                    block['preview'].configure(text=self.ui('กรอกเงื่อนไขส่วนลดให้ถูกต้อง','Enter valid discount conditions.'),fg='#BB2020')
                    block['preview'].pack(anchor='w',pady=8,before=block['delete'])
        def layout(event=None):
            width=event.width if event is not None else grid.winfo_width()
            if width>1:columns[0]=max(1,min(3,width//340))
            for col in range(3):grid.columnconfigure(col,weight=1 if col<columns[0] else 0,uniform='discounts' if col<columns[0] else '')
            for index,block in enumerate(blocks):
                block['frame'].grid(row=index//columns[0],column=index%columns[0],sticky='nsew',padx=6,pady=6)
                block['title'].configure(text=self.ui(f'บล็อก {index+1:02d}',f'Block {index+1:02d}'))
                block['delete'].configure(state='normal' if len(blocks)>1 else 'disabled')
        def remove(block):
            if len(blocks)<=1:return
            blocks.remove(block);block['frame'].destroy();layout();preview()
        def add(values=None):
            values=values or dict(percent=5,minimum=500,cap=200)
            frame=tk.Frame(grid,bg='#F6F8FA',highlightbackground='#DAE0E6',highlightthickness=1)
            inner=tk.Frame(frame,bg='#F6F8FA');inner.pack(fill='both',expand=True,padx=16,pady=16)
            title=self.label(inner,'',15,True,bg='#F6F8FA');title.pack(anchor='w',pady=(0,4))
            block=dict(frame=frame,title=title,variables={},entries={})
            for key,th,en in [('percent','ส่วนลด (%)','Discount (%)'),('minimum','ยอดซื้อขั้นต่ำ (บาท)','Minimum purchase (THB)'),('cap','เพดานส่วนลด (บาท)','Maximum discount (THB)')]:
                entry=self.entry(inner,self.ui(th,en));variable=tk.StringVar(value=f"{values[key]:g}")
                entry.configure(textvariable=variable);variable.trace_add('write',preview)
                block['variables'][key]=variable;block['entries'][key]=entry
            block['preview']=self.label(inner,'',11,bg='#F6F8FA',wraplength=290);block['preview'].pack(anchor='w',pady=(16,12))
            block['delete']=self.button(inner,self.ui('ลบบล็อก','Delete block'),lambda:remove(block),compact=True)
            block['delete'].pack(anchor='w');blocks.append(block);layout();preview()
        add_button=self.button(controls,self.ui('+ เพิ่มบล็อก','+ Add block'),add);add_button.pack(side='left')
        def save():
            try:
                updated=dict(config)
                updated['blocks']=[{k:float(v.get()) for k,v in block['variables'].items()} for block in blocks]
                updated['enabled']=enabled.get();loyalty.save_settings(self.user['id'],updated)
                self._admin('rewards')
            except (ValueError,TypeError,PermissionError) as exc:status.configure(text=str(exc))
        save_button=self.button(b,self.ui('บันทึกส่วนลด','Save discount'),save,dark=True);save_button.pack(anchor='w',pady=16)
        self.label(b,self.ui('บันทึกแล้วมีผลทันที หากเงื่อนไขวันนี้ถูกแก้หรือลบ ระบบจะสุ่มใหม่จากบล็อกที่บันทึก โดยไม่เปลี่ยนคำสั่งซื้อเดิม','Changes apply immediately. If the current conditions are edited or removed, a saved block is selected again. Existing orders stay unchanged.'),11,wraplength=1100).pack(anchor='w',pady=10)
        for values in config['blocks']:add(values)
        grid.bind('<Configure>',layout)
        enabled.trace_add('write',preview)
        self._discount_blocks_ui=dict(blocks=blocks,add=add_button,save=save_button,status=status,enabled=enabled,grid=grid)

    # จัดการรูปสินค้าตามสีและมุมภาพ
    def gallery_dialog(self,product):
        if not product:return
        win=tk.Toplevel(self);win.title('JPZ / PRODUCT PHOTOS');win.geometry('560x420');win.configure(bg='white')
        form=tk.Frame(win,bg='white');form.pack(fill='both',expand=True,padx=20,pady=16)
        self.label(form,product['name'],16,True).pack(anchor='w')
        self.label(form,self.ui('เลือกรูปจริงแยกตามสีและมุม รูปใหม่แทนที่มุมที่เลือกเท่านั้น','Upload a real photo per color and view. Only the selected view is replaced.'),9,wraplength=510,justify='left').pack(anchor='w',pady=10)
        colors=list(dict.fromkeys(v['color'] for v in db.variants(product['id'])))
        if not colors:return
        self.label(form,self.tr('color'),10,True).pack(anchor='w')
        color=select_field(form,values=colors,state='readonly');color.set(colors[0]);color.pack(fill='x',pady=6)
        labels={self.ui('นายแบบด้านหน้า','Model front'):'FRONT',self.ui('นายแบบด้านหลัง','Model back'):'BACK',self.ui('กางเกงเต็มตัว','Full garment'):'DETAIL',self.ui('รายละเอียดผ้า','Fabric detail'):'TEXTURE'}
        self.label(form,self.ui('มุมภาพ','View'),10,True).pack(anchor='w')
        view=select_field(form,values=list(labels),state='readonly');view.set(next(iter(labels)));view.pack(fill='x',pady=6)
        def upload():
            source=filedialog.askopenfilename(parent=win,filetypes=[('Images','*.png *.jpg *.jpeg *.webp')])
            if not source:return
            try:
                catalogue.set_image(self.user['id'],product['id'],color.get(),labels[view.get()],source)
                messagebox.showinfo('JPZ',self.tr('saved'),parent=win)
            except (ValueError,PermissionError,OSError,sqlite3.Error) as exc:messagebox.showerror('JPZ',str(exc),parent=win)
        self.button(form,self.ui('เลือกรูปและบันทึก','Choose photo and save'),upload,dark=True).pack(anchor='w',pady=14)


    # ตั้งค่าผู้รับเงิน ธนาคาร บัญชี และแสดงตัวอย่าง QR
    # J44 | ตั้งค่าการชำระเงิน / QR
    def admin_payment(self, b):
        b = self.scroll_content(b)
        self.heading(b, 'JPZ / ข้อมูลรับชำระ', 'JPZ / Payment details', 'เพิ่ม QR ที่ร้านใช้รับเงินจริง พร้อมชื่อผู้รับและรายละเอียดบัญชี', 'Upload the store payment QR and recipient details.')
        from support import service_setup
        self.button(b,self.ui('ตั้งค่าอีเมล · ใบเสร็จและ OTP','Email settings · receipts and OTP'),lambda:service_setup.show(self),dark=True).pack(anchor='w',pady=(4,16))
        cfg = receipts.payment_settings(); fields = {}
        if receipts.qr_path():self.file_picture(b,receipts.qr_path(),300,360)
        self.label(b,self.ui('ข้อมูลที่บันทึกแล้ว แก้ไขแล้วกดบันทึกอีกครั้งได้','Saved details. Edit and save again to update.'),12,True).pack(anchor='w',pady=10)
        for key, th, en in [('name','ชื่อผู้รับเงิน','Recipient name'),('bank','ธนาคาร / ช่องทางชำระ','Bank / payment method'),('account','บัญชี / PromptPay','Account / PromptPay'),('tax_id','เลขประจำตัวผู้เสียภาษีของร้าน (Tax ID) — 13 หลัก','Store Tax ID — 13 digits')]:
            entry = self.entry(b,self.ui(th,en));entry.insert(0,cfg.get(key,''));fields[key]=entry
        chosen = {'path':None}
        status = self.label(b,self.ui('มี QR รับชำระแล้ว','Payment QR configured') if receipts.qr_path() else self.ui('ยังไม่มี QR รับชำระ','No payment QR configured'),10,fg='#777777');status.pack(anchor='w',pady=12)
        def choose():
            path = filedialog.askopenfilename(filetypes=[('QR images','*.png *.jpg *.jpeg *.webp')])
            if path:
                chosen['path']=path;status.configure(text='ยังไม่บันทึก: '+Path(path).name)
                self.file_picture(b,path,280,320)
        self.button(b,self.ui('เลือกภาพ QR รับเงิน','Choose payment QR'),choose).pack(anchor='w',pady=8)
        def save():
            try:
                receipts.save_payment_settings(self.user['id'],fields['name'].get(),fields['bank'].get(),fields['account'].get(),chosen['path'],tax_id=fields['tax_id'].get())
                messagebox.showinfo('JPZ',self.ui('บันทึกข้อมูลรับชำระแล้ว','Payment details saved.'));self._admin('payment')
            except (ValueError,PermissionError,OSError,sqlite3.Error) as exc:messagebox.showerror('JPZ',str(exc))
        self.button(b,self.ui('บันทึก','Save'),save,dark=True).pack(anchor='w',pady=12)

    # แสดงรูปสินค้าและปรับสต็อกแยกสีและไซซ์ด้วยจำนวนหรือปุ่ม + −
    def quick_stock_dialog(self,product,selected_color=None):
        win=tk.Toplevel(self);win.title('แก้ไขสต็อก');win.geometry('760x800');form=self.scroll_content(win)
        self.label(form,product['name'],20,True).pack(anchor='w',padx=20,pady=12)
        picture_host=tk.Frame(form,bg='white');picture_host.pack(fill='x')
        variants=db.variants(product['id']);colors=sorted({v['color'] for v in variants})
        mapping={self.color_label(color):color for color in colors}
        choice=select_field(form,values=list(mapping),state='readonly');choice.set(self.color_label(selected_color) if selected_color in colors else next(iter(mapping)));choice.pack(fill='x',padx=20,pady=10)
        host=tk.Frame(form,bg='white');host.pack(fill='x',padx=20)
        def refresh(event=None):
            for child in host.winfo_children():child.destroy()
            color=mapping[choice.get()]
            for child in picture_host.winfo_children():child.destroy()
            self.product_picture(picture_host,product,color,'FRONT',height=220)
            for variant in db.variants(product['id']):
                if variant['color']!=color:continue
                row=tk.Frame(host,bg='white');row.pack(fill='x',pady=5)
                status='หมด' if variant['stock']==0 else str(variant['stock'])+' ตัว'
                self.label(row,db.size_label(variant['size'])+' · '+status,12,True,fg='#BB2020' if not variant['stock'] else '#111111').pack(side='left',padx=10)
                amount=tk.Entry(row,width=7,font=self.font(12));amount.insert(0,str(variant['stock']));amount.pack(side='left',padx=10)
                def update(mode,v=variant,e=amount):
                    try:
                        data.adjust_stock(self.user['id'],v['id'],int(e.get()) if mode=='set' else 1,mode);refresh()
                    except Exception as exc:messagebox.showerror('JPZ',str(exc),parent=win)
                self.button(row,'−',lambda fn=update:fn('remove'),compact=True).pack(side='left')
                self.button(row,'+',lambda fn=update:fn('add'),compact=True).pack(side='left')
                self.button(row,'บันทึกจำนวน',lambda fn=update:fn('set'),compact=True).pack(side='right')
        choice.bind('<<ComboboxSelected>>',refresh);refresh()
        def close():
            win.destroy()
            self._admin('products')
        win.protocol('WM_DELETE_WINDOW',close)
        self.button(form,'เพิ่มสี / ไซซ์',lambda:self.variant_dialog(product),compact=True).pack(pady=15)


    # รวมเมนูสินค้า สต็อก หมวดสินค้า และราคาเพิ่มตามไซซ์ไว้หน้าเดียว
    def admin_products(self,b):
        self.heading(b,'สินค้าและสต็อก','Products and stock')
        tabs=ttk.Notebook(b);tabs.pack(fill='both',expand=True)
        builders={};loaded=set()
        for th,en,handler in [('สินค้าและสต็อก','Products and stock',self.product_list),('ราคาตามไซซ์','Size pricing',self.size_prices),('คอลเลกชันหน้าแรก','Homepage collection',self.home_promotion_settings)]:
            frame=tk.Frame(tabs,bg='white');tabs.add(frame,text=self.ui(th,en));builders[str(frame)]=(frame,handler,th=='สินค้าและสต็อก')
        def build(event=None):
            selected=tabs.select()
            if selected in loaded or selected not in builders:return
            loaded.add(selected);frame,handler,plain=builders[selected]
            handler(frame if plain else self.scroll_content(frame))
        tabs.bind('<<NotebookTabChanged>>',build);build()

    # เลือกรูปและสินค้าที่จะโปรโมต โดยเก็บการตั้งค่าไว้ในฐานข้อมูลร้าน
    def home_promotion_settings(self,b):
        import uuid
        from PIL import Image,ImageTk,ImageOps
        from support import home_collection
        self.label(b,self.ui('02 / NEW DENIM · คอลเลกชันใหม่','02 / NEW DENIM · New collection'),20,True,wraplength=1100).pack(anchor='w',padx=24,pady=(20,8))
        self.label(b,self.ui('จัดการการ์ดสินค้าในแถวคอลเลกชันใหม่บนหน้าแรก ราคาใช้ราคาจริงของสินค้าที่เลือก','Manage the product cards in the homepage new collection row. Prices follow the selected products.'),12,wraplength=1100,justify='left').pack(anchor='w',padx=24,pady=(0,12))
        controls=tk.Frame(b,bg='white');controls.pack(fill='x',padx=24,pady=10)
        status=self.label(b,'',12,fg='#5D6975',wraplength=1100);status.pack(anchor='w',padx=24,pady=6)
        grid=tk.Frame(b,bg='white');grid.pack(fill='x',padx=18)
        products=db.products();options={f"{p['code']} / {p['name']}":p['id'] for p in products};blocks=[]
        def layout(event=None):
            width=event.width if event else grid.winfo_width();cols=max(1,min(3,width//390))
            for col in range(3):grid.columnconfigure(col,weight=1 if col<cols else 0,uniform='collection' if col<cols else '')
            for index,block in enumerate(blocks):
                block['frame'].grid(row=index//cols,column=index%cols,sticky='nsew',padx=6,pady=8)
                block['heading'].configure(text=self.ui(f'การ์ด {index+1:02d}',f'Card {index+1:02d}'))
        def remove(block):
            blocks.remove(block);block['frame'].destroy();layout();status.configure(text=self.ui('แก้ไขแล้ว กดบันทึกเพื่อนำไปใช้','Changed. Save to apply.'))
        def add(config=None,parent=None,draft=False,image=None):
            if not products:return status.configure(text=self.ui('เพิ่มสินค้าในร้านก่อน','Add a store product first.'))
            config=dict(config or dict(product_id=products[0]['id'],title='',photo=''))
            cell=tk.Frame(parent if parent is not None else grid,bg='#F5F7F9',highlightbackground=BORDER,highlightthickness=1)
            frame=tk.Frame(cell,bg='#F5F7F9');frame.pack(fill='both',expand=True,padx=16,pady=16)
            heading=self.label(frame,'',16,True,bg='#F5F7F9');heading.pack(anchor='w')
            preview=tk.Label(frame,bg='#E9EEF3');preview.pack(pady=10)
            selected=tk.StringVar(value=next((name for name,pid in options.items() if pid==config['product_id']),''))
            self.label(frame,self.ui('สินค้าเมื่อกดดูสินค้า','Product to open'),11,True,bg='#F5F7F9').pack(anchor='w',pady=(8,4))
            select=select_field(frame,textvariable=selected,values=list(options),state='readonly');select.pack(fill='x')
            title=self.entry(frame,self.ui('ชื่อบนการ์ด (เว้นว่างใช้ชื่อสินค้า)','Card title (blank uses product name)'));title.insert(0,config.get('title',''))
            block=dict(frame=cell,heading=heading,config=config,image=image,selected=selected,select=select,title=title,preview=preview)
            feedback=status
            if draft:
                feedback=self.label(frame,'',10,bg='#F5F7F9',fg='#5D6975',wraplength=440,justify='left');feedback.pack(anchor='w',pady=4)
            price=self.label(frame,'',11,bg='#F5F7F9',wraplength=340);price.pack(anchor='w',pady=8)
            def render(event=None):
                block['config']['product_id']=options.get(selected.get())
                picture=block['image'] if block['image'] is not None else home_collection.picture(block['config'])
                if picture is not None:
                    photo=ImageTk.PhotoImage(ImageOps.pad(picture.convert('RGB'),(205,250),color='#E9EEF3',method=Image.Resampling.LANCZOS),master=self)
                    preview.configure(image=photo,text='');preview._image=photo
                else:preview.configure(image='',text=self.ui('ยังไม่มีรูป','No image'),width=26,height=8)
                product=db.product(block['config']['product_id'])
                price.configure(text=(f"฿{product['price']:,.2f} · "+self.ui('ก่อน VAT ','Before VAT ')+f"฿{db.vat_breakdown(product['price'])['before_vat']:,.2f}") if product else self.ui('เลือกสินค้า','Select a product'))
            def choose():
                path=filedialog.askopenfilename(parent=cell.winfo_toplevel(),filetypes=[('JPG / PNG','*.jpg *.jpeg *.png')])
                if not path:return
                try:
                    with Image.open(path) as image:
                        image=ImageOps.exif_transpose(image).convert('RGB');image.thumbnail((1600,1600));block['image']=image.copy()
                    render();feedback.configure(text=self.ui('เลือกรูปแล้ว กดบันทึก','Picture selected. Save to apply.'))
                except (OSError,ValueError) as exc:feedback.configure(text=str(exc),fg='#BB2020')
            def use_product():block['image']=None;block['config']['photo']='';render()
            actions=tk.Frame(frame,bg='#F5F7F9');actions.pack(fill='x',pady=8)
            self.button(actions,self.ui('เลือกรูป','Choose image'),choose,compact=True).pack(side='left')
            self.button(actions,self.ui('ใช้รูปสินค้า','Use product image'),use_product,compact=True).pack(side='left',padx=6)
            delete=None
            if not draft:
                delete=self.button(frame,self.ui('ลบการ์ด','Remove card'),lambda:remove(block),compact=True);delete.pack(anchor='w',pady=8)
            block.update(choose=choose,use_product=use_product,remove=delete,render=render,price=price)
            select.bind('<<ComboboxSelected>>',render)
            if draft:
                heading.configure(text=self.ui('การ์ดใหม่','New card'));cell.pack(fill='both',expand=True,padx=14,pady=8)
            else:blocks.append(block)
            render()
            if not draft:layout()
            return block
        def save():
            created=[]
            try:
                cards=[]
                for block in blocks:
                    config=dict(block['config']);config['product_id']=options.get(block['selected'].get());config['title']=block['title'].get().strip()
                    if block['image'] is not None:
                        folder=db.BASE_DIR/'user_uploads';folder.mkdir(exist_ok=True)
                        path=folder/f'collection_{uuid.uuid4().hex}.png';block['image'].save(path);created.append(path);config['photo']=str(path.relative_to(db.BASE_DIR))
                    cards.append(config)
                saved=home_collection.save(self.user['id'],cards)
                for block,config in zip(blocks,saved):block['config']=config;block['image']=None
                status.configure(text=self.ui('บันทึกแล้ว การ์ดจะแสดงในส่วน 02 / NEW DENIM','Saved. Cards appear in 02 / NEW DENIM.'),fg='#24633D')
            except (OSError,ValueError,PermissionError,sqlite3.Error) as exc:
                for path in created:path.unlink(missing_ok=True)
                status.configure(text=str(exc),fg='#BB2020')
        draft_state={}
        def open_draft():
            existing=draft_state.get('window')
            if existing is not None and existing.winfo_exists():
                existing.lift();existing.focus_set();return
            if not products:return status.configure(text=self.ui('เพิ่มสินค้าในร้านก่อน','Add a store product first.'))
            win=tk.Toplevel(self);win.title(self.ui('เพิ่มการ์ดคอลเลกชัน','Add collection card'));win.configure(bg='white');win.transient(self)
            width=min(620,self.winfo_screenwidth()-70);height=min(900,self.winfo_screenheight()-100)
            win.geometry(f'{width}x{height}+{max(0,(self.winfo_screenwidth()-width)//2)}+{max(0,(self.winfo_screenheight()-height)//2-20)}')
            win.minsize(min(480,width),min(500,height))
            footer=tk.Frame(win,bg='white');footer.pack(side='bottom',fill='x',padx=18,pady=12)
            notice=self.label(win,self.ui('แก้ข้อมูลก่อนยืนยัน จากนั้นกดบันทึกคอลเลกชันเพื่อนำขึ้นหน้าแรก','Edit before adding. Save the collection afterward to publish on the homepage.'),10,fg='#5D6975',wraplength=540,justify='left')
            notice.pack(side='bottom',fill='x',padx=18,pady=4)
            content=self.scroll_content(win);draft=add(parent=content,draft=True);accepted=[False]
            def cancel():
                try:win.grab_release();win.destroy()
                except tk.TclError:pass
                draft_state.clear()
            def confirm():
                if accepted[0] or not win.winfo_exists():return
                pid=options.get(draft['selected'].get());product=db.product(pid) if pid else None
                title=draft['title'].get().strip()
                if not product or not product.get('active',1):
                    notice.configure(text=self.ui('กรุณาเลือกสินค้าที่เปิดขาย','Select an active product.'),fg='#BB2020');return
                if len(title)>120:
                    notice.configure(text=self.ui('ชื่อบนการ์ดยาวเกิน 120 ตัว','Card title exceeds 120 characters.'),fg='#BB2020');return
                config=dict(draft['config'],product_id=pid,title=title)
                accepted[0]=True;confirm_button.configure(state='disabled')
                add(config,image=draft['image'])
                cancel();status.configure(text=self.ui('เพิ่มการ์ดแล้ว กดบันทึกคอลเลกชันเพื่อนำขึ้นหน้าแรก','Card added. Save the collection to publish on the homepage.'),fg='#24633D')
            cancel_button=self.button(footer,self.ui('ยกเลิก','Cancel'),cancel);cancel_button.pack(side='left')
            confirm_button=self.button(footer,self.ui('ยืนยันเพิ่มการ์ด','Add this card'),confirm,dark=True);confirm_button.pack(side='right')
            draft_state.update(window=win,block=draft,confirm=confirm_button,cancel=cancel_button,notice=notice)
            win.protocol('WM_DELETE_WINDOW',cancel);win.bind('<Escape>',lambda event:cancel());win.grab_set();win.focus_set()
        add_button=self.button(controls,self.ui('+ เพิ่มการ์ดสินค้า','+ Add product card'),open_draft);add_button.pack(side='left',padx=(0,10))
        save_button=self.button(controls,self.ui('บันทึกคอลเลกชัน','Save collection'),save,dark=True);save_button.pack(side='left')
        grid.bind('<Configure>',layout)
        for config in home_collection.settings():add(config)
        self._home_collection_admin_ui=dict(blocks=blocks,add=open_draft,add_button=add_button,draft=draft_state,save=save_button,status=status,options=options)

    # รองรับการเรียกเมนูสต็อกเดิมโดยใช้รายการรวมหนึ่งแถวต่อรุ่น
    def grouped_inventory(self,b):
        return self.product_list(b)

    # ตั้งค่าราคาที่เพิ่มสำหรับไซซ์แต่ละระดับ
    # J65 | ตั้งราคาเพิ่มตามไซซ์
    def size_prices(self,b):
        self.label(b,'ราคาเพิ่มตามไซซ์ (บาทต่อชิ้น) ราคาหน้าสินค้าและตะกร้าคำนวณจากข้อมูลนี้',12,wraplength=850).pack(anchor='w',pady=15)
        c=db.conn();rows=c.execute('SELECT * FROM size_prices ORDER BY size').fetchall();c.close();fields={}
        for row in rows:
            entry=self.entry(b,db.size_label(row['size']));entry.insert(0,str(row['surcharge']));fields[row['size']]=entry
        def save():
            try:
                values={k:float(e.get()) for k,e in fields.items()}
                if any(not data.math.isfinite(v) or v<0 for v in values.values()):raise ValueError('ราคาเพิ่มต้องไม่ติดลบ')
                with data.transaction(self.user['id']) as c:
                    for key,value in values.items():c.execute('UPDATE size_prices SET surcharge=? WHERE size=?',(value,key))
                messagebox.showinfo('JPZ','บันทึกราคาแล้ว')
            except Exception as exc:messagebox.showerror('JPZ',str(exc))
        self.button(b,'บันทึกราคา',save,dark=True).pack(anchor='w',pady=12)

    # ตั้งค่าช่องทางติดต่อและอัปโหลดรูปเจ้าของร้าน พร้อมบันทึกลงฐานข้อมูล
    # J45 | ตั้งค่าช่องทางติดต่อร้าน
    def admin_contact(self,b):
        import json,uuid
        from PIL import Image,ImageOps,ImageTk
        from support.portraits import owner_portrait,read_photo
        from support.avatar_editor import AvatarEditor
        b=self.scroll_content(b);self.heading(b,'ช่องทางติดต่อร้าน','Store contact')
        c=db.conn();record=c.execute("SELECT value FROM shop_metadata WHERE key='contact'").fetchone();c.close()
        values=json.loads(record['value']) if record else {'email':'supaza2549@gmail.com'}
        self.label(b,self.ui('รูปเจ้าของร้าน','Store owner photo'),17,True).pack(anchor='w',pady=(12,8))
        self.label(b,self.ui('เลือกรูปแล้วลากและซูมให้พอดีกรอบ ก่อนบันทึกช่องทางติดต่อ','Choose a photo, drag and zoom to fit the frame, then save store contact.'),11,fg='#5D6975',wraplength=850).pack(anchor='w',pady=(0,12))
        photo={'path':values.get('photo',''),'source':values.get('photo_source',''),'crop':values.get('photo_crop',{})}
        preview=tk.Label(b,bg='white');preview.pack(anchor='w',pady=8)
        def update_preview():
            image=ImageTk.PhotoImage(owner_portrait(db.BASE_DIR,photo['path'],(240,280)),master=self)
            preview.configure(image=image);preview._image=image
        update_preview()
        status=self.label(b,self.ui('รูปที่บันทึกไว้','Saved photo') if photo['path'] else self.ui('ยังไม่ได้เพิ่มรูปเจ้าของร้าน','No owner photo yet'),11,fg='#5D6975');status.pack(anchor='w',pady=6)
        def accept_crop(cropped,original,settings):
            folder=Path(db.BASE_DIR)/'user_uploads';folder.mkdir(exist_ok=True)
            token=uuid.uuid4().hex;dest=folder/f'contact_{token}.png';source=folder/f'contact_{token}_source.png'
            try:
                original=original.copy();original.thumbnail((2048,2048));original.save(source);cropped.save(dest)
            except Exception:
                source.unlink(missing_ok=True);dest.unlink(missing_ok=True);raise
            photo.update(path=str(dest.relative_to(db.BASE_DIR)),source=str(source.relative_to(db.BASE_DIR)),crop=settings)
            update_preview();status.configure(text=self.ui('จัดรูปแล้ว กดบันทึกช่องทางติดต่อเพื่อแสดงหน้าร้าน','Photo adjusted. Save store contact to publish it.'))
        def open_editor(image,settings=None):
            self._owner_photo_editor=AvatarEditor(self,image,accept_crop,settings,portrait=True)
        def adjust():
            image=read_photo(db.BASE_DIR,photo['source']) or read_photo(db.BASE_DIR,photo['path'])
            if image is None:return choose()
            open_editor(image,photo['crop'] if photo['source'] else None)
        def choose():
            path=filedialog.askopenfilename(filetypes=[('JPG / PNG','*.jpg *.jpeg *.png')])
            if not path:return
            try:
                with Image.open(path) as image:
                    image=ImageOps.exif_transpose(image).convert('RGB')
                open_editor(image)
            except (OSError,ValueError):messagebox.showerror('JPZ','เลือกไฟล์รูปภาพ JPG หรือ PNG ที่เปิดได้')
        actions=tk.Frame(b,bg='white');actions.pack(anchor='w',pady=12)
        self.button(actions,self.ui('เพิ่ม / เปลี่ยนรูปเจ้าของร้าน','Change owner photo'),choose).pack(side='left')
        adjust_button=self.button(actions,self.ui('จัดตำแหน่งรูป','Adjust photo'),adjust);adjust_button.pack(side='left',padx=10)
        def camera():
            from support.camera import CameraDialog
            existing=getattr(self,'_owner_camera',None)
            if existing is not None and existing.winfo_exists():existing.lift();return
            self._owner_camera=CameraDialog(self,open_editor)
        self.button(actions,self.ui('เปิดกล้อง','Open camera'),camera).pack(side='left',padx=10)
        preview.bind('<Button-1>',lambda event:adjust());preview.configure(cursor='hand2')
        fields={}
        for key,title in [('phone','เบอร์โทรศัพท์'),('email','อีเมล'),('facebook','ชื่อ Facebook'),('instagram','ชื่อ Instagram'),('line','LINE ID')]:
            entry=self.entry(b,title);entry.insert(0,values.get(key,''));fields[key]=entry
        def save():
            try:
                updated=dict(values);updated.update({k:e.get().strip() for k,e in fields.items()});updated.update(photo=photo['path'],photo_source=photo['source'],photo_crop=photo['crop'])
                if updated['phone']:db.validate_phone(updated['phone'])
                with data.transaction(self.user['id']) as c:c.execute("INSERT INTO shop_metadata VALUES('contact',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(json.dumps(updated),))
                status.configure(text='บันทึกรูปเจ้าของร้านแล้ว' if photo['path'] else 'ยังไม่ได้เพิ่มรูปเจ้าของร้าน')
                messagebox.showinfo('JPZ','บันทึกช่องทางติดต่อและรูปเจ้าของร้านแล้ว')
            except (ValueError,OSError,sqlite3.Error) as exc:messagebox.showerror('JPZ',str(exc))
        save_button=self.button(b,self.ui('บันทึกช่องทางติดต่อ','Save store contact'),save,dark=True);save_button.pack(anchor='w',pady=12)
        self._contact_photo_ui=dict(photo=photo,preview=preview,adjust=adjust_button,save=save_button,open_editor=open_editor,fields=fields)
