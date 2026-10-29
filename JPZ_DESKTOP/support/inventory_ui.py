"""หน้าสินค้าและสต็อก ประกอบด้วยรายชื่อสินค้า ฟอร์มแก้ไข ไซซ์ และยอดขาย"""
import tkinter as tk
import sqlite3
import threading,queue
from tkinter import ttk,messagebox,simpledialog
from PIL import ImageOps
import db
from support import admin_data as data,gallery,product_promotions,inventory,catalogue
from support import product_colors
from support.theme import field,card,select_field,check_field
from support.language import option_name

# J41 | จัดการสินค้าและสต็อก
def show(app,parent):
    state={'product':None,'baseline':{},'dirty':False,'loading':False};cards={};entries={};sizes={}
    card_colors=getattr(app,'_inventory_card_colors',{});app._inventory_card_colors=card_colors
    bar=tk.Frame(parent,bg='white');bar.pack(fill='x',pady=10)
    search=tk.StringVar();query=field(bar);query.configure(textvariable=search,width=280);query.pack(side='left')
    app.label(bar,app.ui('ค้นหาชื่อ / รหัสสินค้า','Search name / SKU'),11,fg='#5D6975').pack(side='left',padx=12)
    app.button(bar,app.ui('+ เพิ่มสินค้า','+ New product'),lambda:app.product_dialog(),dark=True,compact=True).pack(side='right')
    split=tk.PanedWindow(parent,orient='horizontal',bg='#E1E7ED',sashwidth=7);split.pack(fill='both',expand=True)
    left=tk.Frame(split,bg='white',width=340);right=tk.Frame(split,bg='white');split.add(left,width=340,minsize=280);split.add(right,minsize=460)
    pagination={'page':getattr(app,'_inventory_list_page',0),'term':None,'pages':1}
    paging=tk.Frame(left,bg='white');paging.pack(side='bottom',fill='x',padx=8,pady=8)
    page_note=app.label(paging,'',10,fg='#5D6975');page_note.pack(side='top',pady=(0,5))
    def change_page(delta):
        target=pagination['page']+delta
        if 0<=target<pagination['pages']:
            pagination['page']=target;app._inventory_list_page=target;refresh_list()
    previous=app.button(paging,'‹',lambda:change_page(-1),compact=True);previous.pack(side='left')
    following=app.button(paging,'›',lambda:change_page(1),compact=True);following.pack(side='right')
    listing=app.scroll_content(left);form=app.scroll_content(right)
    header=app.label(form,app.ui('เลือกสินค้า','Select a product'),21,True,wraplength=900,justify='left');header.pack(anchor='w',padx=20,pady=(16,12))
    fields=tk.Frame(form,bg='white');fields.pack(fill='x',padx=20)
    fits={app.fit_label(key):key for key in data.FITS};styles={option_name(app.lang,key):key for key in data.STYLES};field_holders=[];field_widgets={}
    def dirty(*args):
        if not state['loading']:state['dirty']=True
    for index,(key,th,en) in enumerate([('name','ชื่อสินค้า','Product name'),('code','รหัสสินค้า','SKU'),('price','ราคา (รวม VAT แล้ว)','Price (VAT included)'),('fit','ทรงยีนส์','Fit'),('style','สไตล์','Style')]):
        holder=tk.Frame(fields,bg='white');holder.grid(row=index//3,column=index%3,sticky='ew',padx=(0,12),pady=6);fields.columnconfigure(index%3,weight=1)
        field_holders.append(holder)
        app.label(holder,app.ui(th,en),11,True).pack(anchor='w',pady=(0,5))
        var=tk.StringVar();var.trace_add('write',dirty)
        widget=select_field(holder,textvariable=var,values=list(fits if key=='fit' else styles),state='readonly',font=app.font(11)) if key in ('fit','style') else field(holder)
        if key not in ('fit','style'):widget.configure(textvariable=var,width=120)
        widget.pack(fill='x');entries[key]=var;field_widgets[key]=widget
    def fields_layout(event):
        cols=3 if event.width>=760 else 2 if event.width>=420 else 1
        for col in range(3):fields.columnconfigure(col,weight=int(col<cols))
        for index,holder in enumerate(field_holders):holder.grid_configure(row=index//cols,column=index%cols)
    fields.bind('<Configure>',fields_layout)
    offers_shell=card(form,color='#F1F3F5',radius=16);offers_shell.configure(border_color='#DAE0E6');offers_shell.pack(fill='x',padx=20,pady=18)
    offers_title=app.label(offers_shell,app.ui('โปรโมชั่นสินค้านี้','This product promotion'),14,True,bg='#F1F3F5',fg='#243E55');offers_title.pack(anchor='w',padx=20,pady=(16,10))
    offers=tk.Frame(offers_shell,bg='#F1F3F5');offers.pack(fill='x',padx=20,pady=(0,18))
    enabled=tk.BooleanVar();enabled.trace_add('write',dirty)
    offer_enabled=check_field(offers,text=app.ui('เปิดโปรโมชั่น','Enable offer'),variable=enabled,font=app.font(11));offer_enabled.grid(row=0,column=0,sticky='w',padx=(0,10))
    offer_names={app.ui('ลดเป็นเปอร์เซ็นต์','Percentage discount'):'percent',app.ui('ตั้งราคาพิเศษ','Special base price'):'price'}
    offer_kind=tk.StringVar();offer_kind.trace_add('write',dirty);kind=select_field(offers,textvariable=offer_kind,values=list(offer_names),state='readonly',font=app.font(11),width=18);kind.grid(row=0,column=1,sticky='ew',padx=(0,12))
    offer_value=tk.StringVar();offer_value.trace_add('write',dirty);value=field(offers);value.configure(textvariable=offer_value,width=110);value.grid(row=0,column=2,sticky='ew')
    offers.columnconfigure(1,weight=1)
    offers_copy=app.label(offers,app.ui('เลือกลดเป็นเปอร์เซ็นต์หรือตั้งราคาพิเศษ · ใช้ส่วนลดที่คุ้มกว่า ไม่ลดซ้อน','Choose a percentage or special price. The better discount applies without stacking.'),11,bg='#F1F3F5',fg='#5D6975',wraplength=800,justify='left');offers_copy.grid(row=1,column=0,columnspan=3,sticky='w',pady=(12,0))
    def offers_layout(event):
        narrow=event.width<650
        offer_enabled.grid_configure(row=0,column=0,columnspan=2 if narrow else 1)
        kind.configure(width=12 if narrow else 18);kind.grid_configure(row=1 if narrow else 0,column=0 if narrow else 1)
        value.grid_configure(row=1 if narrow else 0,column=1 if narrow else 2)
        for column in range(3):offers.columnconfigure(column,weight=int(column==(0 if narrow else 1)))
        offers_copy.configure(wraplength=max(220,event.width-36));offers_copy.grid_configure(row=2 if narrow else 1,columnspan=2 if narrow else 3)
    offers.bind('<Configure>',offers_layout)
    actions=tk.Frame(form,bg='white');actions.pack(fill='x',padx=20,pady=(0,8))
    status=app.label(form,'',12,fg='#5D6975',wraplength=850,justify='left');status.pack(anchor='w',padx=20,pady=5)
    color_bar=tk.Frame(form,bg='white');color_bar.pack(fill='x',padx=20,pady=10)
    app.label(color_bar,app.ui('สต็อกแยกสี','Stock by color'),13,True).pack(side='left',padx=(0,12))
    color_names={app.color_label(key):key for key in data.COLORS};color_var=tk.StringVar();color=select_field(color_bar,textvariable=color_var,values=list(color_names),state='readonly',width=20,font=app.font(11));color.pack(side='left')
    matrix=tk.Frame(form,bg='white');matrix.pack(fill='x',padx=20,pady=8)
    blocks=[]
    for size,label in db.SIZE_LABELS.items():
        block=tk.Frame(matrix,bg='white');blocks.append(block)
        app.label(block,label,12,True).pack(anchor='w',pady=(0,5))
        var=tk.StringVar(value='0');entry=field(block);entry.configure(textvariable=var,width=78);entry.pack(fill='x')
        warning=app.label(block,'',10,fg='#BB2020');warning.pack(anchor='w',pady=4)
        def count_changed(*args,v=var,e=entry,w=warning):
            dirty();raw=v.get();valid=raw.isascii() and raw.isdecimal()
            low=valid and int(raw)<5;e.configure(text_color='#BB2020' if low or not valid else '#243E55')
            w.configure(text=app.ui('เหลือน้อย','Low stock') if low else '' if valid else app.ui('ใส่จำนวนเต็ม','Whole numbers'))
        var.trace_add('write',count_changed);sizes[size]={'variable':var,'entry':entry,'warning':warning}
    columns=[None]
    def layout(event):
        count=max(1,min(10,event.width//95))
        if count==columns[0]:return
        columns[0]=count
        for col in range(10):matrix.columnconfigure(col,weight=int(col<count))
        for index,block in enumerate(blocks):block.grid(row=index//count,column=index%count,sticky='ew',padx=(0,12),pady=6)
    matrix.bind('<Configure>',layout)
    app.label(form,app.ui('ปรับจำนวนแต่ละไซซ์ แล้วกดบันทึกสินค้าและสต็อก','Edit each size quantity, then save the product and stock.'),11,fg='#5D6975',wraplength=850).pack(anchor='w',padx=20,pady=(6,16))
    statistics=card(form,color='#F1F3F5',radius=16);statistics.configure(border_color='#DAE0E6');statistics.pack(fill='x',padx=20,pady=(4,20))
    app.label(statistics,app.ui('ยอดขายแยกสี','Sales by color'),14,True,bg='#F1F3F5',fg='#243E55').pack(anchor='w',padx=20,pady=(18,8))
    stats=app.label(statistics,'',14,True,bg='#F1F3F5',wraplength=800,justify='left');stats.pack(anchor='w',padx=20)
    sales_table=app.table(statistics,[('color',app.ui('สีสินค้า','Color'),210),('units',app.ui('ขายแล้ว (ตัว)','Units sold'),140),('revenue',app.ui('ยอดขายสุทธิ','Net sales'),180)],4)
    stats_actions=tk.Frame(statistics,bg='#F1F3F5');stats_actions.pack(fill='x',padx=20,pady=(14,20))
    app.button(stats_actions,app.ui('ดูคำสั่งซื้อ','View orders'),lambda:app.open_admin_tab('orders'),compact=True).pack(side='left',padx=(0,8))
    app.button(stats_actions,app.ui('ยอดขายตามวัน / เดือน / ปี','Sales by day / month / year'),lambda:app.open_admin_tab('dashboard'),compact=True).pack(side='left')
    def confirm_discard():
        return not state['dirty'] or messagebox.askyesno('JPZ',app.ui('มีข้อมูลที่ยังไม่บันทึก ต้องการเปลี่ยนสินค้า / สีและทิ้งการแก้ไขหรือไม่?','Discard unsaved changes and switch the product / color?'))
    def style_card(card,selected=False):
        product=card._product;chosen=card_colors.get(product['id'],product['color'])
        if chosen is None and card._stock_alerts['colors']:chosen=next(iter(card._stock_alerts['colors']))
        no_colors=not card._stock_alerts['colors']
        alert=card._stock_alerts['colors'].get(chosen,dict(low_count=0 if no_colors else len(db.SIZE_LABELS),out_count=0 if no_colors else len(db.SIZE_LABELS),minimum=0))
        card._stock_alert=alert;low=bool(alert['low_count'])
        card.configure(highlightbackground='#BB2020' if low else '#243E55' if selected else '#DFE5EB',highlightthickness=3 if selected else 2 if low else 1,bg='#F0F4F7' if selected else 'white')
        card._editing_label.configure(text=app.ui('กำลังแก้ไข','EDITING') if selected else '',bg='#243E55' if selected else 'white',fg='white' if selected else '#243E55')
        if selected:
            card._editing_holder.pack(before=card._title,anchor='w')
            card._editing_label.pack(anchor='w',pady=(0,4))
        else:card._editing_holder.pack_forget()
        card._color_label.configure(text=app.ui('ยังไม่มีสีที่จำหน่าย','No selling colors') if no_colors else app.ui('สต็อก: ','Stock: ')+app.color_label(chosen))
        card._stock_label.configure(text=app.ui('หมดบางไซซ์','Some sizes sold out') if alert['out_count'] else app.ui('มีไซซ์ใกล้หมด','Some sizes low') if low else '',fg='#BB2020')
        if low:card._stock_label.grid()
        else:card._stock_label.grid_remove()
        others=sum(bool(v['low_count']) for color,v in card._stock_alerts['colors'].items() if color!=chosen)
        card._other_label.configure(text=app.ui(f'สีอื่นต้องเติม: {others} สี',f'Other colors to restock: {others}') if others else '',fg='#8D652B')
        if others:card._other_label.grid()
        else:card._other_label.grid_remove()
    def load(pid,chosen_color=None,confirm=True,focus=False):
        if confirm and not confirm_discard():return False
        previous_pid=(state['product'] or {}).get('id')
        product=db.product(pid)
        if not product:return False
        sales_table._report_kind='product_colors';sales_table._report_context=dict(product_id=pid)
        state.update(product=product,loading=True);app._inventory_selected=pid
        header.configure(text=product['name'])
        for key,var in entries.items():var.set(next(label for label,value in fits.items() if value==product[key]) if key=='fit' else next(label for label,value in styles.items() if value==product[key]) if key=='style' else str(product[key]))
        offer=product_promotions.setting(pid);enabled.set(bool(offer['enabled']));offer_kind.set(next(label for label,key in offer_names.items() if key==offer['kind']));offer_value.set(f"{offer['value']:g}")
        available=product_colors.keys(pid)
        color_names.clear();color_names.update({app.color_label(key):key for key in available});color.configure(values=list(color_names))
        chosen_color=chosen_color or card_colors.get(pid,product['color'])
        if chosen_color not in available:chosen_color=available[0] if available else None
        color.configure(state='readonly' if available else 'disabled')
        color_var.set(app.color_label(chosen_color) if chosen_color else '');state['color']=chosen_color;card_colors[pid]=chosen_color
        all_variants=db.variants(pid);variants={v['size']:v['stock'] for v in all_variants if v['color']==chosen_color};state['baseline']=variants
        for size,cell in sizes.items():
            cell['variable'].set(str(variants.get(size,0)));cell['entry'].configure(state='normal' if available else 'disabled')
            if not available:cell['warning'].configure(text='')
        sold=data.query(app.user['id'],"SELECT i.color,SUM(i.quantity) units,ROUND(SUM(i.price*i.quantity*o.total/NULLIF(o.subtotal,0)),2) revenue FROM order_items i JOIN orders o ON o.id=i.order_id WHERE i.product_id=? AND o.payment_status='paid' GROUP BY i.color ORDER BY i.color",(pid,))
        sales={row['color']:row for row in sold};sales_table.delete(*sales_table.get_children())
        for key in dict.fromkeys(available+[row['color'] for row in sold]):
            row=sales.get(key,dict(units=0,revenue=0));sales_table.insert('','end',iid=key,values=(app.color_label(key),row['units'],f"{row['revenue']:,.2f}"))
        selected_sales=sales.get(chosen_color,dict(units=0,revenue=0))
        stats.configure(text=(app.ui('สีที่เลือก: ','Selected color: ')+app.color_label(chosen_color)+app.ui(f" · ขาย {selected_sales['units']} ตัว · ฿{selected_sales['revenue']:,.2f}",f" · {selected_sales['units']} units · ฿{selected_sales['revenue']:,.2f}")) if chosen_color else app.ui('ยังไม่ได้เลือกสี','No color selected'))
        hide.configure(text=app.ui('ซ่อนสินค้า','Hide product') if product['active'] else app.ui('แสดงสินค้า','Show product'))
        state.update(loading=False,dirty=False);status.configure(text='')
        action_buttons[0].configure(state='normal' if available else 'disabled')
        if not available:status.configure(text=app.ui('ยังไม่มีสีสินค้า กดเพิ่มสีก่อนบันทึกสต็อก','No product colors. Add a color before saving stock.'),fg='#8D652B')
        if pid in cards:
            visible_keys={v['color'] for v in all_variants}
            cards[pid]._stock_alerts['colors']={key:value for key,value in cards[pid]._stock_alerts['colors'].items() if key in visible_keys}
        if pid in cards and chosen_color is not None:
            values=[variants.get(size,0) for size in db.SIZE_LABELS]
            cards[pid]._stock_alerts['colors'][chosen_color]=dict(low_count=sum(n<inventory.LOW_STOCK_LIMIT for n in values),out_count=sum(n==0 for n in values),minimum=min(values))
        for card_pid in {previous_pid,pid}:
            if card_pid in cards:style_card(cards[card_pid],card_pid==pid)
        header.configure(text=app.ui('กำลังแก้ไข · ','Editing · ')+product['name']+' / '+product['code'],fg='#243E55')
        if focus:
            status.configure(text=app.ui('แก้ไขข้อมูลแล้วกดบันทึกสินค้าและสต็อก','Edit the fields, then save the product and stock.'),fg='#5D6975')
            def reveal():
                if not form.winfo_exists() or not state['product'] or state['product']['id']!=pid:return
                form.master.yview_moveto(0);field_widgets['name'].focus_set();field_widgets['name'].icursor(0)
            app.after_idle(reveal)
        return True
    image_generation=[0];image_stop=[threading.Event()]
    def refresh_list(*args):
        image_stop[0].set();stopped=threading.Event();image_stop[0]=stopped;image_generation[0]+=1;generation=image_generation[0]
        term=search.get().strip().casefold();actor=app.user['id'];result_queue=queue.Queue()
        if pagination['term'] is not None and pagination['term']!=term:pagination['page']=0
        pagination['term']=term;requested_page=pagination['page']
        if not cards:app.label(listing,app.ui('กำลังโหลดสินค้า…','Loading products…'),12,fg='#5D6975').pack(pady=25)
        def read_products():
            try:
                products=[p for p in db.products(include_archived=True) if term in (p['name']+' '+p['code']).casefold()]
                total=len(products);pages=max(1,(total+19)//20);number=min(requested_page,pages-1)
                products=products[number*20:(number+1)*20]
                quotes={};connection=db.conn()
                try:
                    connection.execute('BEGIN IMMEDIATE')
                    alerts=inventory.stock_alerts(connection,products)
                    for product in products:
                        if stopped.is_set():return
                        quotes[product['id']]=product_promotions.cart_quote({(product['id'],product['color'],32):1},actor,connection)
                    connection.commit()
                finally:connection.close()
                result_queue.put((products,quotes,alerts,None,total,pages,number))
            except Exception as exc:result_queue.put((None,None,None,str(exc),0,1,0))
        def receive():
            from support.image_jobs import is_current
            if not is_current(listing):stopped.set();return
            if stopped.is_set() or not listing.winfo_exists():return
            try:products,quotes,alerts,error,total,pages,number=result_queue.get_nowait()
            except queue.Empty:app.after(20,receive);return
            if error:
                status.configure(text=app.ui('โหลดสินค้าไม่สำเร็จ: ','Could not load products: ')+error,fg='#BB2020');return
            pagination.update(page=number,pages=pages);app._inventory_list_page=number
            page_note.configure(text=app.ui(f'{total} รายการ · หน้า {number+1}/{pages}',f'{total} products · page {number+1}/{pages}'))
            previous.configure(state='normal' if number else 'disabled');following.configure(state='normal' if number+1<pages else 'disabled')
            listing.master.yview_moveto(0)
            render_products(products,quotes,alerts,stopped,generation)
        threading.Thread(target=read_products,daemon=True).start();app.after(20,receive)
    def render_products(products,quotes,alerts,stopped,generation):
        for widget in listing.winfo_children():widget.destroy()
        cards.clear()
        pictures={}
        waiting_images={}
        def visible_images():
            from support.image_jobs import is_current
            if not is_current(listing):return
            if stopped.is_set() or generation!=image_generation[0] or not listing.winfo_exists():return
            viewport=listing.master
            top=viewport.winfo_rooty()-180;bottom=top+viewport.winfo_height()+360
            # โหลดเฉพาะภาพที่เห็นหรืออยู่ใกล้ขอบจอ ไม่ถอดรหัสภาพครบทั้งร้านตอนเปิดหน้า
            for pid,(picture,work,done) in list(waiting_images.items()):
                if picture.winfo_ismapped() and top<=picture.winfo_rooty()+picture.winfo_height() and picture.winfo_rooty()<=bottom:
                    from support import image_jobs
                    image_jobs.submit(app,picture,work,done);del waiting_images[pid]
            app.after(160,visible_images)
        if not state['product'] and products:
            wanted=getattr(app,'_inventory_selected',None)
            initial=next((p for p in products if p['id']==wanted),products[0])
            load(initial['id'],confirm=False)
        def render_one(product):
            pid=product['id'];card=tk.Frame(listing,bg='white',highlightbackground='#DFE5EB',highlightthickness=1);card.pack(fill='x',padx=8,pady=6);cards[pid]=card
            card._product=product;card._stock_alerts=alerts[pid]
            photo_box=tk.Frame(card,bg='#F1F3F5',width=85,height=110);photo_box.pack(side='left',padx=8,pady=8);photo_box.pack_propagate(False)
            picture=tk.Label(photo_box,bg='#F1F3F5',text='JPZ',font=app.font(11,True));picture.pack(fill='both',expand=True);pictures[pid]=picture
            info=tk.Frame(card,bg='white');info.pack(side='left',fill='both',expand=True,padx=(0,8),pady=8)
            editing_holder=tk.Frame(info,bg='white');editing_holder.pack(anchor='w')
            card._editing_holder=editing_holder
            card._editing_label=app.label(editing_holder,'',9,True,bg='white',fg='#243E55',padx=7,pady=3)
            title=app.label(info,product['name'],11,True,wraplength=190,justify='left');title.pack(anchor='w')
            card._title=title
            app.label(info,product['code'],10,fg='#5D6975').pack(anchor='w')
            stock_holder=tk.Frame(info,bg='white');stock_holder.pack(anchor='w')
            card._color_label=app.label(stock_holder,'',10,fg='#5D6975',wraplength=185,justify='left');card._color_label.grid(row=0,column=0,sticky='w')
            card._stock_label=app.label(stock_holder,'',10,True,fg='#BB2020',wraplength=185,justify='left');card._stock_label.grid(row=1,column=0,sticky='w')
            card._other_label=app.label(stock_holder,'',9,fg='#8D652B',wraplength=185,justify='left');card._other_label.grid(row=2,column=0,sticky='w')
            style_card(card,((state['product'] or {}).get('id')==pid))
            if not product['active']:app.label(info,app.ui('ซ่อนอยู่','Hidden'),10,fg='#BB2020').pack(anchor='w')
            app.catalogue_price(info,product,quote=quotes[pid])
            edit=app.button(info,app.ui('เปิดแก้ไข','Open editor'),lambda product_id=pid:load(product_id,focus=True),compact=True);edit.pack(anchor='w',pady=(5,0));card._edit_button=edit
            for widget in (card,picture,title):widget.bind('<Button-1>',lambda event,product_id=pid:load(product_id,focus=True))
            def load_image():
                if stopped.is_set():return None
                try:
                    photo=gallery.preview(pid,product['color'],'DETAIL') if gallery.Image is not None else None
                    return ImageOps.pad(photo,(85,110),color='#F1F3F5') if photo is not None else None
                except (OSError,ValueError,sqlite3.Error):return None
            def apply_image(photo):
                if stopped.is_set() or generation!=image_generation[0] or photo is None:return
                image=gallery.to_photo(photo,master=app);picture.configure(image=image,text='');picture._image=image
            waiting_images[pid]=(picture,load_image,apply_image)
            # เปิดฟอร์มแก้ไขได้ทันที โดยไม่รอสร้างการ์ดสินค้าครบทุกตัว
            wanted=getattr(app,'_inventory_selected',None)
            if not state['product'] and (wanted==pid or wanted is None):load(pid,confirm=False)
        def finish():
            if not cards:app.label(listing,app.ui('ไม่พบสินค้า','No products found'),12,fg='#5D6975').pack(pady=25)
            pid=(state['product'] or {}).get('id') or getattr(app,'_inventory_selected',None)
            if not state['product'] and cards:load(pid if pid in cards else next(iter(cards)),confirm=False)
            elif pid in cards:style_card(cards[pid],True)
        pending=iter(products)
        def batch():
            from support.image_jobs import is_current
            if not is_current(listing):return
            if stopped.is_set() or generation!=image_generation[0] or not listing.winfo_exists():return
            for index in range(1):
                try:product=next(pending)
                except StopIteration:finish();return
                render_one(product)
            app.after(16,batch)
        batch()
        app.after(30,visible_images)
    def save():
        if not state['product']:return
        try:
            counts={}
            for size,cell in sizes.items():
                raw=cell['variable'].get().strip()
                if not raw.isascii() or not raw.isdecimal():raise ValueError(app.ui('กรอกสต็อกเป็นจำนวนเต็มตั้งแต่ 0 ทุกช่อง','Enter non-negative whole stock quantities for all sizes.'))
                counts[size]=int(raw)
            values=dict(state['product']);values.update({key:var.get() for key,var in entries.items()});values['fit']=fits[entries['fit'].get()];values['style']=styles[entries['style'].get()]
            offer=dict(kind=offer_names[offer_kind.get()],value=offer_value.get(),enabled=enabled.get())
            inventory.save(app.user['id'],state['product'],values,offer,state['color'],counts,state['baseline'])
            pid=state['product']['id'];load(pid,state['color'],confirm=False);refresh_list();status.configure(text=app.ui('บันทึกสินค้า โปรโมชั่น และสต็อกแล้ว','Product, promotion and stock saved.'),fg='#26734D')
        except (ValueError,PermissionError,sqlite3.Error) as exc:status.configure(text=str(exc),fg='#BB2020')
    action_buttons=[app.button(actions,app.ui('บันทึกสินค้าและสต็อก','Save product and stock'),save,dark=True,compact=True),app.button(actions,app.ui('รูปสินค้า','Product photos'),lambda:app.gallery_dialog(state['product']) if state['product'] else None,compact=True),app.button(actions,app.ui('ตารางไซซ์','Size chart'),lambda:app.admin_size_dialog(state['product']) if state['product'] else None,compact=True)]
    def action_layout(event):
        cols=3 if event.width>=560 else 2 if event.width>=380 else 1
        for index,button in enumerate(action_buttons):button.grid(row=index//cols,column=index%cols,sticky='w',padx=(0,8),pady=(0,6))
    actions.bind('<Configure>',action_layout)
    visibility=tk.Frame(form,bg='white');visibility.pack(fill='x',padx=20,pady=(0,20))
    def toggle():
        if not state['product'] or not confirm_discard():return
        product=state['product'];catalogue.set_product_visibility(app.user['id'],product['id'],not product['active']);load(product['id'],confirm=False);refresh_list()
    hide=app.button(visibility,app.ui('ซ่อนสินค้า','Hide product'),toggle,compact=True);hide.pack(side='left',padx=(0,8))
    def delete():
        product=state['product']
        if not product:return
        if not messagebox.askyesno('JPZ',app.ui(f"ลบ {product['name']} ออกจากร้าน?",f"Delete {product['name']}?")):return
        try:catalogue.delete_product(app.user['id'],product['id']);state.update(product=None,dirty=False);refresh_list()
        except (ValueError,PermissionError) as exc:status.configure(text=str(exc),fg='#BB2020')
    app.button(visibility,app.ui('ลบสินค้า','Delete product'),delete,compact=True).pack(side='left')
    app.button(visibility,app.ui('โหลดข้อมูลใหม่','Reload data'),lambda:load(state['product']['id'],state['color']) if state['product'] else None,compact=True).pack(side='right')
    def choose_color(event):
        previous=state.get('color');wanted=color_names[color_var.get()]
        if not state['product'] or not load(state['product']['id'],wanted):color_var.set(app.color_label(previous))
    def add_color():
        if not state['product'] or not confirm_discard():return
        win=tk.Toplevel(app);win.title(app.ui('เพิ่มสีสินค้า','Add product color'));win.configure(bg='white');win.transient(app)
        width=min(520,app.winfo_screenwidth()-80);height=min(580,app.winfo_screenheight()-140)
        win.geometry(f'{width}x{height}+{max(0,(app.winfo_screenwidth()-width)//2)}+{max(0,(app.winfo_screenheight()-height)//2)}');win.minsize(360,360)
        footer=tk.Frame(win,bg='white',height=72);footer.pack(side='bottom',fill='x',padx=20,pady=12);footer.pack_propagate(False)
        body=app.scroll_content(win)
        choices={app.color_label(k):k for k in data.COLORS}
        app.label(body,app.ui('เลือกสีร้าน หรือกำหนดสีใหม่','Choose a store color or name a new color'),13,True,wraplength=390).pack(padx=20,pady=20)
        selected=tk.StringVar(value=next(iter(choices)))
        select_field(body,values=list(choices),textvariable=selected,state='readonly').pack(fill='x',padx=20)
        def apply(key=None,name=None):
            try:
                pid=state['product']['id'];key=product_colors.add(app.user['id'],pid,name=name,key=key)
                win.destroy();load(pid,key,confirm=False);refresh_list()
            except (ValueError,PermissionError,sqlite3.Error) as exc:messagebox.showerror('JPZ',str(exc),parent=win)
        app.button(body,app.ui('เพิ่มสีที่เลือก','Add selected color'),lambda:apply(key=choices[selected.get()])).pack(pady=10)
        name=app.entry(body,app.ui('ชื่อสีใหม่ที่กำหนดเอง','Custom color name'))
        app.label(body,app.ui('กรอกชื่อสี แล้วกดบันทึกสีใหม่ด้านล่าง','Enter a color name, then save the new color below.'),11,wraplength=390).pack(padx=20,pady=12)
        app.button(footer,app.ui('ยกเลิก','Cancel'),win.destroy,compact=True).pack(side='left',pady=10)
        save_new=app.button(footer,app.ui('บันทึกสีใหม่','Save new color'),lambda:apply(name=name.get()),dark=True,compact=True);save_new.pack(side='right',pady=10)
        app._add_color_ui=dict(window=win,name=name,save=save_new,apply=apply,body=body,footer=footer)
    def remove_color():
        if not state['product'] or not confirm_discard():return
        key=state['color'];pid=state['product']['id']
        if key is None:return
        if not messagebox.askyesno('JPZ',app.ui('ลบสี '+app.color_label(key)+' ออกจากสินค้านี้? สต็อกและคำสั่งซื้อเดิมจะถูกเก็บไว้','Remove '+app.color_label(key)+' from this product? Stock and past orders are retained.')):return
        try:
            next_color=product_colors.remove(app.user['id'],pid,key);load(pid,next_color,confirm=False);refresh_list()
        except (ValueError,PermissionError,sqlite3.Error) as exc:status.configure(text=str(exc),fg='#BB2020')
    app.button(color_bar,app.ui('+ เพิ่มสี','+ Add color'),add_color,compact=True).pack(side='left',padx=8)
    app.button(color_bar,app.ui('ลบสีนี้','Remove color'),remove_color,compact=True).pack(side='left')
    pending_search=[None]
    def search_changed(*args):
        if pending_search[0]:app.after_cancel(pending_search[0])
        def run():
            pending_search[0]=None
            if listing.winfo_exists():refresh_list()
        pending_search[0]=app.after(180,run)
    listing.bind('<Destroy>',lambda event:image_stop[0].set() if event.widget is listing else None)
    color.bind('<<ComboboxSelected>>',choose_color);search.trace_add('write',search_changed)
    app._inventory_editor_ui=dict(state=state,cards=cards,entries=entries,field_widgets=field_widgets,form=form,header=header,sizes=sizes,search=search,load=load,save=save,color=color,color_variable=color_var,enabled=enabled,kind=offer_kind,value=offer_value,status=status,refresh=refresh_list,add_color=add_color,sales_table=sales_table,stats=stats)
    app._inventory_editor_ui['pagination']=dict(state=pagination,next=following,previous=previous,label=page_note)
    refresh_list()
