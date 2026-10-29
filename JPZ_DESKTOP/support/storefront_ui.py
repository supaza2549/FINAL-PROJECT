"""หน้ารวมสินค้าแบบใหม่ ใช้ระบบราคา สต็อก และตะกร้าเดิม"""
import tkinter as tk
from support.theme import card,DENIM,BORDER,select_field,ui_font
from support import merchandising,product_colors,product_promotions,catalogue,loyalty,gallery
from support.language import option_name
import db
PAGE_SIZE=12


def accordion(app,parent,caption,selection,choices,on_select):
    from support.denim_surface import NAVY,IVORY
    app.label(parent,caption,12,True,fg=IVORY,bg=NAVY).pack(anchor='w',padx=12,pady=(18,8))
    button=app.button(parent,selection+' ▾',lambda:None,compact=True);button.pack(fill='x',padx=10,pady=3)
    button.configure(fg_color=IVORY,border_color='#B8A88E')
    fold=tk.Frame(parent,bg=NAVY,height=1);fold.pack_propagate(False)
    inner=tk.Frame(fold,bg=NAVY);inner.pack(fill='x',anchor='n')
    state={'open':False,'height':0,'target':0,'job':None}
    for key,text in choices:
        app.button(inner,text,lambda k=key:on_select(k),dark=text==selection,compact=True).pack(fill='x',padx=10,pady=3)
    def animate():
        state['job']=None
        if not fold.winfo_exists():return
        delta=state['target']-state['height']
        if abs(delta)<=2:
            state['height']=state['target'];fold.configure(height=max(1,state['height']))
            if not state['open']:fold.pack_forget()
            return
        state['height']+=int(delta/3) or (1 if delta>0 else -1)
        fold.configure(height=max(1,state['height']))
        state['job']=fold.after(16,animate)
    def toggle():
        state['open']=not state['open'];button.configure(text=selection+(' ▴' if state['open'] else ' ▾'))
        if state['open']:
            fold.pack(fill='x',after=button);fold.update_idletasks();state['target']=inner.winfo_reqheight()
        else:state['target']=0
        if state['job'] is not None:fold.after_cancel(state['job']);state['job']=None
        animate()
    def cancel(event):
        if event.widget is fold and state['job'] is not None:
            fold.after_cancel(state['job']);state['job']=None
    fold.bind('<Destroy>',cancel);button.configure(command=toggle)
    return dict(button=button,fold=fold,state=state)


# J14 | หน้ารวมสินค้า / ตัวกรอง / แบ่งหน้า
def show(app):
    body=app.shell(show_back=False)
    workspace=tk.Frame(body,bg='white');workspace.pack(fill='both',expand=True,padx=24,pady=18)
    sidebar=tk.Frame(workspace,bg='#193244',width=215,highlightbackground='#B8A88E',highlightthickness=1);sidebar.pack(side='left',fill='y',padx=(0,18));sidebar.pack_propagate(False)
    from support.denim_surface import sidebar as denim_sidebar
    categories=denim_sidebar(app,sidebar)
    from main import FITS,STYLES
    fit_caption=app.tr('all') if app.shop_fit=='all' else app.fit_label(app.shop_fit)
    fit_choices=[(key,app.tr('all') if key=='all' else app.fit_label(key)) for key in ['all']+FITS]
    fit_fold=accordion(app,categories,app.ui('หมวดหมู่สินค้า','Product category'),fit_caption,fit_choices,app.set_shop_fit)
    style_caption=app.tr('all') if app.shop_style=='all' else option_name(app.lang,app.shop_style)
    style_choices=[(key,app.tr('all') if key=='all' else option_name(app.lang,key)) for key in ['all']+STYLES]
    style_fold=accordion(app,categories,app.ui('สไตล์','Style'),style_caption,style_choices,app.set_shop_style)
    right=tk.Frame(workspace,bg='white');right.pack(side='left',fill='both',expand=True)
    page=app.scroll_content(right)
    head=tk.Frame(page,bg='white');head.pack(fill='x',padx=12,pady=(10,14))
    app.label(head,'JPZ / COLLECTION',10,True,fg='#5D6975').pack(anchor='w')
    app.label(head,app.ui('ยีนส์ทั้งหมด','YOUR DENIM SELECTION'),22,True,fg=DENIM).pack(anchor='w',pady=(6,4))
    app.label(head,app.ui('เลือกยีนส์ที่ใช่ ในสไตล์ที่เป็นคุณ','Find your fit. Make it yours.'),11,fg='#5D6975').pack(anchor='w')
    app.promotion_banner(page)
    items=[p for p in db.products() if (app.shop_fit=='all' or p['fit']==app.shop_fit) and (app.shop_style=='all' or p['style']==app.shop_style)]
    ranks=merchandising.best_sellers();items.sort(key=lambda p:(ranks.get(p['id'],6),p['id']))
    sort=getattr(app,'shop_sort','recommended')
    quotes={}
    if sort in ('price_low','price_high'):
        # คำนวณราคาในธุรกรรมเดียว ลดการเปิดฐานข้อมูลซ้ำเมื่อเรียงสินค้า
        connection=db.conn()
        try:
            for product in items:quotes[product['id']]=product_promotions.cart_quote({(product['id'],product['color'],32):1},app.user['id'],connection)
            connection.commit()
        except Exception:connection.rollback();raise
        finally:connection.close()
        items.sort(key=lambda p:quotes[p['id']]['total'],reverse=sort=='price_high')
    signature=(app.shop_fit,app.shop_style,sort)
    if getattr(app,'_shop_filter_signature',None)!=signature:app.shop_page=0;app._shop_filter_signature=signature
    pages=max(1,(len(items)+PAGE_SIZE-1)//PAGE_SIZE);number=min(max(0,getattr(app,'shop_page',0)),pages-1);app.shop_page=number
    def change(target):
        if not 0<=target<pages:return
        app.shop_page=target;app._reset_shop_scroll=True;app._shop()
    def pagination():
        bar=tk.Frame(page,bg='white');bar.pack(fill='x',padx=12,pady=(4,14))
        previous=app.button(bar,app.ui('‹ ก่อนหน้า','‹ Previous'),lambda:change(number-1),compact=True)
        previous.pack(side='left');previous.configure(state='normal' if number else 'disabled')
        app.label(bar,app.ui(f'หน้า {number+1} / {pages}',f'Page {number+1} / {pages}'),11,fg='#5D6975').pack(side='left',padx=14)
        following=app.button(bar,app.ui('ถัดไป ›','Next ›'),lambda:change(number+1),compact=True)
        following.pack(side='right');following.configure(state='normal' if number+1<pages else 'disabled')
        return dict(frame=bar,previous=previous,next=following)
    controls=tk.Frame(page,bg='white');controls.pack(fill='x',padx=12,pady=(6,12))
    app.label(controls,app.ui(f'{len(items)} รายการ',f'{len(items)} products'),11,fg='#5D6975').pack(side='left')
    choices={app.ui('แนะนำ','Recommended'):'recommended',app.ui('ราคาน้อยไปมาก','Price: low to high'):'price_low',app.ui('ราคามากไปน้อย','Price: high to low'):'price_high'}
    variable=tk.StringVar(value=next(k for k,v in choices.items() if v==sort))
    picker=select_field(controls,textvariable=variable,values=list(choices),state='readonly',width=20)
    def choose(value):app.shop_sort=choices[value];app.shop_page=0;app._reset_shop_scroll=True;app._shop()
    picker.configure(command=choose);picker.pack(side='right')
    top_paging=pagination()
    visible=items[number*PAGE_SIZE:(number+1)*PAGE_SIZE]
    connection=db.conn()
    try:
        for product in visible:
            if product['id'] not in quotes:quotes[product['id']]=product_promotions.cart_quote({(product['id'],product['color'],32):1},app.user['id'],connection)
        connection.commit()
    except Exception:connection.rollback();raise
    finally:connection.close()
    grid(app,page,visible,quotes)
    bottom_paging=pagination()
    app._new_shop_ui=dict(sidebar=sidebar,denim_canvas=categories._denim_canvas,content=page,items=items,page=number,change=change,more=fit_fold['button'],extra=fit_fold['fold'],style_toggle=style_fold['button'],styles=style_fold['fold'],sort=picker,set_sort=choose,top_paging=top_paging,bottom_paging=bottom_paging)


# J15 | การ์ดสินค้า
def grid(app,parent,items,quotes=None):
    frame=tk.Frame(parent,bg='white');frame.pack(fill='x',padx=6,pady=4)
    cards=[];columns=[None]
    app._card_batches=getattr(app,'_card_batches',set());token=object();app._card_batches.add(token)
    frame.bind('<Destroy>',lambda e:app._card_batches.discard(token) if e.widget is frame else None,add='+')
    def layout(event=None):
        count=4 if frame.winfo_width()>=1250 else 3 if frame.winfo_width()>=850 else 2 if frame.winfo_width()>=540 else 1
        if count==columns[0]:return
        columns[0]=count
        for col in range(4):frame.columnconfigure(col,weight=int(col<count),uniform='catalog' if col<count else '',minsize=0)
        for index,panel in enumerate(cards):panel.grid(row=index//count,column=index%count,sticky='nsew',padx=6,pady=8)
    frame.bind('<Configure>',layout)
    def open_product(product,color=None):
        if color is not None:
            state=app.product_state.setdefault(product['id'],dict(color=color,size=32,qty=1,view='FRONT'));state['color']=color
        app.product_detail(product)
    def build(index,product):
        panel=card(frame,radius=10);panel._skip_block_shine=True;cards.append(panel)
        tools=tk.Frame(panel,bg='#343A40');tools.pack(fill='x',padx=1,pady=(1,0))
        offer=product_promotions.setting(product['id'])
        if offer['enabled'] and offer['kind']=='price':app.label(tools,app.ui('ราคาพิเศษ','SPECIAL PRICE'),10,True,bg='#343A40',fg='#F7E2E7').pack(side='left',padx=12)
        saved=db.is_favorite(app.user['id'],product['id'])
        heart=app.favorite_button(tools,product,saved=saved,compact=True)
        heart.configure(image=None,text='♥' if saved else '♡',font=ui_font(18),fg_color='#343A40',bg_color='#343A40',hover_color='#454D55',border_color='#626B74',text_color='#EF667C' if saved else '#F3F4F5')
        heart.pack(side='right',padx=10,pady=7)
        # ใช้ภาพที่ตรงรุ่นและสีจริง สลับมุมคนใส่ที่มีอยู่ในแกลเลอรี
        views={row['view'] for row in catalogue.gallery(product['id'],product['color'])}
        view=gallery.standing_view(product,prefer_back=index%4==2)
        app.product_picture(panel,product,product['color'],view,height=310,lower_body=True,hover_zoom=getattr(app,'current_page','')=='shop',lazy=True)
        swatches=tk.Frame(panel,bg='white');swatches.pack(fill='x',padx=14,pady=(8,2))
        colors=product_colors.keys(product['id'])
        for color in colors[:4]:
            palette={'black':'#191919','dark_indigo':'#23344D','raw_indigo':'#263D59','washed_blue':'#6E93AC','light_blue':'#B1CDDF','vintage_blue':'#64869B','grey':'#8B8D90'}
            dot=tk.Canvas(swatches,width=17,height=17,bg='white',highlightthickness=0,cursor='hand2');dot.pack(side='left',padx=(0,5))
            dot.create_oval(2,2,15,15,fill=palette.get(color,'#687887'),outline='')
            dot.bind('<Button-1>',lambda e,p=product,c=color:open_product(p,c))
        app.label(swatches,app.color_label(product['color']),10,fg='#5D6975',wraplength=180).pack(side='left',padx=3)
        name=app.label(panel,product['name'],12,True,fg=DENIM,wraplength=260);name.pack(anchor='w',padx=14,pady=(8,2))
        app.label(panel,f"{app.fit_label(product['fit'])} / {option_name(app.lang,product['style'])}",10,fg='#5D6975').pack(anchor='w',padx=14)
        app.catalogue_price(panel,product,padx=14,quote=(quotes or {}).get(product['id']))
        app.button(panel,app.tr('view_product'),lambda p=product:open_product(p),compact=True).pack(fill='x',padx=14,pady=(10,14))
        panel.bind('<Configure>',lambda e,label=name:label.configure(wraplength=max(140,e.width-28)))
        if columns[0] is None:layout()
        else:panel.grid(row=index//columns[0],column=index%columns[0],sticky='nsew',padx=6,pady=8)
    iterator=iter(enumerate(items))
    def batch():
        from support.image_jobs import is_current
        if not is_current(frame) or not frame.winfo_exists():app._card_batches.discard(token);return
        for _ in range(1):
            try:index,product=next(iterator)
            except StopIteration:app._card_batches.discard(token);return
            build(index,product)
        app.after(16,batch)
    batch()
    app._new_catalog_cards=cards

# J19 | รายการโปรด
def show_favorites(app):
    """รายการโปรดและสินค้าแนะนำใช้การ์ดและภาพแบบเดียวกับหน้ารวมสินค้า"""
    body=app.shell(show_back=False);content=app.scroll_content(body)
    head=tk.Frame(content,bg='white');head.pack(fill='x',padx=30,pady=(20,12))
    app.label(head,'JPZ / FAVORITES',10,True,fg='#5D6975').pack(anchor='w')
    app.label(head,app.tr('favorites'),24,True,fg=DENIM).pack(anchor='w',pady=8)
    saved=db.favorite_products(app.user['id']);empty=not saved
    if empty:
        app.label(head,app.ui('ยังไม่มีสินค้าที่บันทึกไว้ เลือกยีนส์ที่ถูกใจแล้วกดหัวใจได้เลย','No saved pairs yet. Find your denim and tap the heart.'),11,fg='#5D6975',wraplength=900).pack(anchor='w')
        buttons=tk.Frame(head,bg='white');buttons.pack(anchor='w',pady=12)
        app.button(buttons,app.tr('browse_denim'),app.shop,dark=True).pack(side='left',padx=(0,8))
        app.button(buttons,app.tr('find_fit'),app.fit_page).pack(side='left')
        app.label(head,'FIND YOUR NEXT FAVORITE.',16,True,fg=DENIM).pack(anchor='w',pady=(12,0))
        items=db.products()[:8];pages=1;number=0
    else:
        items=saved;pages=max(1,(len(items)+17)//18);number=min(getattr(app,'favorites_page',0),pages-1)
        app.favorites_page=number
        app.label(head,app.ui(f'บันทึกไว้ {len(saved)} รายการ',f'{len(saved)} saved products'),11,fg='#5D6975').pack(anchor='w')
    def change(target):
        if 0<=target<pages:
            app.favorites_page=target;app._reset_favorites_scroll=True;app._favorites()
    def paging():
        bar=tk.Frame(content,bg='white');bar.pack(fill='x',padx=30,pady=12)
        previous=app.button(bar,app.ui('‹ ก่อนหน้า','‹ Previous'),lambda:change(number-1),compact=True);previous.pack(side='left');previous.configure(state='normal' if number else 'disabled')
        app.label(bar,app.ui(f'หน้า {number+1} / {pages}',f'Page {number+1} / {pages}'),11,fg='#5D6975').pack(side='left',padx=14)
        following=app.button(bar,app.ui('ถัดไป ›','Next ›'),lambda:change(number+1),compact=True);following.pack(side='right');following.configure(state='normal' if number+1<pages else 'disabled')
    if not empty:paging()
    visible=items[number*18:(number+1)*18];connection=db.conn()
    try:
        quotes={p['id']:product_promotions.cart_quote({(p['id'],p['color'],32):1},app.user['id'],connection) for p in visible}
        connection.commit()
    except Exception:connection.rollback();raise
    finally:connection.close()
    grid(app,content,visible,quotes)
    if not empty:paging()
    app._new_favorites_ui=dict(content=content,items=items,empty=empty,page=number,change=change)
