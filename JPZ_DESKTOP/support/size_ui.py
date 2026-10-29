from support.theme import check_field
from support.theme import select_field
import tkinter as tk
from tkinter import ttk,messagebox
from support import sizing
class SizeMixin:
    # เปิดตารางไซซ์เต็มจอ เน้นไซซ์ที่แนะนำ และตรึงปุ่มปิดไว้ด้านล่าง
    # J22 | ตารางไซซ์
    def size_chart(self,p):
        win=tk.Toplevel(self);win.title('JPZ / SIZE GUIDE');win.configure(bg='white');win.attributes('-fullscreen',True)
        footer=tk.Frame(win,bg='white');footer.pack(side='bottom',fill='x',padx=24,pady=12)
        self.label(footer,self.ui('ขนาดตามตารางไซซ์ของรุ่น','Dimensions from the model’s size chart'),12,fg='#777777').pack(side='left')
        self.button(footer,self.ui('ปิดตารางไซซ์','Close size chart'),win.destroy,dark=True).pack(side='right')
        def reveal_bar(event):
            win.attributes('-fullscreen',False);win.state('zoomed');return 'break'
        win.bind('<Escape>',reveal_bar)
        canvas=tk.Canvas(win,bg='white',highlightthickness=0,yscrollincrement=24)
        scroll=ttk.Scrollbar(win,orient='vertical',command=canvas.yview);scroll.pack(side='right',fill='y')
        canvas.configure(yscrollcommand=scroll.set);canvas.pack(fill='both',expand=True)
        body=tk.Frame(canvas,bg='white');item=canvas.create_window((0,0),window=body,anchor='nw')
        body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width))
        win.bind('<MouseWheel>',lambda e:(canvas.yview_scroll(int(-e.delta/120),'units'),'break')[-1])
        self.label(body,p['name'],30,True).pack(anchor='w',padx=28,pady=(24,12))
        self.label(body,self.ui('ตารางขนาดกางเกง · รอบเอว / สะโพก / ต้นขา / ปลายขาเป็นรอบวง','Garment size chart · waist / hip / thigh / opening are circumferences'),14,wraplength=1500).pack(anchor='w',padx=28,pady=(0,12))
        unit=tk.StringVar(value='IN');bar=tk.Frame(body,bg='white');bar.pack(fill='x',padx=28)
        style=ttk.Style(win);style.configure('JPZ.Size.Treeview',font=self.font(14),rowheight=38)
        style.configure('JPZ.Size.Treeview.Heading',font=self.font(12,True),padding=(8,12))
        table=ttk.Treeview(body,columns=('size',*sizing.FIELDS),show='headings',height=10,style='JPZ.Size.Treeview')
        names=[self.ui('ไซซ์','Size'),self.ui('A รอบเอว','A Waist'),self.ui('B รอบสะโพก','B Hip'),self.ui('C รอบต้นขา','C Thigh'),self.ui('D เป้าหน้า','D Front rise'),self.ui('E ขาด้านใน','E Inseam'),self.ui('F รอบปลายขา','F Opening')]
        for key,name in zip(('size',*sizing.FIELDS),names):table.heading(key,text=name);table.column(key,width=160,minwidth=100,anchor='center')
        table.tag_configure('selected',background='#DFE7ED')
        selected=p.get('recommended_size',self.product_state.get(p['id'],{}).get('size',32))
        self.label(bar,self.ui('ไซซ์ที่เลือก: ','Selected size: ')+__import__('db').size_label(selected),13,True,fg='#243E55').pack(side='right')
        unit_buttons={}
        def refresh():
            table.delete(*table.get_children());factor=2.54 if unit.get()=='CM' else 1
            suffix=self.ui(' (ซม.)',' (cm)') if unit.get()=='CM' else self.ui(' (นิ้ว)',' (in)')
            for key,name in zip(sizing.FIELDS,names[1:]):table.heading(key,text=name+suffix)
            for r in sizing.rows(p['id']):
                table.insert('','end',iid=str(r['size']),values=(__import__('db').size_label(r['size']),*[f'{r[k]*factor:.1f}' for k in sizing.FIELDS]),tags=('selected',) if r['size']==selected else ())
            for value,button in unit_buttons.items():
                chosen=unit.get()==value
                button.configure(fg_color='#243E55' if chosen else '#F8F6F0',text_color='white' if chosen else '#243E55',border_color='#B8A88E' if chosen else '#DDD6C8',border_width=1)
        from support.theme import ctk
        switch=ctk.CTkFrame(bar,fg_color='#F8F6F0',corner_radius=12,border_width=1,border_color='#DDD6C8');switch.pack(side='left',pady=10)
        def choose(value):unit.set(value);refresh()
        for value,label in [('IN',self.ui('นิ้ว / IN','Inches / IN')),('CM',self.ui('เซนติเมตร / CM','Centimeters / CM'))]:
            button=self.button(switch,label,lambda v=value:choose(v),compact=True)
            button.configure(height=40,corner_radius=9);button.pack(side='left',padx=4,pady=4);unit_buttons[value]=button
        table.pack(fill='x',padx=28,pady=12);refresh()
        self.measurement_art(body)
        self.label(body,self.ui('วางกางเกงราบ ติดกระดุม ไม่ดึงผ้า · A เอว B สะโพก C ต้นขา F ปลายขา: วัดความกว้างแล้วคูณ 2 · D เป้าหน้า E ขาด้านใน: วัดตามตะเข็บ','Lay flat, fasten waist, do not stretch. A waist, B hip, C thigh, F opening: flat width × 2. D front rise and E inseam: measure along the seam.'),12,wraplength=1400).pack(padx=28,pady=18)
        self._size_chart_ui={'window':win,'table':table,'unit':unit,'refresh':refresh,'selected':selected,'unit_buttons':unit_buttons}
    # แยกปุ่มบันทึกออกจากพื้นที่เลื่อน เพื่อบันทึกขนาดที่วัดจริงได้ทุกขนาดจอ
    def admin_size_dialog(self,p):
        win=tk.Toplevel(self);win.title('JPZ / SIZE MEASUREMENTS');win.geometry('700x760');win.configure(bg='white')
        footer=tk.Frame(win,bg='white');footer.pack(side='bottom',fill='x',padx=20,pady=12)
        status=self.label(footer,'',11,fg='#247450',wraplength=480);status.pack(anchor='w',pady=(0,8))
        body=self.scroll_content(win)
        self.label(body,p['name'],19,True).pack(anchor='w',padx=20,pady=15)
        self.label(body,self.ui('วัดกางเกงจริงแยกทุกไซซ์ แล้วบันทึกเป็นหน่วยนิ้ว','Measure the actual garment for each size, then record inches.'),12,wraplength=580).pack(anchor='w',padx=20)
        self.label(body,self.ui('วางราบ ติดกระดุม ไม่ดึงผ้า · เอว สะโพก ต้นขา และปลายขา: ความกว้าง × 2\nเป้าหน้าและขาด้านใน: วัดตามตะเข็บ ไม่คูณ 2','Lay flat, fasten waist, do not stretch. Waist / hip / thigh / opening: width × 2.\nFront rise / inseam: measure along the seam, without doubling.'),11,fg='#777777',wraplength=580).pack(anchor='w',padx=20,pady=12)
        labels=[__import__('db').size_label(r['size']) for r in sizing.rows(p['id'])]
        size=tk.StringVar(value='L' if 'L' in labels else labels[0] if labels else '')
        picker=select_field(body,textvariable=size,values=labels,state='readonly');picker.pack(fill='x',padx=20,pady=10)
        fields=tk.Frame(body,bg='white');fields.pack(fill='x',padx=20)
        entries={k:self.entry(fields,self.tr('opening' if k=='leg_opening' else k)) for k in sizing.FIELDS}
        estimated=tk.BooleanVar(value=True)
        check_field(body,text=self.ui('ข้อมูลประมาณการ (เอาเครื่องหมายออกเมื่อวัดจริงแล้ว)','Estimated (uncheck only after measuring)'),variable=estimated,bg='white',font=self.font(11)).pack(anchor='w',padx=20,pady=12)
        def load(*args):
            r=sizing.for_size(p,__import__('db').size_key(size.get()))
            for k,e in entries.items():e.delete(0,'end');e.insert(0,str(r[k]))
            estimated.set(bool(r['estimated']));status.configure(text='')
        def save():
            try:
                sizing.save(self.user['id'],p['id'],__import__('db').size_key(size.get()),{k:e.get() for k,e in entries.items()},estimated.get())
                status.configure(text=self.ui('บันทึกแล้ว · คำแนะนำจะใช้ขนาดนี้ในการค้นหาครั้งถัดไป','Saved · the next fit search will use these dimensions.'),fg='#247450')
            except (ValueError,PermissionError) as exc:status.configure(text=str(exc),fg='#BB2020')
        picker.bind('<<ComboboxSelected>>',load)
        if labels:load()
        self.button(footer,self.ui('ปิด','Close'),win.destroy).pack(side='left')
        save_button=self.button(footer,self.tr('save'),save,dark=True);save_button.pack(side='right')
        self._size_measurements_ui={'window':win,'size':size,'picker':picker,'entries':entries,'estimated':estimated,'save':save_button,'status':status}

    # กรอกสัดส่วนและจำนวนของไซซ์ที่เลือก เก็บเป็นร่างจนกดบันทึกสินค้า
    # J66 | กรอกสัดส่วนและจำนวนแยกไซซ์
    def product_size_draft_dialog(self,parent,name,size,values,estimated,on_save,stock=None):
        import math
        import db
        win=tk.Toplevel(parent);win.title('JPZ / '+db.size_label(size)+f' / W{size}');win.geometry('700x790');win.minsize(520,500);win.configure(bg='white');win.transient(parent);win.grab_set()
        footer=tk.Frame(win,bg='white');footer.pack(side='bottom',fill='x',padx=20,pady=12)
        status=self.label(footer,'',11,fg='#BB2020',wraplength=600);status.pack(anchor='w',pady=6)
        body=self.scroll_content(win)
        title=self.ui('กำลังกรอกสัดส่วนไซซ์ ','Editing measurements for ')+db.size_label(size)+f' / W{size}'
        self.label(body,title,21,True,fg='#243E55',wraplength=620).pack(anchor='w',padx=20,pady=(20,10))
        self.label(body,name,13,wraplength=620).pack(anchor='w',padx=20,pady=(0,12))
        self.label(body,self.ui('ขนาดกางเกงจริง หน่วยนิ้ว ไม่ใช่สัดส่วนร่างกาย\nเอว สะโพก ต้นขา และปลายขาใช้รอบวง · เป้าและขาด้านในใช้ความยาว','Actual garment measurements in inches, not body measurements.\nWaist, hip, thigh and opening are circumferences; rise and inseam are lengths.'),11,fg='#5D6975',wraplength=620,justify='left').pack(anchor='w',padx=20,pady=(0,12))
        fields=tk.Frame(body,bg='white');fields.pack(fill='x',padx=20);entries={}
        for key,th,en in [('waist','A รอบเอว (นิ้ว)','A Waist (in)'),('hip','B รอบสะโพก (นิ้ว)','B Hip (in)'),('thigh','C รอบต้นขา (นิ้ว)','C Thigh (in)'),('rise','D เป้าหน้า (นิ้ว)','D Front rise (in)'),('inseam','E ขาด้านใน (นิ้ว)','E Inseam (in)'),('leg_opening','F รอบปลายขา (นิ้ว)','F Opening (in)')]:
            entry=self.entry(fields,self.ui(th,en));entry.insert(0,str(values[key]));entries[key]=entry
        quantity=None
        if stock is not None:
            quantity=self.entry(fields,self.ui('จำนวนสินค้าไซซ์นี้','Stock for this size'));quantity.insert(0,str(stock))
        approximate=tk.BooleanVar(value=estimated)
        check_field(body,text=self.ui('เป็นค่าประมาณ (เอาเครื่องหมายออกเมื่อวัดกางเกงจริงแล้ว)','Estimated (uncheck after measuring the actual garment)'),variable=approximate,bg='white').pack(anchor='w',padx=20,pady=14)
        self.label(body,self.ui('กดเก็บข้อมูลไซซ์นี้ แล้วกดบันทึกสินค้าและรูปในหน้าหลักเพื่อบันทึกทั้งหมด','Apply this size, then save the product and photos in the main form to save everything.'),11,wraplength=620,justify='left').pack(anchor='w',padx=20,pady=10)
        def apply():
            try:
                row={k:float(e.get()) for k,e in entries.items()}
                if not all(math.isfinite(v) and 0<v<=100 for v in row.values()):raise ValueError(self.ui('ขนาดต้องมากกว่า 0 และไม่เกิน 100 นิ้ว','Measurements must be positive and at most 100 inches.'))
                qty=int(quantity.get()) if quantity is not None else None
                if qty is not None and qty<0:raise ValueError(self.ui('จำนวนสินค้าต้องเป็นจำนวนเต็มตั้งแต่ 0 ขึ้นไป','Stock must be a non-negative integer.'))
                row['estimated']=approximate.get();on_save(size,row,qty);win.destroy()
            except ValueError as exc:status.configure(text=self.ui('ตรวจข้อมูลอีกครั้ง: ','Check the values: ')+str(exc))
        self.button(footer,self.ui('ยกเลิก','Cancel'),win.destroy).pack(side='left')
        save=self.button(footer,self.ui('เก็บข้อมูลไซซ์นี้','Apply this size'),apply,dark=True);save.pack(side='right')
        win.bind('<Escape>',lambda e:win.destroy())
        self._size_draft_ui=dict(window=win,size=size,entries=entries,estimated=approximate,stock=quantity,save=save,status=status)
        return win
