from support.theme import check_field
from support.theme import select_field
# หน้าร้านและหน้าต่างหลักของโปรแกรม JPZ บนคอมพิวเตอร์
# App รวมส่วนล็อกอิน ขนาดสินค้า การชำระเงิน และแอดมิน ผ่านคลาส Mixin
# เส้นทางหลัก: เข้าสู่ระบบ > เลือกสินค้า > ตะกร้า > คำสั่งซื้อ > หลักฐาน > ใบเสร็จ

import tkinter as tk
from tkinter import messagebox, filedialog, ttk
from tkinter import font as tkfont
import os
import shutil
import uuid
import math
from pathlib import Path

try:
    from PIL import Image, ImageTk, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
from support import gallery as gallery_assets
import db
from support import admin_data
from support import loyalty
from support import catalogue
from support import merchandising
from support import product_promotions
import receipt as receipts
from support import sizing
from support.navigation import NavigationMixin
from support.return_ui import ReturnMixin
from support.size_ui import SizeMixin
from admin import AdminMixin
from receipt import PaymentMixin
from support.language import t, fit_name, option_name
from support.fit_engine import recommend, fit_details

BASE_DIR = Path(__file__).resolve().parent
PAYMENT_UPLOAD_DIR = BASE_DIR / 'payment_uploads'
ASSET_DIR = BASE_DIR / 'assets'
WHITE = '#FFFFFF'
INK = '#080808'
SOFT = '#F4F4F4'
MID = '#505050'
LINE = '#DADADA'
PANEL = '#ECECEC'
FITS = ['baggy', 'wide', 'loose', 'relaxed', 'straight', 'skinny', 'flare', 'bootcut', 'cargo', 'wide_straight']
STYLES = ['clean', 'ripped', 'vintage', 'washed', 'raw']

# กำหนดสีฟอกเฉพาะของ JPZ แต่ละทรงมีชุดสีที่เหมาะสม
# ใช้สีจำนวนจำกัดเพื่อให้รายการสินค้าดูผ่านการคัดเลือก
# และสะท้อนลักษณะของสินค้าจริง
FIT_COLOR_PALETTE = {
    'baggy': ['washed_blue', 'dark_indigo', 'light_blue'],
    'wide': ['black', 'dark_indigo', 'raw_indigo'],
    'loose': ['grey', 'dark_indigo', 'washed_blue'],
    'relaxed': ['washed_blue', 'vintage_blue', 'dark_indigo'],
    'straight': ['raw_indigo', 'vintage_blue', 'black'],
    'skinny': ['black', 'dark_indigo'],
    'flare': ['raw_indigo', 'vintage_blue', 'black'],
    'bootcut': ['raw_indigo', 'vintage_blue', 'black'],
    'cargo': ['black', 'grey'],
    'wide_straight': ['black', 'dark_indigo', 'raw_indigo'],
}

COLOR_DISPLAY_ALIASES = {
    'dark_indigo': 'indigo_black',
    'black': 'jet_black',
    'grey': 'washed_grey',
}

from support.theme import ctk, action, field, card, surface, ui_font, font_family, font_weight, DENIM
from Startprogram import StartprogramMixin

class App(NavigationMixin, ReturnMixin, StartprogramMixin, SizeMixin, PaymentMixin, AdminMixin, ctk.CTk):

    # สร้างหน้าต่างหลัก ตั้งค่าหน้าตาและตัวแปรของบัญชี ตะกร้า และการเปลี่ยนหน้า
    # J08 | หน้าต่างหลัก
    def __init__(self):
        # กำหนด DPI ก่อนสร้าง Tk เพื่อให้เต็มจอใช้ขนาดจอจริงบน Windows
        # ถ้ากำหนดหลังสร้างหน้าต่าง จอที่ตั้งสเกล 125% อาจเหลือพื้นที่ด้านข้าง
        ctk.ScalingTracker.activate_high_dpi_awareness()
        super().__init__()
        self.title('JPZ. — FIND YOUR FIT')
        self.geometry('1500x850')
        self.minsize(1100, 700)
        self.configure(fg_color=WHITE)
        self.option_add('*TCombobox*Listbox.font',self.font(11))
        style=ttk.Style(self);style.theme_use('clam')
        style.configure('TCombobox',padding=7,font=self.font(11))
        self.user = None
        self.lang = 'TH'
        self.cart = {}
        self.cart_excluded = set()
        self.page_history = []
        self.current_page = 'login'
        self.current_args = {}
        self.shop_fit = 'all'
        self.shop_style = 'all'
        self.shop_category = None
        self.fit_results = []
        self.product_state = {}
        self.login_campaign_image = None
        self.show_login(push=False)
        # เปิดเต็มจอ กด Esc เพื่อแสดงแถบหน้าต่างและปุ่มปิดตามปกติ
        self.attributes('-fullscreen',True)
        self.after_idle(self.finish_fullscreen_startup)
        self.bind('<Escape>',self.show_window_bar)
        self.protocol('WM_DELETE_WINDOW',self.destroy)
        from support.block_shine import install
        install(self)
        self.after(1000, self.receipt_worker)

    # ยกหน้าต่างขึ้นหลัง Windows จัดขนาดจอแล้ว ไม่บังคับทับโปรแกรมอื่นตลอดเวลา
    def finish_fullscreen_startup(self):
        if not self.attributes('-fullscreen'):return
        self.lift()
        self.focus_force()

    # คืนแถบด้านบนโดยยังขยายหน้าต่างเต็มพื้นที่ ไม่เปลี่ยนหน้าหรือข้อมูล
    # Esc ในหน้าต่างย่อยยังทำงานตามคำสั่งของหน้าต่างนั้น
    def show_window_bar(self,event=None):
        if event is not None and event.widget.winfo_toplevel()!=self:return
        self.attributes('-fullscreen',False)
        self.state('zoomed')
        return 'break'

    # กำหนดฟอนต์และขนาดตัวอักษรที่ใช้ร่วมกัน
    def font(self, size=11, bold=False):
        return (font_family(bold,size), max(11,size), font_weight(bold,size))

    # ล้างหน้าปัจจุบันและรายการพื้นที่เลื่อน ก่อนสร้างหน้าใหม่
    def clear(self):
        self.capture_viewport()
        self.unbind_all('<MouseWheel>')
        self._scroll_targets=[]
        # ซ่อนหน้าเก่าทันที แล้วทยอยล้างวิดเจ็ตเพื่อให้หน้าใหม่ตอบสนองก่อน
        import time
        from collections import deque
        retired=getattr(self,'_retired_widgets',None)
        if retired is None:retired=self._retired_widgets=deque()
        leaves=(ctk.CTkButton,ctk.CTkEntry,ctk.CTkLabel,ctk.CTkComboBox,ctk.CTkScrollbar,ctk.CTkCheckBox)
        def stop_events(widget):
            for sequence in tk.Misc.bind(widget) or ():
                if sequence!='<Destroy>':tk.Misc.unbind(widget,sequence)
        def collect(widget):
            # หยุดการจัดตำแหน่งของหน้าที่ซ่อนไว้ ก่อนทยอยลบองค์ประกอบย่อย
            widget.unbind('<Configure>')
            stop_events(widget)
            if isinstance(widget,(tk.Canvas,ttk.Treeview,tk.Text)):
                widget.configure(yscrollcommand='',xscrollcommand='')
            if not isinstance(widget,leaves):
                own_canvas=getattr(widget,'_canvas',None) if isinstance(widget,ctk.CTkFrame) else None
                if own_canvas is not None:stop_events(own_canvas)
                for child in widget.winfo_children():
                    if child is not own_canvas:collect(child)
            retired.append(widget)
        for w in self.winfo_children():
            if getattr(w,'_retired_page',False):continue
            if isinstance(w,tk.Toplevel):w.destroy();continue
            w._retired_page=True
            manager=w.winfo_manager()
            if manager=='pack':w.pack_forget()
            elif manager=='grid':w.grid_remove()
            elif manager=='place':w.place_forget()
            collect(w)
        self.focus_set()
        if not getattr(self,'_retirement_job',None):
            def dispose():
                self._retirement_job=None;started=time.perf_counter()
                while retired:
                    widget=retired.popleft()
                    if widget.winfo_exists():widget.destroy()
                    if time.perf_counter()-started>=.006:break
                if retired:self._retirement_job=self.after(8,dispose)
            self._retirement_job=self.after(8,dispose)
        self.schedule_viewport_restore()

    # สร้างพื้นที่เลื่อนพร้อมแถบเลื่อนสำหรับเนื้อหาที่ยาวกว่าหน้าต่าง
    def scroll_content(self, parent, native=False):
        holder = tk.Frame(parent, bg=WHITE)
        holder.pack(fill='both',expand=True,padx=6 if isinstance(parent,ctk.CTkFrame) else 0,pady=6 if isinstance(parent,ctk.CTkFrame) else 0)
        scroll = ttk.Scrollbar(holder,orient='vertical') if native else ctk.CTkScrollbar(holder,orientation='vertical',fg_color=WHITE,button_color='#ADB8C3',button_hover_color='#52697D')
        scroll.pack(side='right', fill='y')
        canvas = tk.Canvas(holder, bg=WHITE, highlightthickness=0, yscrollincrement=24)
        # อัปเดตแถบเลื่อนหลังจัดหน้าจอ ป้องกันการวาด CTk ซ้อนระหว่างปรับขนาด
        scroll_update={'pending':False,'values':('0','1')}
        def draw_scroll():
            from support.image_jobs import is_current
            values=scroll_update['values']
            if is_current(scroll) and scroll.winfo_exists():scroll.set(*values)
            scroll_update['pending']=False
            if values!=scroll_update['values'] and canvas.winfo_exists():queue_scroll(*scroll_update['values'])
        def queue_scroll(first,last):
            scroll_update['values']=(first,last)
            if not scroll_update['pending']:
                scroll_update['pending']=True;canvas.after_idle(draw_scroll)
        canvas.configure(yscrollcommand=queue_scroll)
        canvas.pack(fill='both', expand=True)
        scroll.configure(command=canvas.yview)
        content = tk.Frame(canvas, bg=WHITE)
        item = canvas.create_window((0, 0), window=content, anchor='nw')
        content.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(item, width=e.width))
        self._scroll_targets=getattr(self,'_scroll_targets',[])+[canvas]
        self.bind_all('<MouseWheel>',self.scroll_wheel)
        return content

    # ส่งการเลื่อนเมาส์ไปยังพื้นที่ที่ผู้ใช้กำลังชี้อยู่
    def scroll_wheel(self,event):
        if not event.delta:return
        units=(-1 if event.delta>0 else 1)*max(1,abs(int(event.delta/120)))
        alive=[c for c in getattr(self,'_scroll_targets',[]) if c.winfo_exists()]
        self._scroll_targets=alive
        widget=self.winfo_containing(event.x_root,event.y_root) or event.widget
        if widget.winfo_toplevel()!=event.widget.winfo_toplevel():widget=event.widget
        probe=widget
        while probe is not None:
            if probe in alive:
                probe.yview_scroll(units,'units');return
            probe=getattr(probe,'master',None)
        same=[c for c in alive if c.winfo_toplevel()==event.widget.winfo_toplevel()]
        if same:same[-1].yview_scroll(units,'units')

    # สร้างข้อความด้วยรูปแบบร่วมและปรับช่องว่างให้สม่ำเสมอ
    def label(self, p, text, size=11, bold=False, fg=INK, bg=None, **kw):
        from support.theme import clean_ui_text
        kw.setdefault('justify','left')
        label_font=('Tahoma',max(11,size),'bold' if bold else 'normal') if str(text).strip() in ('JPZ.','JPZ') else self.font(size,bold)
        return tk.Label(p, text=clean_ui_text(text), font=label_font, fg=fg, bg=bg or surface(p), **kw)

    # J33 | ข้อความแจ้งตรวจจดหมายขยะ
    def email_delivery_notice(self,parent,bg=None):
        # ใช้ข้อความเดียวกันในหน้ารับ OTP และใบเสร็จ โดยไม่หายเมื่อสถานะส่งเปลี่ยน
        label=self.label(parent,self.ui(
            'อีเมลอาจอยู่ในโฟลเดอร์สแปม/จดหมายขยะ (Spam/Junk) กรุณาตรวจสอบ หากพบให้เลือก “ไม่ใช่สแปม”',
            'The email may arrive in Spam/Junk. Please check that folder and mark it as “Not spam” if found.'),10,fg=MID,bg=bg,wraplength=420,justify='left')
        label._email_delivery_notice=True
        label.pack(anchor='w',pady=(8,12))
        return label

    # สร้างปุ่มด้วยรูปแบบร่วมของโปรแกรม
    def button(self, p, text, cmd, dark=False, compact=False):
        button=action(p,text,cmd,dark,compact)
        primary_texts={self.tr('shop_now'),self.tr('analyze'),self.tr('checkout'),self.ui('ชำระเงิน','Pay now')}
        admin_page=getattr(self,'_admin_screen_active',False) or str(getattr(self,'current_page','')).startswith('admin')
        if dark and text in primary_texts and not admin_page:
            # เน้นเฉพาะปุ่มหลัก ขยายตัวอักษรหนึ่งพิกเซลโดยคงกรอบและตำแหน่งปุ่ม
            font=button.cget('font');base_size=font.cget('size')
            button.configure(border_width=1,border_color='#243E55')
            button._user_primary_hover=True;button._primary_font_size=base_size
            def highlight(active):
                if button.cget('state')=='disabled' and active:return
                font.configure(size=base_size+1 if active else base_size)
                button.configure(border_color='#A89167' if active else '#243E55')
            button.bind('<Enter>',lambda event:highlight(True),add=True)
            button.bind('<Leave>',lambda event:highlight(False),add=True)
        return button

    # สร้างชื่อช่องกรอกและช่องกรอกข้อมูล
    def entry(self, p, label_text, show=None):
        self.label(p,label_text,11,True,fg=MID).pack(anchor='w',pady=(12,6))
        e=field(p,show=show)
        e.pack(fill='x')
        return e

    # อ่านข้อความจากตารางภาษาโดยใช้ชื่อรายการ
    def tr(self, key):
        return t(self.lang, key)

    # แปลงรหัสทรงยีนส์เป็นชื่อที่ผู้ใช้เข้าใจ
    def fit_label(self, key):
        if key=='any':return self.ui('ยังไม่มีทรงที่ชอบ','No preferred fit')
        return fit_name(self.lang, key)

    # แปลงรหัสสีเป็นชื่อสีของยีนส์
    def color_label(self, key):
        from support import product_colors
        custom=product_colors.custom_name(key)
        if custom:return custom
        display_key = COLOR_DISPLAY_ALIASES.get(key, key)
        return option_name(self.lang, display_key)

    # รวบรวมสีที่มีอยู่ของสินค้าแต่ละรุ่น
    def allowed_colors(self, fit):
        return FIT_COLOR_PALETTE.get(fit, ['dark_indigo', 'black', 'washed_blue'])

    # วาดโลโก้ตัวอักษร JPZ
    def brand_mark(self, parent, size=13, bg=None):
        return self.label(
            parent,
            'JPZ.',
            size,
            True,
            bg=bg or parent.cget('bg'),
        )

    # สร้างเส้นแบ่งเนื้อหาในหน้า
    def divider(self, parent, pady=(8, 8)):
        line = tk.Frame(parent, bg=LINE, height=1)
        line.pack(fill='x', pady=pady)
        return line

    # แสดงข้อความแจ้งผลสั้น ๆ แล้วซ่อนให้อัตโนมัติ
    def toast(self, text):
        toast = tk.Label(
            self,
            text=text,
            font=self.font(9, True),
            bg=INK,
            fg=WHITE,
            padx=18,
            pady=10,
        )
        toast.place(relx=0.5, rely=0.94, anchor='center')
        toast.lift()
        self.after(1800, toast.destroy)

    # สร้างข้อความแสดงสถานะรายการ
    def status_label(self, value):
        return self.tr({'waiting_payment': 'payment_waiting', 'under_review': 'payment_review', 'paid': 'payment_paid', 'rejected': 'payment_rejected', 'preparing': 'order_preparing', 'shipped': 'order_shipped', 'completed': 'order_completed'}.get(value, value))

    # ใช้คู่สีเดียวกันทุกหน้า พร้อมข้อความกำกับสำหรับผู้ที่แยกสีได้ยาก
    def status_colors(self,status):
        return {'waiting_payment':('#FFF1DC','#8B4C00'),'under_review':('#E4F3FF','#175D8A'),'paid':('#E3F5E9','#24633D'),'preparing':('#FFF1DC','#8B4C00'),'shipped':('#F0E8FF','#674192'),'completed':('#E3F5E9','#24633D'),'cancelled':('#FCE6E8','#9D2835'),'rejected':('#FCE6E8','#9D2835'),'refunded':('#FCE6E8','#9D2835')}.get(status,('#E9EEF3','#243E55'))

    # ให้สถานะยกเลิกหรือคืนเงินมาก่อนสถานะชำระเงินเดิม
    def order_status_key(self,order):
        if order['order_status'] in ('cancelled','refunded'):return order['order_status']
        if order['payment_status']=='paid':return order['order_status']
        return order['payment_status']

    # แยกป้ายการชำระเงินและการจัดส่งเพื่อไม่ให้ชำระแล้วถูกเข้าใจว่าส่งแล้ว
    def order_badges(self,parent,order):
        row=tk.Frame(parent,bg=parent.cget('bg'))
        states=[order['order_status']] if order['order_status'] in ('cancelled','refunded') else [order['payment_status']]
        if order['order_status'] in ('preparing','shipped','completed'):states.append(order['order_status'])
        for status in states:
            bg,fg=self.status_colors(status)
            badge=self.label(row,self.status_label(status),11,True,bg=bg,fg=fg,padx=10,pady=5)
            badge._order_status=status;badge.pack(side='left',padx=(0,8),pady=3)
        return row

    # เก็บประวัติหน้าและเรียกฟังก์ชันสร้างหน้าที่ต้องการ
    def navigate(self, name, func, *args, push=True, **kwargs):
        if push and self.current_page not in ('login', None):
            state=self.current_args.copy()
            if self.current_page=='shop':state['_shop_state']=(self.shop_fit,self.shop_style,getattr(self,'shop_page',0),getattr(self,'shop_sort','recommended'))
            self.page_history.append((self.current_page,state))
        self.current_page = name
        self.current_args = {'args': args, 'kwargs': kwargs}
        if self.user and self.user.get('role') == 'customer':
            admin_data.log_event(self.user['id'], 'page_view', name)
        func(*args, **kwargs)

    # กลับไปหน้าก่อนหน้าจากประวัติการเปิดหน้า
    def go_back(self):
        if not self.page_history:
            return self.home(push=False) if self.user else self.show_login(push=False)
        name, state = self.page_history.pop()
        self.current_page = name
        self.current_args = state
        if name=='shop' and '_shop_state' in state:
            saved=state['_shop_state']
            self.shop_fit,self.shop_style,self.shop_page=saved[:3]
            self.shop_sort=saved[3] if len(saved)>3 else 'recommended'
            self._shop_filter_signature=(self.shop_fit,self.shop_style,self.shop_sort)
        if self.user and self.user.get('role') == 'customer':
            admin_data.log_event(self.user['id'], 'page_view', name)
            self.current_args.pop('_viewed_product', None)
        self.render_page(name, *state.get('args', ()), **state.get('kwargs', {}))

    # จับคู่ชื่อหน้ากับฟังก์ชันที่แสดงหน้านั้น
    def render_page(self, name, *args, **kwargs):
        if name=='return':return self._return_page(*args,**kwargs)
        pages = {'home': self._home, 'shop': self._shop, 'product': self._product_detail, 'fit': self._fit_page, 'fit_results': self._fit_results, 'guide': self._size_guide, 'bag': self._bag, 'checkout': self._checkout, 'payment_result': self._payment_result, 'order_detail': self._order_detail, 'orders': self._orders, 'profile': self._profile, 'favorites': self._favorites, 'admin': self._admin, 'admin_stock': self._admin_stock, 'admin_profile': self._admin_profile, 'register': self.register_page_view, 'register_otp':self.register_otp_page, 'forgot_password':self.forgot_password_page, 'contact': self._contact}
        pages.get(name, self._home)(*args, **kwargs)

    # เปลี่ยนภาษา บันทึกภาษาของบัญชี และแสดงหน้าปัจจุบันใหม่
    # J59 | เปลี่ยนภาษาไทยและอังกฤษ
    def set_lang(self, lang):
        self.lang = lang
        if self.user:
            db.update_language(self.user['id'], lang)
            self.user['language'] = lang
        if self.current_page == 'login':
            self.show_login(push=False)
        else:
            self.render_page(self.current_page, *self.current_args.get('args', ()), **self.current_args.get('kwargs', {}))

    # สร้างปุ่มสลับภาษา TH และ EN
    def lang_switch(self,p):
        box=tk.Frame(p,bg=surface(p));box.pack(side='right',padx=12,pady=8)
        for lang in ('TH','EN'):
            self.button(box,lang,lambda value=lang:self.set_lang(value),dark=lang==self.lang,compact=True).pack(side='left',padx=2)

    # วาดแผงตกแต่งแบรนด์ด้านขวา
    def editorial_rail(self, parent):
        """Reference-style vertical graphic; each page uses its own denim wash."""
        palettes = {
            'home': ('#292929', '#94928b', '#4b4b48'),
            'shop': ('#234962', '#9bafbb', '#54788e'),
            'favorites': ('#182632', '#71818c', '#364957'),
            'product': ('#395d77', '#adbec8', '#6e8ba0'),
            'fit': ('#626f79', '#c1c7ca', '#8d989f'),
            'fit_results': ('#315b78', '#b1c3cf', '#7897aa'),
            'match': ('#486d87', '#b6cbd7', '#809eaf'),
            'guide': ('#788590', '#d5dce0', '#a7b2bb'),
            'bag': ('#202c38', '#8d9ca8', '#465868'),
            'checkout': ('#202c38', '#8d9ca8', '#465868'),
            'orders': ('#2c506e', '#a5b9c9', '#698ba5'),
            'profile': ('#526877', '#bcc7ce', '#899eac'),
        }
        colors = palettes.get(self.current_page, palettes['fit'])
        graphic = tk.Canvas(parent, bg='#f6f5f2', bd=0, highlightthickness=0)
        graphic.pack(fill='both', expand=True)
        def draw(event):
            graphic.delete('all')
            sx, sy = event.width / 280, event.height / 820
            scale = min(sx, sy)
            def line(points, color='#aaa9a5', width=1):
                graphic.create_line(*[v * (sx if i % 2 == 0 else sy) for i, v in enumerate(points)], fill=color, width=width)
            def text(x, y, value, size=12, bold=False, **kw):
                graphic.create_text(x*sx, y*sy, text=value, fill=kw.pop('fill', '#797975'), font=('Tahoma', -max(7, round(size*scale)), 'bold' if bold else 'normal'), **kw)
            # ใช้ลายกระดาษและเส้นตกแต่งตามภาพอ้างอิง
            for i in range(190):
                x, y = (i*73 % 280), (i*137 % 820)
                line([x, y, x+1, y+1], '#e5e3de')
            line([0, 0, 0, 820], '#dad8d2')
            line([40, 20, 40, 198])
            line([20, 90, 247, 310])
            line([0, 103, 132, 230])
            line([125, 215, 125, 400])
            line([40, 565, 40, 820])
            line([125, 535, 125, 652])
            line([125, 652, 21, 750])
            line([145, 562, 195, 562])
            text(159, 82, 'PREMIUM\nDENIM WEAR\nFOR EVERYDAY\n—', anchor='nw', justify='left')
            text(74, 391, 'JPZ / DENIM 2026', 35, True, angle=270, fill='#333331')
            # วาดลายทแยงของผ้าทวิลสำหรับตกแต่ง
            x0, y0, w, h = 141, 325, 104, 125
            graphic.create_rectangle(x0*sx, y0*sy, (x0+w)*sx, (y0+h)*sy, fill=colors[0], outline='')
            for offset in range(-h, w, 4):
                ax, ay = max(0, offset), max(0, -offset)
                bx, by = min(w, offset+h), min(h, w-offset)
                line([x0+ax, y0+ay, x0+bx, y0+by], colors[2], max(1, 1.5*scale))
                for step in range(0, int(min(bx-ax, by-ay)), 7):
                    px, py = ax+step, ay+step
                    line([x0+px, y0+py, x0+min(px+2,bx), y0+min(py+2,by)], colors[1])
            text(143, 474, 'FIT\nWASH\nIDENTITY\nLIFESTYLE', 13, anchor='nw', justify='left')
            text(159, 681, 'JPZ DENIM\n2026', 12, anchor='nw', justify='left')
            text(143, 760, 'DENIM MADE\nPERSONAL.', 11, anchor='nw', justify='left')
        graphic.bind('<Configure>', draw)
        return graphic

    # สร้างไอคอนโปรไฟล์วงกลมจากรูปของบัญชี กดแล้วเปิดข้อมูลบัญชี
    def profile_avatar_button(self,parent):
        from support.portraits import avatar
        image=avatar(BASE_DIR,self.user.get('avatar',''),size=144,active=self.current_page=='profile')
        icon=ctk.CTkImage(light_image=image,dark_image=image,size=(48,48))
        button=ctk.CTkButton(parent,text='',image=icon,command=self.profile,width=54,height=54,
                             corner_radius=27,border_spacing=0,fg_color=WHITE,hover_color='#E9EEF3',
                             bg_color=surface(parent),cursor='hand2')
        button._avatar_image=icon;button._profile_avatar=True
        self.profile_icon=button
        return button

    # สร้างส่วนหัว ไอคอนบัญชี เมนูหลัก และพื้นที่เนื้อหาของหน้าร้าน
    # J09 | ส่วนหัวและเมนู
    def shell(self, show_back=True):
        self._admin_screen_active=False
        self.clear()
        ivory='#F8F6F0';gold='#B8A88E'
        tk.Frame(self,bg=gold,height=2).pack(fill='x')
        top=ctk.CTkFrame(self,fg_color=ivory,corner_radius=0,height=84)
        top.pack(fill='x');top.pack_propagate(False)
        brand=tk.Frame(top,bg=ivory);brand.pack(side='left',padx=30,pady=10)
        logo=self.brand_mark(brand,30,bg=ivory);logo.configure(fg='#193244');logo.pack(side='left')
        tk.Frame(brand,bg=gold,width=1,height=38).pack(side='left',padx=18)
        signature=tk.Frame(brand,bg=ivory);signature.pack(side='left')
        self.label(signature,'PIZZA JEANS',10,True,fg='#243E55',bg=ivory).pack(anchor='w')
        self.label(signature,'DENIM MADE PERSONAL.',8,fg='#877354',bg=ivory).pack(anchor='w',pady=(3,0))
        self._shell_brand=logo
        # เส้นทองเข้มช่วงสั้นกลางส่วนหัว ตัดกับไอวอรี และวาดเมื่อขนาดเปลี่ยนเท่านั้น
        accent=tk.Canvas(top,bg=ivory,height=12,width=180,highlightthickness=0)
        accent.pack(side='left',fill='x',expand=True,padx=18)
        accent_line=accent.create_line(0,6,180,6,fill='#877354',width=2)
        def arrange_accent(event):
            length=min(180,max(0,event.width-12));left=max(0,(event.width-length)/2)
            accent.coords(accent_line,left,6,left+length,6)
        accent.bind('<Configure>',arrange_accent);self._shell_accent=accent
        self.lang_switch(top)
        self.profile_avatar_button(top).pack(side='right',padx=(10,6))
        self.button(top,self.tr('logout'),self.logout,compact=True).pack(side='right',padx=6)
        self.button(top,f"{self.tr('bag')} ({sum(self.cart.values())})",self.bag,dark=True,compact=True).pack(side='right',padx=6)
        if self.user['role']=='admin':
            self.button(top,self.ui('กลับหน้าแอดมิน','Back to Admin'),self.admin,compact=True).pack(side='right',padx=6)
        menu=ctk.CTkFrame(self,fg_color='#193244',corner_radius=0,height=60)
        menu.pack(fill='x');menu.pack_propagate(False)
        from support.denim_surface import texture
        menu_texture=tk.Canvas(menu,bg='#193244',highlightthickness=0)
        menu_texture.place(x=0,y=0,relwidth=1,relheight=1)
        menu_texture.tk.call('raise',str(menu_texture),str(menu._canvas));texture(self,menu_texture)
        nav=[('home',self.home),('collection',self.shop),('find_fit',self.fit_page),('size_guide',self.size_guide),('orders',self.my_orders),('favorites',self.favorites),('contact',self.contact)]
        groups={'shop':'collection','product':'collection','fit':'find_fit','fit_results':'find_fit','guide':'size_guide','order_detail':'orders','payment_result':'orders'}
        active=groups.get(self.current_page,self.current_page)
        nav_buttons=[self.button(menu,self.tr(key),cmd,dark=key==active,compact=True) for key,cmd in nav]
        for (key,_),button in zip(nav,nav_buttons):
            button.configure(fg_color=ivory if key==active else '#243E55',text_color='#193244' if key==active else '#F8F6F0',border_color=gold if key==active else '#536978',border_width=1,hover_color='#E7E0D3' if key==active else '#355873',bg_color='#193244')
        self._shell_nav=nav_buttons
        layout=[None]
        def arrange(event):
            available=max(400,event.width/menu._get_widget_scaling()-36);x,y=18,10;rows=1
            for item in nav_buttons:
                width=int(item.cget('width'))+10
                if x+width>available and x>18:x=18;y+=44;rows+=1
                item.place(x=x,y=y);x+=width
            if layout[0]!=rows:layout[0]=rows;menu.configure(height=rows*44+14)
        menu.bind('<Configure>',arrange)
        tk.Frame(self,bg=LINE,height=1).pack(fill='x')
        body=tk.Frame(self,bg=WHITE);body.pack(fill='both',expand=True)
        if self.current_page not in ('home','shop','product','favorites','chat'):
            rail=tk.Frame(body,bg=WHITE,width=125);rail.pack(side='right',fill='y',padx=(10,18),pady=16);rail.pack_propagate(False)
            self.editorial_rail(rail)
        if show_back and self.page_history:
            self.button(body,self.tr('back'),self.go_back,compact=True).pack(anchor='w',padx=30,pady=(12,0))
        return body

    # เปิดหน้าแรกผ่านระบบเปลี่ยนหน้า
    def home(self, push=True):
        self.navigate('home', self._home, push=push)

    # สร้างภาพแบรนด์ สินค้า และแผงตกแต่งหน้าแรก พร้อมการเลื่อน
    # J10 | หน้าแรก
    def _home(self):
        """JPZ image-led editorial Home page.

        The entire page is rendered on one Canvas so scrolling is reliable from
        every point on the window and visual sections never collapse/clamp when
        the outer page is scrolled.
        """
        b = self.shell(show_back=False)
        b.configure(bg=WHITE)
        self.promotion_banner(b)

        # แถบเอกลักษณ์ด้านข้างของหน้าแรกคงอยู่บนหน้าจอ
        # ขณะเลื่อนเนื้อหา เพื่อเติมพื้นที่ขอบขวาของหน้าต่าง
        # หน้าอื่นยังใช้แถบด้านข้างตามรูปแบบของหน้านั้น
        home_rail = tk.Frame(b, bg=WHITE, width=170, highlightbackground=LINE, highlightthickness=1)
        home_rail.pack(side='right', fill='y')
        home_rail.pack_propagate(False)

        canvas = tk.Canvas(b, bg='#D3D5D7', highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(b, orient='vertical', command=canvas.yview,
                                 width=7, troughcolor=WHITE, bg='#BDBDBD',
                                 activebackground=INK)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        self._home_canvas = canvas

        # เก็บตัวอ้างอิงภาพไว้ตลอดอายุหน้าแรก ป้องกันภาพหาย
        self.home_hero_image = None
        self.home_new_image = None
        self.home_fit_image = None
        self.home_product_images = []

        def wheel(event):
            if self.current_page != 'home':
                return
            if event.num == 4:
                canvas.yview_scroll(-4, 'units')
            elif event.num == 5:
                canvas.yview_scroll(4, 'units')
            elif event.delta:
                units = max(1, abs(event.delta) // 60)
                canvas.yview_scroll(-units if event.delta > 0 else units, 'units')

        # รับการหมุนล้อเมาส์แม้อยู่เหนือปุ่มหรือภาพ
        # รวมถึงข้อความและพื้นที่ว่างในหน้าจอ
        for sequence in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            try:
                self.unbind_all(sequence)
            except tk.TclError:
                pass
            self.bind_all(sequence, wheel, add='+')

        W = 1500
        H = 3000
        canvas.configure(scrollregion=(0, 0, W, H))

        def rect(x1, y1, x2, y2, fill=WHITE, outline=LINE):
            return canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=1)

        def text(x, y, value, size=10, bold=False, fill=INK, anchor='nw', width=None):
            opts = {'font': self.font(size, bold), 'fill': fill, 'anchor': anchor}
            if width:
                opts['width'] = width
            return canvas.create_text(x, y, text=value, **opts)

        pending_home_images={}
        home_image_timer=[None]
        def visible_home_images():
            if not canvas.winfo_exists():return
            top=canvas.canvasy(0)-550;bottom=canvas.canvasy(canvas.winfo_height())+550
            for slot,(y,load,apply) in list(pending_home_images.items()):
                if top<=y<=bottom:
                    from support import image_jobs
                    image_jobs.submit(self,canvas,load,apply);del pending_home_images[slot]
            home_image_timer[0]=canvas.after(160,visible_home_images)
        home_image_timer[0]=canvas.after(30,visible_home_images)
        def stop_home_images(event):
            if event.widget is canvas and home_image_timer[0]:
                try:canvas.after_cancel(home_image_timer[0])
                except tk.TclError:pass
        canvas.bind('<Destroy>',stop_home_images,add='+')
        curve_state={'path':([],[]),'items':()}
        def image(path, x, y, anchor='nw', attribute=None, tags=(), fit=None, trace=False):
            if not path.exists():
                return None
            # จองตำแหน่งภาพก่อน เพื่อให้ข้อความยังอยู่เหนือภาพเมื่อโหลดเสร็จ
            slot=canvas.create_image(x,y,anchor=anchor,tags=tags)
            def load():
                with Image.open(path) as original:
                    result=original.convert('RGBA')
                    result=ImageOps.fit(result,fit,method=Image.Resampling.LANCZOS,centering=(.5,.28)) if fit else result
                    if trace:
                        from support.home_motion import trace_curve
                        return result,trace_curve(result,(x,y))
                    return result
            def apply(result):
                if result is None:return
                if trace:
                    result,curve_state['path']=result
                    from support.home_motion import prepare_walker
                    prepare_walker(self,canvas,curve_state['walker'],curve_state['path'])
                photo=ImageTk.PhotoImage(result,master=self);self.home_product_images.append(photo)
                if attribute:setattr(self,attribute,photo)
                canvas.itemconfigure(slot,image=photo)
            pending_home_images[slot]=(y,load,apply)
            return slot

        # ==============================================================
        # 01 / DENIM FOR YOU — language-safe hero
        # ==============================================================
        rect(14, 14, 1306, 654, '#C4C6C8', LINE)
        text(42, 42, self.tr('home_section_denim'), 9, True, MID)
        text(42, 100, self.tr('hero'), 32, True, INK, width=450)
        # วางคำอธิบายและปุ่มใต้หัวเรื่องสองบรรทัดในทั้งสองภาษา
        # ป้องกันตำแหน่งคงที่ทับหัวเรื่องภาษาอังกฤษ
        hero_sub_y = 340 if self.lang == 'EN' else 280
        # เก็บประโยคภาษาอังกฤษให้ครบในคอลัมน์ข้อความหลัก
        hero_sub_font = tkfont.Font(self, font=self.font(13))
        self._hero_sub_font = hero_sub_font
        while hero_sub_font.measure(self.tr('hero_sub')) > 385 and hero_sub_font.cget('size') > 10:
            hero_sub_font.configure(size=hero_sub_font.cget('size') - 1)
        canvas.create_text(42, hero_sub_y, text=self.tr('hero_sub'), font=hero_sub_font,
                           fill='#333333', anchor='nw', tags='home_hero_subtitle')

        shop_btn = self.button(canvas,self.tr('shop_now'),self.shop,dark=True,compact=True)
        shop_btn.configure(fg_color=INK,corner_radius=0)
        canvas.create_window(42, 390 if self.lang == 'EN' else 345, anchor='nw', window=shop_btn)
        text(42, 566, self.tr('home_footer_code'), 9, True, INK)
        text(42, 588, self.tr('home_footer_tagline'), 8, False, MID)
        text(42, 618, self.tr('home_scroll'), 7, True, MID)

        hero_path = ASSET_DIR / 'home_hero_model_display.png'
        self.home_hero_image = None
        image(hero_path,445,18,attribute='home_hero_image')

        curve_path = ASSET_DIR / 'hero_curve_smooth.png'
        self.home_curve_image = None
        image(curve_path,42,420,attribute='home_curve_image',trace=True)

        # แบบที่ผู้ใช้เลือก: แถบแบรนด์งาช้าง ตัวอักษรเข้ม และเส้นทองหม่น
        canvas.create_rectangle(847,18,919,640,fill='#F8F6F0',outline='',tags='home_middle_decor')
        canvas.create_line(847,18,919,18,fill='#B8A88E',width=2,tags='home_middle_decor')
        canvas.create_line(847,640,919,640,fill='#B8A88E',width=2,tags='home_middle_decor')
        middle_label=canvas.create_text(883,329,text='JPZ / DENIM',angle=270,font=('Georgia',23,'bold'),fill='#203447',tags='home_middle_decor')

        # แผงโปรโมชันด้านขวาและภาพยีนส์โทนดำด้านล่าง
        # จัดภาพทั้งสองไว้ด้วยกันเพื่อใช้พื้นที่หน้าแรกให้ครบ
        # และเติมพื้นที่ด้านขวาล่าง
        promo_x1, promo_y1, promo_x2, promo_y2 = 955, 18, 1290, 486
        rect(promo_x1, promo_y1, promo_x2, promo_y2, SOFT, LINE)
        special_rows=admin_data.query(self.user['id'],"SELECT p.* FROM products p JOIN product_promotions offer ON offer.product_id=p.id WHERE p.active=1 AND offer.enabled=1 AND offer.kind='price' ORDER BY p.id") if self.user['role']=='admin' else []
        if self.user['role']!='admin':
            c=db.conn()
            try:special_rows=[dict(row) for row in c.execute("SELECT p.* FROM products p JOIN product_promotions offer ON offer.product_id=p.id WHERE p.active=1 AND offer.enabled=1 AND offer.kind='price' ORDER BY p.id")]
            finally:c.close()
        from support import product_colors,image_jobs
        special_rows=[p for p in special_rows if product_colors.keys(p['id'])]
        text(promo_x1+22,promo_y1+24,self.ui('02 / สินค้าราคาพิเศษ','02 / SPECIAL PRICES'),9,True,'#8C2635')
        heading=canvas.create_text(promo_x1+22,promo_y1+62,text='',font=self.font(13,True),fill=INK,anchor='nw',width=290)
        prices=canvas.create_text(promo_x1+22,promo_y1+130,text='',font=self.font(14,True),fill='#8C2635',anchor='nw',width=290)
        count_text=canvas.create_text(promo_x2-22,promo_y1+26,text='',font=self.font(10),fill=MID,anchor='ne')
        image_slot=canvas.create_image(promo_x1+22,promo_y1+184,anchor='nw',tags='home_promo_photo')
        position=[0];generation=[0];self.home_new_promo_image=None
        def open_special():
            if special_rows:self.product_detail(special_rows[position[0]])
        promo_btn=self.button(canvas,self.ui('ดูสินค้าราคาพิเศษ','VIEW SPECIAL PRICE'),open_special,dark=True,compact=True)
        promo_btn.configure(fg_color='#8C2635',corner_radius=0)
        self._home_promotion_button=promo_btn
        canvas.create_window(promo_x1+22,promo_y2-60,anchor='nw',window=promo_btn,width=promo_x2-promo_x1-44,height=40,tags='home_promo_button')
        def render_special():
            generation[0]+=1;version=generation[0]
            if not special_rows:
                canvas.itemconfigure(heading,text=self.ui('เดนิมที่เข้ากับคุณ','FIND YOUR FIT.'))
                canvas.itemconfigure(prices,text=self.ui('ค้นหาทรงที่ใช่ ในสไตล์ของคุณ','Find your fit. Make it yours.'),font=self.font(11),fill=MID)
                promo_btn.configure(text=self.ui('ดูสินค้าทั้งหมด','EXPLORE DENIM'),command=self.shop,state='normal',bg='#243E55')
                def load_fallback():
                    with Image.open(ASSET_DIR/'home_new_panel.png') as image:return ImageOps.pad(image.convert('RGB'),(291,202),color=SOFT,method=Image.Resampling.LANCZOS)
                def apply_fallback(image):
                    if image is not None and version==generation[0]:
                        self.home_new_promo_image=ImageTk.PhotoImage(image,master=self);canvas.itemconfigure(image_slot,image=self.home_new_promo_image)
                image_jobs.submit(self,canvas,load_fallback,apply_fallback);return
            product=special_rows[position[0]];offer=product_promotions.setting(product['id'])
            canvas.itemconfigure(heading,text=product['name']);canvas.itemconfigure(prices,text=f"฿{offer['value']:,.2f}")
            canvas.itemconfigure(count_text,text=f"{position[0]+1} / {len(special_rows)}");canvas.itemconfigure(image_slot,image='')
            def load():
                image=gallery_assets.source(product['id'],product['color'],'FRONT',fallback=True)
                return ImageOps.pad(image.convert('RGB'),(291,202),color=SOFT,method=Image.Resampling.LANCZOS) if image is not None else None
            def apply(image):
                if image is not None and version==generation[0]:
                    self.home_new_promo_image=ImageTk.PhotoImage(image,master=self);canvas.itemconfigure(image_slot,image=self.home_new_promo_image)
            image_jobs.submit(self,canvas,load,apply)
        def step_special(delta):position[0]=(position[0]+delta)%len(special_rows);render_special()
        if len(special_rows)>1:
            for x,label,delta in [(promo_x1+5,'‹',-1),(promo_x2-39,'›',1)]:
                arrow=tk.Button(canvas,text=label,command=lambda d=delta:step_special(d),font=self.font(18,True),bg=WHITE,fg='#8C2635',bd=0,cursor='hand2')
                canvas.create_window(x,promo_y1+260,anchor='nw',window=arrow,width=34,height=44)
        self._home_special_ui=dict(products=special_rows,position=position,next=lambda:step_special(1),previous=lambda:step_special(-1),canvas=canvas,heading=heading,prices=prices)
        render_special()

        # แถบด้านข้างคงอยู่โดยไม่ขึ้นกับตำแหน่งเลื่อนหน้าแรก
        self.editorial_rail(home_rail)

        # ใช้ภาพยีนส์โทนดำไม่เห็นใบหน้าที่อนุมัติไว้ใต้ส่วน 02
        lower_promo_path = ASSET_DIR / 'home_find_fit.png'
        self.home_lower_promo_image = None
        image(lower_promo_path,955,500,attribute='home_lower_promo_image',tags=('home_lower_promo_photo',),fit=(335,140))

        # ==============================================================
        # 02 / NEW DENIM — fixed product frames + language-safe copy
        # ==============================================================
        rect(14, 680, 1306, 1170, WHITE, LINE)
        text(42, 705, self.tr('home_new_section'), 9, True, MID)
        # Break at whole Thai words instead of splitting the word "ใหม่".
        title_size = 18 if self.lang == 'TH' else 25
        collection_title=self.ui('ยีนส์\nคอลเลกชันใหม่','NEW\nDENIM')
        collection_font=tkfont.Font(self,font=self.font(title_size,True))
        while max(collection_font.measure(line) for line in collection_title.splitlines())>235:collection_font.configure(size=collection_font.cget('size')-1)
        collection_heading=canvas.create_text(42,735,text=collection_title,font=collection_font,fill=INK,anchor='nw',tags='new_denim_heading')
        collection_copy_text=self.ui('คอลเลกชันใหม่ที่ออกแบบ\nให้เข้ากับทุกทรง','A new collection designed\nfor every silhouette.')
        copy_font=tkfont.Font(self,font=self.font(11))
        while max(copy_font.measure(line) for line in collection_copy_text.splitlines())>235:copy_font.configure(size=copy_font.cget('size')-1)
        collection_copy=canvas.create_text(42,canvas.bbox(collection_heading)[3]+22,text=collection_copy_text,font=copy_font,fill=MID,anchor='nw',tags='new_denim_copy')
        view_all = self.button(canvas,self.tr('view_all'),self.shop,dark=True,compact=True)
        view_all.configure(fg_color=INK,corner_radius=0)
        # เว้นระยะใต้คำอธิบายคอลเลกชันก่อนแสดงปุ่มเลือกสินค้า
        canvas.create_window(42, max(860, canvas.bbox(collection_copy)[3] + 28), anchor='nw', window=view_all,tags='home_collection_button')

        from support import home_collection
        cards_frame=tk.Frame(canvas,bg=WHITE)
        canvas.create_window(300,700,anchor='nw',window=cards_frame,width=1000,height=510,tags='home_collection_cards')
        card_canvas=tk.Canvas(cards_frame,bg=WHITE,highlightthickness=0)
        horizontal=ctk.CTkScrollbar(cards_frame,orientation='horizontal',command=card_canvas.xview,fg_color=WHITE,button_color='#ADB8C3')
        horizontal.pack(side='bottom',fill='x');card_canvas.pack(fill='both',expand=True)
        card_canvas.configure(xscrollcommand=horizontal.set)
        cards_holder=tk.Frame(card_canvas,bg=WHITE);card_canvas.create_window(0,0,anchor='nw',window=cards_holder)
        cards_holder.bind('<Configure>',lambda event:card_canvas.configure(scrollregion=card_canvas.bbox('all')))
        self._home_collection_ui={'canvas':card_canvas,'cards':[],'buttons':[]}
        for index,(config,product) in enumerate(home_collection.visible()):
            cell=tk.Frame(cards_holder,bg=WHITE,highlightbackground=LINE,highlightthickness=1,width=235,height=425)
            cell.pack(side='left',padx=(0,15));cell.pack_propagate(False)
            picture=home_collection.picture(config)
            image_holder=tk.Label(cell,bg=PANEL,width=205,height=250)
            image_holder.place(x=15,y=14,width=205,height=250)
            if picture is not None:
                framed=ImageOps.pad(picture.convert('RGB'),(205,250),color=PANEL,method=Image.Resampling.LANCZOS)
                photo=ImageTk.PhotoImage(framed,master=self);image_holder.configure(image=photo);image_holder._image=photo
            else:image_holder.configure(text=self.ui('ยังไม่มีรูปสินค้า','Product photo unavailable'),font=self.font(11),wraplength=180)
            special=product_promotions.setting(product['id'])
            if special['enabled'] and special['kind']=='price':tk.Label(cell,text=self.ui('ราคาพิเศษ','SPECIAL PRICE'),font=self.font(9,True),bg='#8C2635',fg='white',padx=8,pady=4).place(x=20,y=20)
            title=config.get('title') or product['name']
            title_font=tkfont.Font(self,font=self.font(11,True))
            # แสดงหัวเรื่องให้ครบโดยไม่ตัดคำภาษาไทย
            words=title.split();lines=['']
            for word in words:
                joined=(lines[-1]+' '+word).strip()
                if lines[-1] and title_font.measure(joined)>205:lines.append(word)
                else:lines[-1]=joined
            if len(lines)>2:lines=[title]
            while max(title_font.measure(line) for line in lines)>205 and title_font.cget('size')>7:title_font.configure(size=title_font.cget('size')-1)
            title_label=tk.Label(cell,text='\n'.join(lines),font=title_font,bg=WHITE,fg=INK,justify='left',anchor='nw')
            title_height=max(48,title_font.metrics('linespace')*len(lines)+4)
            title_label.place(x=15,y=279,width=205,height=title_height)
            price_y=279+title_height
            line_height=max(24,tkfont.Font(self,font=self.font(11)).metrics('linespace')+4)
            offer=product_promotions.cart_quote({(product['id'],product['color'],32):1},self.user['id'])
            price=offer['total']
            price_line=tk.Frame(cell,bg=WHITE);price_line.place(x=15,y=price_y,width=205,height=line_height)
            if offer['discount_amount']:
                old_font=tkfont.Font(self,font=self.font(10));old_font.configure(overstrike=1)
                old=tk.Label(price_line,text=f"฿{offer['subtotal']:,.0f}",font=old_font,bg=WHITE,fg=MID);old._price_font=old_font;old.pack(side='left',padx=(0,8))
            tk.Label(price_line,text=f"฿{price:,.0f}" if float(price).is_integer() else f"฿{price:,.2f}",font=self.font(11,True),bg=WHITE,fg='#BB2020' if offer['discount_amount'] else INK,anchor='w').pack(side='left')
            tk.Label(cell,text=self.ui('ก่อน VAT ','Before VAT ')+f"฿{db.vat_breakdown(price)['before_vat']:,.2f}",font=self.font(11),bg=WHITE,fg=MID,anchor='w').place(x=15,y=price_y+line_height,width=205,height=line_height)
            button_y=price_y+line_height*2+8
            button_height=max(44,line_height+12)
            cell.configure(height=button_y+button_height+14)
            button_holder=tk.Frame(cell,bg=WHITE);button_holder.place(x=15,y=button_y,width=205,height=button_height)
            button=self.button(button_holder,self.tr('view_product'),lambda product=product:self.product_detail(product),compact=True)
            button.pack(fill='both',expand=True)
            self._home_collection_ui['cards'].append(dict(config=config,product=product,frame=cell,title=title_label))
            self._home_collection_ui['buttons'].append(button)
        if not self._home_collection_ui['cards']:
            tk.Label(cards_holder,text=self.ui('ยังไม่มีสินค้าในคอลเลกชันนี้','No collection products yet'),font=self.font(14),bg=WHITE,fg=MID).pack(padx=24,pady=160)

        # ==============================================================
        # 03 / FIND MY FIT — dark editorial image, no face, no baked copy
        # ==============================================================
        rect(14, 1192, 1306, 1620, INK, INK)

        # เตรียมภาพจากต้นฉบับโทนดำไม่เห็นใบหน้าที่อนุมัติไว้
        # ตัดข้อความที่ติดมากับภาพเพื่อแสดงข้อความตามภาษาที่เลือก
        fit_bg_path = ASSET_DIR / 'home_find_fit_bg.png'
        self.home_fit_image_large = None
        image(fit_bg_path,546,1192,attribute='home_fit_image_large')

        # จัดข้อความไว้ในคอลัมน์ด้านซ้ายโดยเฉพาะ
        # ป้องกันภาพทับข้อความหรือข้อความหายเมื่อสลับภาษา
        text(42, 1220, self.tr('home_find_section'), 9, True, '#AFAFAF')
        fit_heading = text(42, 1260, self.tr('home_find_title'), 30, True, WHITE, width=455)
        fit_copy = text(42, canvas.bbox(fit_heading)[3] + 24, self.tr('home_find_sub'), 9, False, '#AFAFAF', width=430)
        fit_btn2 = tk.Button(canvas, text=self.tr('start_fit'), command=self.fit_page,
                             font=self.font(9, True), bg=WHITE, fg=INK, bd=0,
                             cursor='hand2', padx=18, pady=9)
        canvas.create_window(42, canvas.bbox(fit_copy)[3] + 28, anchor='nw', window=fit_btn2)

        # ==============================================================
        # 04 / EXPLORE FITS — four equal full-background editorial cards
        # ==============================================================
        rect(14, 1642, 1306, 2255, WHITE, WHITE)
        text(42, 1666, self.tr('home_explore_section'), 9, True, MID)
        explore_heading = text(42, 1696, self.tr('home_explore_title'), 24, True, INK, width=1200)
        text(42, canvas.bbox(explore_heading)[3] + 12, self.tr('home_explore_sub'), 9, False, MID, width=1200)

        fit_cards = [
            ('BAGGY', self.tr('fit_card_baggy_desc'), 'baggy', 'explore_baggy_bg.png'),
            ('STRAIGHT', self.tr('fit_card_straight_desc'), 'straight', 'explore_straight_bg.png'),
            ('WIDE', self.tr('fit_card_wide_desc'), 'wide', 'explore_wide_bg.png'),
            ('CARGO', self.tr('fit_card_cargo_desc'), 'cargo', 'explore_cargo_bg.png'),
        ]

        card_y = 1802
        card_w = 295
        card_h = 400
        gap = 20
        for idx, (title, desc, fit_key, bg_name) in enumerate(fit_cards):
            x = 42 + idx * (card_w + gap)
            path = ASSET_DIR / bg_name
            rect(x, card_y, x + card_w, card_y + card_h, INK, INK)
            image(path,x,card_y)

            # ใช้ขอบภาพบางเพื่อให้การ์ดทั้งสี่มีลักษณะสม่ำเสมอ
            canvas.create_rectangle(x, card_y, x + card_w, card_y + card_h, outline=LINE, width=1)
            text(x + 20, card_y + 22, f'0{idx + 1}', 9, True, WHITE)
            text(x + 20, card_y + 70, title, 22, True, WHITE, width=250)
            canvas.create_line(x + 20, card_y + 112, x + 54, card_y + 112, fill=WHITE, width=2)
            text(x + 20, card_y + 132, desc, 9, False, WHITE, width=175)
            btn = tk.Button(
                canvas,
                text=self.tr('home_explore'),
                command=lambda f=fit_key: self.set_shop_fit_and_open(f),
                font=self.font(8, True), bg=WHITE, fg=INK,
                activebackground=WHITE, activeforeground=INK,
                bd=0, cursor='hand2', padx=13, pady=8
            )
            canvas.create_window(x + 20, card_y + card_h - 58, anchor='nw', window=btn)

        # ==============================================================
        # 05 / THE DENIM CODE — equal blocks + fixed image frames
        # ==============================================================
        rect(14, 2258, 1306, 2678, WHITE, LINE)
        text(42, 2282, self.tr('home_code_section'), 9, True, MID)
        code_heading = text(42, 2310, self.tr('home_code_title'), 28, True, INK, width=1200)
        # เว้นระยะคำอธิบายทั้งภาษาไทยและภาษาอังกฤษ
        # จากหัวเรื่องทรง สีฟอก และเอกลักษณ์ของสินค้า
        text(42, canvas.bbox(code_heading)[3] + 12, self.tr('home_code_fit'), 8, False, MID, width=560)

        code_items = [
            ('01 / FIT', self.tr('home_code_fit'), 'baggy_denim.png'),
            ('02 / WASH', self.tr('home_code_wash'), 'straight_denim.png'),
            ('03 / IDENTITY', self.tr('home_code_identity'), 'cargo_denim.png'),
        ]
        code_y = 2405
        code_w = 385
        code_h = 230
        code_gap = 25
        code_img_w = 155
        code_img_h = 170

        for idx, (title, desc, filename) in enumerate(code_items):
            x = 42 + idx * (code_w + code_gap)
            rect(x, code_y, x + code_w, code_y + code_h, SOFT, LINE)
            text(x + 15, code_y + 18, title, 10, True, INK)

            # ใช้กรอบภาพขนาดเท่ากันทั้งสามส่วน
            frame_x = x + code_w - code_img_w - 12
            frame_y = code_y + 45
            canvas.create_rectangle(
                frame_x, frame_y,
                frame_x + code_img_w, frame_y + code_img_h,
                fill=PANEL, outline=LINE, width=1
            )
            fixed_code_images = {
                'baggy_denim.png': 'home_code_fit.png',
                'straight_denim.png': 'home_code_wash.png',
                'cargo_denim.png': 'home_code_identity.png',
            }
            path = ASSET_DIR / fixed_code_images[filename]
            image(path,frame_x+code_img_w//2,frame_y+code_img_h//2,anchor='center')

            # วางคำอธิบายด้านซ้าย ป้องกันภาพทับข้อความ
            caption = text(x + 15, code_y + 195, desc, 8, False, MID, width=185)
            bounds = canvas.bbox(caption)
            canvas.move(caption, 0, code_y + code_h - 22 - bounds[3])

        # ==============================================================
        # 06 / สินค้าที่ดูล่าสุด
        # ==============================================================
        rect(14, 2680, 1306, 2980, WHITE, WHITE)
        text(42, 2708, '06 / ' + self.tr('recently_viewed'), 9, True, MID)
        recent = db.recent_products(self.user['id'], 4)
        if recent:
            for idx, item in enumerate(recent):
                x = 42 + idx * 315
                rect(x, 2745, x + 295, 2920, SOFT, LINE)
                recent_title = text(x + 14, 2762, item['name'], 9, True, INK, width=267)
                recent_fit = text(x + 14, canvas.bbox(recent_title)[3] + 12, self.fit_label(item['fit']), 8, False, MID, width=267)
                btn = tk.Button(canvas, text=self.tr('view_product'),
                                command=lambda product=item: self.product_detail(product),
                                font=self.font(7, True), bg=WHITE, fg=INK,
                                highlightthickness=1, highlightbackground=LINE,
                                bd=0, cursor='hand2', padx=10, pady=5)
                canvas.create_window(x + 14, max(2830, canvas.bbox(recent_fit)[3] + 16), anchor='nw', window=btn)
        else:
            text(42, 2770, 'YOUR NEXT FIT STARTS HERE', 12, True, MID)
            text(42, 2805, self.ui('เลือกยีนส์ที่ชอบ แล้วรายการล่าสุดของคุณจะปรากฏตรงนี้','Explore the jeans you like. Your recently viewed products will appear here.'), 9, False, MID,width=1150)

        self._home_extension_images=[]
        extension_assets=list(zip(db.products()[:3],('DETAIL','TEXTURE','DETAIL')))
        extension_size=[None]
        def decorate_spare_space(event):
            width=event.width
            if width==extension_size[0]:return
            extension_size[0]=width;canvas.delete('home_extension');self._home_extension_images=[]
            left=1318;available=width-left-14
            if available<90:return
            options={'tags':'home_extension'}
            canvas.create_rectangle(left,14,width-14,H-14,fill='#F8F6F0',outline='#DDD6C8',**options)
            center=left+available/2
            canvas.create_text(center,48,text='JPZ.',font=self.font(min(32,max(16,int(available/8))),True),fill='#203447',**options)
            canvas.create_text(center,99,text='DENIM MADE PERSONAL.',font=self.font(11,True),fill='#786D5B',width=max(70,available-28),justify='center',**options)
            canvas.create_line(left+18,145,width-32,145,fill='#B8A88E',**options)
            if extension_assets:
                for index,y in enumerate((174,804,1434,2064)):
                    target=(max(30,available-28),480)
                    slot=canvas.create_image(left+14,y,anchor='nw',**options)
                    product,view=extension_assets[index%len(extension_assets)]
                    def prepare(p=product,v=view,size=target):
                        picture=gallery_assets.preview(p['id'],p['color'],v)
                        return ImageOps.fit(picture,size,method=Image.Resampling.LANCZOS) if picture is not None else None
                    def display(picture,item=slot,render_width=width):
                        if picture is None or extension_size[0]!=render_width:return
                        photo=ImageTk.PhotoImage(picture,master=self);self._home_extension_images.append(photo);canvas.itemconfigure(item,image=photo)
                    image_jobs.submit(self,canvas,prepare,display)
                    canvas.create_text(center,y+516,text=('THE DETAILS','THE WASH','THE FIT','YOUR IDENTITY')[index],font=self.font(13,True),fill='#203447',width=max(70,available-28),justify='center',**options)
                    canvas.create_line(left+18,y+554,width-32,y+554,fill='#B8A88E',**options)
            canvas.create_text(center,2750,text='WEAR IT.\nMAKE IT YOURS.',font=self.font(16,True),fill='#203447',width=max(70,available-28),justify='center',**options)
            canvas.configure(scrollregion=(0,0,max(W,width),H))
        canvas.bind('<Configure>',decorate_spare_space)
        canvas.yview_moveto(0.0)
        # ตัวหนังสืออยู่นิ่ง ขยับเส้นและแสงด้วยพิกัด ไม่อ่านหรือย่อภาพซ้ำทุกเฟรม
        import math,time
        from support.image_jobs import is_current
        accent=canvas.create_line(855,38,855,110,fill='#B8A88E',width=2,tags='home_motion')
        accent_bottom=canvas.create_line(911,566,911,638,fill='#B8A88E',width=2,tags='home_motion')
        from support.home_motion import segment,create_walker,move_walker,LOOP_SECONDS
        trail_soft=canvas.create_line(0,0,0,0,fill='#B8A88E',width=5,capstyle='round',state='hidden',tags='home_motion')
        trail=canvas.create_line(0,0,0,0,fill='#F8F6F0',width=2.5,capstyle='round',state='hidden',tags='home_motion')
        curve_state['items']=(trail_soft,trail)
        curve_state['walker']=create_walker(canvas)
        motion=dict(canvas=canvas,label=middle_label,accent=accent,accent_bottom=accent_bottom,curve=curve_state,active=True,timer=None,frames=0)
        self._home_motion_ui=motion;started=time.monotonic()
        def stop_motion(event=None):
            if event is not None and event.widget is not canvas:return
            motion['active']=False
            if motion['timer']:
                try:canvas.after_cancel(motion['timer'])
                except tk.TclError:pass
                motion['timer']=None
        # J11 | เส้นขยับบนหน้าแรก
        def animate():
            motion['timer']=None
            if not is_current(canvas) or not canvas.winfo_exists():stop_motion();return
            # ลดความถี่เมื่อเลื่อนพ้นส่วนแรกหรือย่อหน้าต่าง
            visible=canvas.winfo_ismapped() and canvas.canvasy(0)<700 and self.state()!='iconic'
            if visible:
                phase=(time.monotonic()-started)*math.tau/7
                y=38+(1-math.cos(phase))*245
                canvas.coords(accent,855,y,855,y+72)
                lower=604-y
                canvas.coords(accent_bottom,911,lower,911,lower+72)
                path=curve_state['path']
                if path[0]:
                    elapsed=time.monotonic()-started
                    head=(elapsed%12)/12*path[1][-1]
                    stroke=segment(path,head)
                    for item in curve_state['items']:
                        if stroke:canvas.coords(item,*stroke);canvas.itemconfigure(item,state='normal')
                        else:canvas.itemconfigure(item,state='hidden')
                    walker_time=(elapsed%LOOP_SECONDS)/LOOP_SECONDS*path[1][-1]
                    move_walker(canvas,curve_state['walker'],path,walker_time,elapsed*math.tau/.85)
                motion['frames']+=1
            motion['timer']=canvas.after(33 if visible else 200,animate)
        canvas.bind('<Destroy>',stop_motion,add='+')
        motion['timer']=canvas.after(33,animate)

    # เลือกทรงจากหน้าแรกแล้วเปิดรายการสินค้าที่ตรงกับทรงนั้น
    def set_shop_fit_and_open(self, fit_key):
        self.shop_fit = fit_key
        self.shop_style = 'all'
        self.shop()

    # แสดงรูปสินค้าและปรับตามสัดส่วนภาพเพื่อไม่ตัดศีรษะ
    def product_picture(self, parent, product, color, view, height=300, expand=False, rank=None, lower_body=False, hover_zoom=False, lazy=False):
        reference=gallery_assets.reference(product['id'],color,view)
        if reference and reference['color']!=color:
            self.label(parent,self.ui('ภาพอ้างอิงรุ่นเดียวกัน สี','Same model reference in')+' '+self.color_label(reference['color']),10,fg=MID,bg=SOFT,wraplength=360,justify='left').pack(fill='x',padx=10,pady=8)
        stage = tk.Frame(parent, bg=SOFT, height=height)
        stage.pack(fill='both' if expand else 'x', expand=expand)
        stage._hot_sale_rank=rank
        if not expand:
            stage.pack_propagate(False)
        label = tk.Label(stage, bg=SOFT, bd=0, cursor='hand2')
        label.pack(fill='both', expand=True)
        hover_zoom=hover_zoom and not getattr(self,'_admin_screen_active',False)
        if hover_zoom:
            stage._hover_picture=label;label._hover_frames=None;label._hovered=False
            def hover(active):
                label._hovered=active
                if label._hover_frames:
                    photo=label._hover_frames[int(active)];label.configure(image=photo);label._image=photo
            label.bind('<Enter>',lambda event:hover(True))
            label.bind('<Leave>',lambda event:hover(False))
        self._photo_ratios=getattr(self,'_photo_ratios',{})
        ratio_key=(product['id'],color,view,(reference or {}).get('path'),lower_body)
        def match_cached_ratio(event):
            ratio=self._photo_ratios.get(ratio_key)
            if ratio:
                target=max(120,round(event.width*ratio))
                if abs(stage.winfo_height()-target)>1:stage.configure(height=target)
        if not expand:stage.bind('<Configure>',match_cached_ratio)
        from support import image_jobs
        source=None;last_size=None;resize_job=[None];draw_generation=[0]
        def render(size):
            nonlocal last_size
            if source is None or size==last_size or min(size)<20:return
            last_size=size;draw_generation[0]+=1;generation=draw_generation[0]
            original=source
            def work():
                image=ImageOps.contain(original,(max(20,size[0]),max(20,size[1])),method=Image.Resampling.LANCZOS)
                if rank:
                    from PIL import ImageDraw,ImageFont
                    draw=ImageDraw.Draw(image);draw.ellipse((12,12,90,90),fill='#B82B37',outline='#F5DDD2',width=2)
                    draw.text((51,34),'HOT SALE',font=ImageFont.truetype('arial.ttf',11),fill='white',anchor='mm')
                    draw.text((51,62),str(rank),font=ImageFont.truetype('arialbd.ttf',26),fill='white',anchor='mm')
                if hover_zoom:
                    w,h=image.size;zoom=image.resize((round(w*1.035),round(h*1.035)),Image.Resampling.LANCZOS)
                    x=(zoom.width-w)//2;y=(zoom.height-h)//2
                    return image,zoom.crop((x,y,x+w,y+h))
                return image
            def apply(image):
                if image is None or generation!=draw_generation[0]:return
                if hover_zoom:
                    label._hover_frames=tuple(gallery_assets.to_photo(frame,master=self) for frame in image)
                    photo=label._hover_frames[int(label._hovered)]
                else:photo=gallery_assets.to_photo(image,master=self)
                label.configure(image=photo,text='');label._image=photo
            image_jobs.submit(self,label,work,apply)
        def resize(event):
            if resize_job[0]:
                try:label.after_cancel(resize_job[0])
                except tk.TclError:pass
            def draw():
                resize_job[0]=None
                if label.winfo_exists():render((label.winfo_width(),label.winfo_height()))
            resize_job[0]=label.after(60,draw)
        label.bind('<Configure>',resize)
        def stop_resize(event):
            if event.widget is label and resize_job[0]:
                try:label.after_cancel(resize_job[0])
                except tk.TclError:pass
                resize_job[0]=None
        label.bind('<Destroy>',stop_resize,add='+')
        def ready(image):
            nonlocal source,last_size
            source=image;last_size=None
            if image is None:
                label.configure(text=self.ui('ยังไม่มีภาพสีนี้','No photo for this color yet'),font=self.font(10),fg=MID);return
            if not expand:
                self._photo_ratios[ratio_key]=image.height/image.width
                match_cached_ratio(type('Size',(),{'width':max(120,stage.winfo_width())})())
            render((label.winfo_width(),label.winfo_height()))
        label.configure(text=self.ui('กำลังโหลดรูป…','Loading photo…'),font=self.font(10),fg=MID)
        loader=lambda:(gallery_assets.lower_body(product['id'],color,view,fallback=True) if expand else gallery_assets.lower_body_preview(product['id'],color,view)) if lower_body else gallery_assets.source(product['id'],color,view,fallback=True) if expand or (reference and reference['color']!=color) else gallery_assets.preview(product['id'],color,view)
        if lazy:
            # เตรียมเฉพาะภาพที่อยู่ในหน้าจอ ไม่โหลดภาพทั้งหน้าพร้อมกัน
            def load_visible():
                if not image_jobs.is_current(stage) or not stage.winfo_exists():return
                top=stage.winfo_rooty();screen_top=self.winfo_rooty();screen_bottom=screen_top+self.winfo_height()
                if stage.winfo_ismapped() and top+stage.winfo_height()>screen_top-40 and top<screen_bottom+60:
                    image_jobs.submit(self,stage,loader,ready)
                else:stage.after(160,load_visible)
            stage.after(30,load_visible)
        else:image_jobs.submit(self,stage,loader,ready)
        label.bind('<Button-1>' , lambda event: self.zoom_product(product, color, view,lower_body=lower_body))
        return stage

    # เปิดหน้าต่างดูภาพสินค้าและเครื่องมือซูม
    # J18 | ดูรูปสินค้าแบบขยาย
    def zoom_product(self, product, color, view,lower_body=False):
        image = gallery_assets.lower_body(product['id'], color, view,fallback=True) if lower_body else gallery_assets.source(product['id'], color, view,fallback=True)
        if image is None:
            return messagebox.showinfo('JPZ', self.ui('ยังไม่มีภาพสำหรับสีและมุมนี้', 'No photo for this color and view yet.'))
        win = tk.Toplevel(self)
        win._product_source_size=image.size
        reference=gallery_assets.reference(product['id'],color,view)
        picture_color=reference['color'] if reference else color
        caption=f"{product['name']} / {self.color_label(picture_color)}"
        if picture_color!=color:caption+=' / '+self.ui('ภาพอ้างอิงรุ่นเดียวกัน','Same model reference')
        win.title('JPZ / '+caption)
        win.configure(bg=SOFT);win.attributes('-fullscreen',True)
        bar=tk.Frame(win,bg=WHITE);bar.pack(fill='x')
        self.label(bar,caption,11,True,wraplength=600,justify='left',anchor='w').pack(side='left',padx=14,pady=8)
        hint=self.label(win,self.ui('ล้อเมาส์: ซูมเข้า–ออก  ·  คลิกลาก: เลื่อนภาพ  ·  Esc: ปิด','Mouse wheel: zoom  ·  Drag: pan  ·  Esc: close'),10,fg=MID,bg=SOFT)
        hint.pack(side='bottom',pady=6)
        canvas=tk.Canvas(win,bg=SOFT,highlightthickness=0,cursor='hand2');canvas.pack(fill='both',expand=True)
        image_item=canvas.create_image(0,0,anchor='nw')
        state=dict(scale=1.,x=0.,y=0.,fit=True,pending=None,busy=False,generation=0,closed=False,drag=None)
        def clamp():
            w,h=max(1,canvas.winfo_width()),max(1,canvas.winfo_height())
            iw,ih=image.width*state['scale'],image.height*state['scale']
            state['x']=(w-iw)/2 if iw<=w else max(w-iw,min(0,state['x']))
            state['y']=(h-ih)/2 if ih<=h else max(h-ih,min(0,state['y']))
        def draw():
            state['pending']=None
            if state['closed'] or state['busy']:return
            from support import image_jobs
            clamp();scale=state['scale'];x,y=state['x'],state['y'];version=state['generation']
            w,h=max(1,canvas.winfo_width()),max(1,canvas.winfo_height())
            if PIL_AVAILABLE:
                # Resize only the visible area; one background image job at a time.
                box=(max(0,math.floor(-x/scale)),max(0,math.floor(-y/scale)),min(image.width,math.ceil((w-x)/scale)),min(image.height,math.ceil((h-y)/scale)))
                location=(x+box[0]*scale,y+box[1]*scale)
                target=(max(1,round((box[2]-box[0])*scale)),max(1,round((box[3]-box[1])*scale)))
                def work():return image.crop(box).resize(target,Image.Resampling.LANCZOS)
                def done(scaled):
                    state['busy']=False
                    if state['closed']:return
                    if version==state['generation'] and scaled is not None:
                        photo=gallery_assets.to_photo(scaled,master=win);canvas.itemconfigure(image_item,image=photo);canvas.coords(image_item,*location);canvas._image=photo
                    elif version!=state['generation']:queue_draw()
                state['busy']=True;image_jobs.submit(self,canvas,work,done)
            else:
                scaled=image.resize((max(1,round(image.width*scale)),max(1,round(image.height*scale))))
                photo=gallery_assets.to_photo(scaled,master=win);canvas.itemconfigure(image_item,image=photo);canvas.coords(image_item,x,y);canvas._image=photo
        def queue_draw():
            if state['closed']:return
            if state['pending'] is None:state['pending']=win.after(16,draw)
        def fit(event=None):
            state['fit']=True
            state['scale']=min(max(1,canvas.winfo_width())/image.width,max(1,canvas.winfo_height())/image.height)
            state['generation']+=1;clamp();queue_draw()
        def zoom(factor,px=None,py=None):
            if state['closed']:return
            px=canvas.winfo_width()/2 if px is None else px;py=canvas.winfo_height()/2 if py is None else py
            old=state['scale'];fit_scale=min(max(1,canvas.winfo_width())/image.width,max(1,canvas.winfo_height())/image.height)
            new=max(fit_scale*.25,min(max(4.,fit_scale*4),old*factor))
            state['x']=px-(px-state['x'])*new/old;state['y']=py-(py-state['y'])*new/old
            state.update(scale=new,fit=False);state['generation']+=1;clamp();queue_draw()
        def wheel(event):
            steps=event.delta/120 if getattr(event,'delta',0) else 1 if getattr(event,'num',0)==4 else -1
            zoom(1.18**max(-3,min(3,steps)),event.x,event.y);return 'break'
        def start_drag(event):state['drag']=(event.x,event.y);canvas.configure(cursor='fleur');return 'break'
        def drag(event):
            if state['drag'] is not None:
                x,y=state['drag'];state['x']+=event.x-x;state['y']+=event.y-y;state['drag']=(event.x,event.y)
                state['generation']+=1;clamp();queue_draw()
            return 'break'
        def end_drag(event):state['drag']=None;canvas.configure(cursor='hand2');return 'break'
        def resized(event):
            if state['fit']:fit()
            else:state['generation']+=1;clamp();queue_draw()
        def close():
            if state['closed']:return
            state['closed']=True;win._retired_page=True
            if state['pending'] is not None:
                try:win.after_cancel(state['pending'])
                except tk.TclError:pass
            win.destroy()
        self.button(bar,self.ui('× ปิด','× Close'),close,compact=True).pack(side='right',padx=8,pady=6)
        self.button(bar,'−',lambda:zoom(1/1.18),compact=True).pack(side='right')
        self.button(bar,'+',lambda:zoom(1.18),compact=True).pack(side='right')
        self.button(bar,self.ui('พอดีหน้าจอ','Fit screen'),fit,compact=True).pack(side='right',padx=8)
        canvas.bind('<MouseWheel>',wheel);canvas.bind('<Button-4>',wheel);canvas.bind('<Button-5>',wheel)
        canvas.bind('<ButtonPress-1>',start_drag);canvas.bind('<B1-Motion>',drag);canvas.bind('<ButtonRelease-1>',end_drag)
        canvas.bind('<Double-Button-1>',lambda event:fit());canvas.bind('<Configure>',resized)
        win.bind('<Escape>',lambda event:close());win.protocol('WM_DELETE_WINDOW',close)
        self._zoom_ui=dict(window=win,canvas=canvas,state=state,fit=fit,zoom=zoom,wheel=wheel,start_drag=start_drag,drag=drag,end_drag=end_drag,close=close)
        win.focus_set();canvas.focus_set();queue_draw()

    # สิทธิพิเศษรายวันในแถบไอวอรี พร้อมเงื่อนไขจริงและการจัดวางตามหน้าจอ
    # J13 | แบนเนอร์ส่วนลด
    def promotion_banner(self, parent):
        promo=loyalty.daily()
        if not promo['enabled']:return
        ivory='#F8F6F0';ink='#203447';wine='#8C2635';gold='#B8A88E';muted='#786D5B'
        banner=tk.Frame(parent,bg=ivory,highlightbackground='#DDD6C8',highlightthickness=1)
        banner.pack(fill='x',padx=30,pady=(14,12))
        tk.Frame(banner,bg=gold,height=2).pack(fill='x')
        inner=tk.Frame(banner,bg=ivory);inner.pack(fill='x',padx=24,pady=18)
        badge=tk.Canvas(inner,width=142,height=114,bg=wine,highlightthickness=0)
        badge.create_line(18,16,124,16,fill=gold)
        badge.create_text(71,31,text=self.ui('สิทธิพิเศษวันนี้','TODAY’S PRIVILEGE'),fill='#D5C5A7',font=(font_family(True,11),-12,font_weight(True,11)))
        percent_pixels=42
        percent_font=tkfont.Font(self,family='Tahoma',size=-percent_pixels,weight='bold')
        percent_text=f"{promo['percent']}%"
        while percent_font.measure(percent_text)>120 and percent_pixels>18:
            percent_pixels-=2;percent_font.configure(size=-percent_pixels)
        badge.create_text(71,70,text=percent_text,fill=ivory,font=percent_font)
        badge.create_line(18,98,124,98,fill=gold)
        badge._percent_font=percent_font;badge._daily_percent=promo['percent']
        # แสงไล่ผ่านป้ายส่วนลดแบบเบา ใช้ป้ายเดียวกันทั้งหน้าแรกและหน้าสินค้า
        soft=badge.create_polygon(-100,0,-54,0,-9,114,-55,114,fill='#993144',outline='',tags='discount_shine')
        shine=badge.create_polygon(-80,0,-60,0,-15,114,-35,114,fill='#AC3A4F',outline='',tags='discount_shine')
        badge.tag_lower('discount_shine')
        import time
        from support.image_jobs import is_current
        motion=dict(active=True,timer=None,frames=0,shine=shine,soft=soft)
        started=time.monotonic();viewport=badge.master
        while viewport is not None and not isinstance(viewport,tk.Canvas):viewport=getattr(viewport,'master',None)
        def stop_discount_motion(event=None):
            if event is not None and event.widget is not badge:return
            motion['active']=False
            if motion['timer']:
                try:badge.after_cancel(motion['timer'])
                except tk.TclError:pass
                motion['timer']=None
        def animate_discount():
            motion['timer']=None
            if not is_current(badge) or not badge.winfo_exists():stop_discount_motion();return
            visible=badge.winfo_ismapped() and self.state()!='iconic' and not str(self.current_page).startswith('admin')
            if visible and viewport is not None:
                top=viewport.winfo_rooty();y=badge.winfo_rooty()
                visible=y+badge.winfo_height()>top and y<top+viewport.winfo_height()
            if visible:
                phase=(time.monotonic()-started)%4
                x=-70+280*phase/2.5 if phase<2.5 else -70
                badge.coords(soft,x-20,0,x+26,0,x+71,114,x+25,114)
                badge.coords(shine,x,0,x+20,0,x+65,114,x+45,114)
                motion['frames']+=1
            motion['timer']=badge.after(60 if visible else 200,animate_discount)
        badge.bind('<Destroy>',stop_discount_motion,add='+')
        motion['timer']=badge.after(60,animate_discount)
        copy=tk.Frame(inner,bg=ivory)
        title=self.label(copy,'DAILY DENIM',19,True,bg=ivory,fg=wine,anchor='w',justify='left');title.pack(anchor='w')
        caption=self.label(copy,self.ui('สิทธิพิเศษสำหรับยีนส์ที่คุณเลือก','A daily privilege for your denim.'),12,bg=ivory,fg=ink,anchor='w',justify='left');caption.pack(fill='x',pady=(7,8))
        detail=self.label(copy,self.ui(f"วันที่ {promo['day']} · ใช้ส่วนลดอัตโนมัติเมื่อสั่งซื้อ",f"{promo['day']} · Applied automatically at checkout"),10,fg=muted,bg=ivory,anchor='w',justify='left');detail.pack(fill='x')
        copy.bind('<Configure>',lambda event:[label.configure(wraplength=max(140,event.width)) for label in (title,caption,detail)])
        terms=tk.Frame(inner,bg=ivory);term_blocks=[]
        for column,(th,en,value) in enumerate([('ยอดซื้อขั้นต่ำ','MINIMUM SPEND',promo['minimum']),('ลดสูงสุด','MAXIMUM SAVING',promo['cap'])]):
            block=tk.Frame(terms,bg=ivory);term_blocks.append(block);block.grid(row=0,column=column,sticky='nw',padx=(0,24) if column==0 else (24,0))
            self.label(block,self.ui(th,en),10,bg=ivory,fg=muted).pack(anchor='w')
            self.label(block,f"฿{value:,.0f}",20,True,bg=ivory,fg=wine if column==1 else ink).pack(anchor='w',pady=(8,0))
        divider=tk.Frame(terms,bg=gold,width=1);divider.grid(row=0,column=0,sticky='nse',pady=2)
        mode=[None]
        def arrange(event):
            selected=2 if event.width<430 else 1 if event.width<900 else 0
            if mode[0]==selected:return
            mode[0]=selected
            for index,block in enumerate(term_blocks):block.grid_configure(row=index if selected==2 else 0,column=0 if selected==2 else index,padx=0 if selected==2 else (0,24) if index==0 else (24,0),pady=(0,14) if selected==2 else 0)
            if selected==2:divider.grid_remove()
            else:divider.grid()
            for col in range(3):inner.columnconfigure(col,weight=0)
            if selected==0:
                badge.grid(row=0,column=0,sticky='nw',padx=(0,26),pady=0)
                copy.grid(row=0,column=1,sticky='new',padx=(0,24),pady=8)
                terms.grid(row=0,column=2,columnspan=1,sticky='nw',padx=0,pady=14);inner.columnconfigure(1,weight=1)
            elif selected==1:
                badge.grid(row=0,column=0,sticky='nw',padx=(0,24),pady=0)
                copy.grid(row=0,column=1,sticky='new',padx=0,pady=8)
                terms.grid(row=1,column=0,columnspan=2,sticky='w',padx=0,pady=(14,0));inner.columnconfigure(1,weight=1)
            else:
                badge.grid(row=0,column=0,sticky='w',padx=0,pady=(0,16))
                copy.grid(row=1,column=0,sticky='ew',padx=0,pady=0)
                terms.grid(row=2,column=0,columnspan=1,sticky='w',padx=0,pady=(18,0));inner.columnconfigure(0,weight=1)
        inner.bind('<Configure>',arrange)
        badge.grid(row=0,column=0);copy.grid(row=0,column=1);terms.grid(row=0,column=2)
        self._promotion_banner_ui=dict(banner=banner,badge=badge,copy=copy,title=title,caption=caption,detail=detail,terms=terms,promotion=promo,motion=motion)
        return banner

    # สรุปยอดสินค้า ส่วนลดรายวัน ยอดก่อน VAT และ VAT ที่รวมในราคา
    def price_before_vat(self,parent,total,bg=None,padx=0,unit=False):
        tax=db.vat_breakdown(total)
        label=self.label(parent,self.ui(('ราคาต่อชิ้นก่อน VAT' if unit else 'ยอดก่อน VAT')+f" ฿{tax['before_vat']:,.2f}",('Unit price before VAT' if unit else 'Before VAT')+f" ฿{tax['before_vat']:,.2f}"),11,fg=MID,bg=bg,wraplength=520)
        label._before_vat=tax['before_vat'];label.pack(anchor='w',padx=padx,pady=4)
        return label

    def catalogue_price(self,parent,product,size=32,padx=0,bg=WHITE,quote=None):
        quote=quote if quote is not None else product_promotions.cart_quote({(product['id'],product['color'],size):1},self.user['id'])
        offer=product_promotions.setting(product['id'])
        if offer['enabled'] and offer['kind']=='price':
            self.label(parent,self.ui('ราคาพิเศษ','SPECIAL PRICE'),9,True,bg='#8C2635',fg='white',padx=8,pady=4).pack(anchor='w',padx=padx,pady=(5,3))
        frame=tk.Frame(parent,bg=bg);frame.pack(anchor='w',fill='x',padx=padx,pady=3)
        old=None
        if quote['discount_amount']:
            font=tkfont.Font(self,font=self.font(10));font.configure(overstrike=1)
            old=self.label(frame,f"฿{quote['subtotal']:,.2f}",10,fg=MID,bg=bg);old.configure(font=font);old._price_font=font;old.pack(side='left',padx=(0,10))
        current=self.label(frame,f"฿{quote['total']:,.2f}",12,True,fg='#BB2020' if quote['discount_amount'] else INK,bg=bg);current.pack(side='left')
        def fit_prices(event):
            if old is None:return
            stacked=old.winfo_reqwidth()+current.winfo_reqwidth()+10>event.width
            old.pack_configure(side='top' if stacked else 'left',anchor='w',padx=0 if stacked else (0,10))
            current.pack_configure(side='top' if stacked else 'left',anchor='w')
        frame.bind('<Configure>',fit_prices)
        return quote['total']

    def reward_summary(self,parent,subtotal,points=0,cart=None,padx=30):
        totals=product_promotions.cart_quote(cart,self.user['id']) if cart is not None else loyalty.redeem_quote(subtotal,self.user['id'],0)
        return self.order_summary(parent,totals,padx=padx)

    # J24 | สรุปคำสั่งซื้อ / VAT / ยอดชำระ
    def order_summary(self,parent,totals,padx=20):
        tax=db.vat_breakdown(totals['total'])
        panel=tk.Frame(parent,bg=WHITE);panel.pack(fill='x',padx=padx,pady=(24,20))
        heading=self.label(panel,self.ui('สรุปคำสั่งซื้อ','Order Summary'),22,True,bg=WHITE,anchor='w',justify='left');heading.pack(anchor='w',fill='x',pady=(0,20))
        block=tk.Frame(panel,bg=WHITE,width=520,height=180);block.pack(anchor='w');block.pack_propagate(False)
        rows=[]
        def update_height():
            from support.image_jobs import is_current
            if is_current(block) and block.winfo_exists():block.configure(height=sum(row['frame'].winfo_reqheight()+18 for row in rows))
        for caption,value,total in [(self.ui('ยอดก่อน VAT','Before VAT'),tax['before_vat'],False),(self.ui('VAT 7%','VAT 7%'),tax['vat'],False),(self.ui('ยอดชำระแล้ว' if totals.get('payment_status')=='paid' else 'ยอดที่ต้องชำระ','Paid total' if totals.get('payment_status')=='paid' else 'Amount to pay'),tax['total'],True)]:
            row=tk.Frame(block,bg=WHITE);row.pack(anchor='w',fill='x',pady=(0,18))
            row.columnconfigure(1,weight=1)
            title=self.label(row,caption,18 if total else 16,True,bg=WHITE,anchor='w')
            amount=self.label(row,f'฿{value:,.2f}',18 if total else 16,True,bg=WHITE,anchor='w')
            layout=[None]
            def arrange(event,t=title,a=amount,mode=layout):
                stacked=t.winfo_reqwidth()+a.winfo_reqwidth()+14>event.width
                if mode[0]==stacked:return
                mode[0]=stacked;t.grid(row=0,column=0,sticky='w')
                a.grid(row=1 if stacked else 0,column=0 if stacked else 1,sticky='w' if stacked else 'e',padx=(0 if stacked else 10,0),pady=(5 if stacked else 0,0))
                self.after_idle(update_height)
            row.bind('<Configure>',arrange);rows.append(dict(frame=row,title=title,amount=amount,value=value))
        discount=self.label(panel,self.ui('ยอดก่อน VAT เป็นยอดหลังหักส่วนลดแล้ว · VAT รวมอยู่ในยอดชำระแล้ว','Before VAT is after discounts. VAT is included in the payment total.'),11,fg=MID,bg=WHITE,justify='left');discount.pack(fill='x',pady=(2,0))
        def fit_text(event):
            # จำกัดกรอบราคาให้พอดีกับชื่อรายการและยอดเงิน ไม่กระจายถึงขอบหน้าจอ
            preferred=max(row['title'].winfo_reqwidth() for row in rows)+max(row['amount'].winfo_reqwidth() for row in rows)+48
            block.configure(width=min(event.width,preferred))
            heading.configure(wraplength=max(120,min(680,event.width)))
            if discount is not None:discount.configure(wraplength=max(120,min(680,event.width)))
        panel.bind('<Configure>',fit_text)
        panel._order_summary=dict(heading=heading,rows=rows,discount=discount,tax=tax,totals=totals,block=block)
        self._order_summary_ui=panel._order_summary
        return panel


    # เปิดหน้ารวมสินค้า
    def shop(self, push=True):
        self.navigate('shop', self._shop, push=push)

    # สร้างหน้าสินค้า ตัวกรอง และปุ่มเปลี่ยนหน้ารายการ
    def _shop(self):
        from support import storefront_ui
        storefront_ui.show(self)

    # สร้างปุ่มตัวกรองทรงสินค้า
    def filter_button(self,parent,key,fit=True):
        active=self.shop_fit==key
        text=self.tr('all') if key=='all' else self.fit_label(key)
        self.flow_chip(parent,self.button(parent,text,lambda:self.set_shop_fit(key),dark=active,compact=True))

    # สร้างปุ่มตัวกรองสไตล์สินค้า
    def style_button(self,parent,key):
        active=self.shop_style==key
        text=self.tr('all') if key=='all' else option_name(self.lang,key)
        self.flow_chip(parent,self.button(parent,text,lambda:self.set_shop_style(key),dark=active,compact=True))

    # จัดปุ่มตัวกรองให้ขึ้นบรรทัดใหม่เมื่อหน้าต่างแคบ
    def flow_chip(self,parent,button):
        if not hasattr(parent,'_chips'):
            parent._chips=[];parent.pack_propagate(False);parent.configure(height=44)
            def arrange(event):
                scale=parent._chips[0]._get_widget_scaling()
                available=max(200,parent.winfo_width()/scale-8);x,y=0,0;rows=1
                for item in parent._chips:
                    width=int(item.cget('width'))+6
                    if x+width>available and x>0:x=0;y+=44;rows+=1
                    item.place(x=x,y=y);x+=width
                target=round(rows*44*scale)
                if parent.winfo_height()!=target:parent.configure(height=target)
            parent.bind('<Configure>',arrange)
            parent._layout_chips=lambda:arrange(None)
        parent._chips.append(button)
        button.bind('<Configure>',lambda event:parent._layout_chips(),add='+')

    # เปลี่ยนทรงที่ใช้กรองและแสดงสินค้าใหม่
    def set_shop_fit(self, key):
        self.shop_fit = key
        self._shop()

    # เปลี่ยนสไตล์ที่ใช้กรองและแสดงสินค้าใหม่
    def set_shop_style(self, key):
        self.shop_style = key
        self._shop()

    # สร้างปุ่มหัวใจและแสดงว่าบันทึกเป็นรายการโปรดแล้วหรือยัง
    def favorite_button(self, parent, product, saved=False, text='', compact=False):
        button = self.button(parent, text, lambda: self.toggle_favorite(product), compact=compact)
        key = 'favorite_saved.png' if saved else 'favorite_empty.png'
        cache = getattr(self, '_favorite_icons', None)
        if cache is None:
            cache = self._favorite_icons = {}
        if key not in cache:
            with Image.open(ASSET_DIR/key) as heart:
                cache[key]=ctk.CTkImage(light_image=heart.copy(),dark_image=heart.copy(),size=(24,24))
        button.configure(image=cache[key], compound='left', fg='#D93648' if saved else INK, activeforeground='#D93648')
        button._image = cache[key]
        return button

    # จัดการ์ดสินค้าเป็นตาราง พร้อมรูป ชื่อ ราคา และปุ่มรายการโปรด
    def product_grid(self, p, items, scroll=True):
        frame = tk.Frame(self.scroll_content(p) if scroll else p, bg=WHITE)
        frame.pack(fill='x', padx=25, pady=(0, 12))
        for col in range(3):
            frame.grid_columnconfigure(col, weight=1, uniform='prod')
        ranks=merchandising.best_sellers()
        def render_one(i,x):
            c = card(frame)
            c._skip_block_shine=True
            c.grid(row=i // 3, column=i % 3, padx=6, pady=6, sticky='nsew')
            self.product_picture(c, x, x['color'], 'FRONT', height=380,rank=ranks.get(x['id']))
            self.label(c, x['name'], 12, True, wraplength=300, justify='left').pack(anchor='w', padx=14, pady=(10, 2))
            self.label(c, f"{self.fit_label(x['fit'])} / {option_name(self.lang, x['style'])}", 8, fg=MID).pack(anchor='w', padx=14)
            displayed_price=self.catalogue_price(c,x,padx=14)
            self.price_before_vat(c,displayed_price,padx=14,unit=True)
            actions = tk.Frame(c, bg=WHITE)
            actions.pack(fill='x', padx=8, pady=9)
            self.button(actions, self.tr('view_product'), lambda z=x: self.product_detail(z), compact=True).pack(side='left')
            favorite_text = '♥' if db.is_favorite(self.user['id'], x['id']) else '♡'
            heart = self.favorite_button(actions, x, saved=favorite_text == '♥', compact=True)
            heart.configure(fg='#D93648' if favorite_text == '♥' else MID, activeforeground='#D93648')
            heart.pack(side='right')

        self._card_batches=getattr(self,'_card_batches',set());token=object();self._card_batches.add(token)
        frame.bind('<Destroy>',lambda event:self._card_batches.discard(token) if event.widget is frame else None,add='+')
        pending=iter(enumerate(items))
        def batch():
            if not frame.winfo_exists():self._card_batches.discard(token);return
            for index in range(1):
                try:i,x=next(pending)
                except StopIteration:self._card_batches.discard(token);return
                render_one(i,x)
            self.after(16,batch)
        batch()

    # เพิ่มหรือนำสินค้าออกจากรายการโปรดของบัญชี
    def toggle_favorite(self, product):
        saved = db.toggle_favorite(self.user['id'], product['id'])
        message = self.tr('favorite_saved') if saved else self.tr('favorite_removed')
        self.toast('✓ ' + message)
        self.render_page(
            self.current_page,
            *self.current_args.get('args', ()),
            **self.current_args.get('kwargs', {}),
        )

    # เปิดหน้ารายการโปรด
    def favorites(self, push=True):
        self.navigate('favorites', self._favorites, push=push)

    # แสดงสินค้าที่บัญชีบันทึกไว้ในรายการโปรด
    def _favorites(self):
        from support import storefront_ui
        storefront_ui.show_favorites(self)

    # เปิดหน้ารายละเอียดของสินค้าที่เลือก
    def product_detail(self, p, push=True):
        self.navigate('product', self._product_detail, p, push=push)

    # แสดงรูป ราคา สี ไซซ์ สต็อก และรายละเอียดของสินค้าที่เลือก
    # J17 | หน้ารายละเอียดสินค้า
    def _product_detail(self, p):
        if self.current_args.get('_viewed_product') != p['id']:
            admin_data.log_event(self.user['id'], 'product_view', p['id'])
            self.current_args['_viewed_product'] = p['id']
        db.record_recent_view(self.user['id'], p['id'])
        b = self.shell(show_back=False)
        breadcrumb=tk.Frame(b,bg=WHITE);breadcrumb.pack(fill='x',padx=30,pady=(10,0))
        from_favorites=bool(self.page_history and self.page_history[-1][0]=='favorites')
        back_caption=self.ui('‹ กลับไปรายการโปรด','‹ Back to favorites') if from_favorites else self.ui('‹ กลับไปสินค้า','‹ Back to products')
        self.button(breadcrumb,back_caption,self.go_back if self.page_history else lambda:self.shop(push=False),compact=True).pack(side='left')
        self.label(breadcrumb,'JPZ / '+p['name'],10,fg=MID).pack(side='left',padx=14)
        connection=db.conn()
        default_colors=[row['color'] for row in connection.execute('SELECT DISTINCT color FROM product_gallery WHERE product_id=? ORDER BY color',(p['id'],))]
        connection.close()
        default_colors=sorted({v['color'] for v in db.variants(p['id'])}) or [p['color']]
        current_state = self.product_state.setdefault(
            p['id'],
            {'color': p['color'], 'size': p.get('recommended_size',32), 'qty': 1, 'view': gallery_assets.standing_view(p,prefer_back=p['id']%4==0)},
        )
        if current_state['color'] not in default_colors:
            current_state['color'] = default_colors[0]
        state = current_state
        variants = db.variants(p['id'])
        available = {v['color'] for v in variants if v['stock'] > 0}
        colors = [color for color in default_colors if any(v['color'] == color for v in variants)]
        if colors and state['color'] not in colors:
            state['color'] = next((color for color in colors if color in available), colors[0])
        wrap = tk.Frame(b, bg=WHITE)
        wrap.pack(fill='both', expand=True, padx=30, pady=12)
        left = tk.Frame(wrap, bg=WHITE,width=680)
        left.pack(side='left',fill='y');left.pack_propagate(False)
        def balance(event):
            left.configure(width=max(300,min(event.height+80,int(event.width*.56))))
        wrap.bind('<Configure>',balance)
        thumbs = tk.Frame(left, bg=WHITE, width=90)
        thumbs.pack(side='left', fill='y');thumbs.pack_propagate(False)
        view_labels = {'FRONT': self.ui('คนใส่ · ด้านหน้า','WORN / FRONT'), 'BACK': self.ui('คนใส่ · ด้านหลัง','WORN / BACK'), 'DETAIL': self.ui('ตัวกางเกง','DENIM'), 'TEXTURE': self.ui('เนื้อผ้า / รายละเอียด','TEXTURE')}
        pictures = catalogue.gallery(p['id'], state['color'])
        for view in ('DETAIL', 'FRONT', 'BACK', 'TEXTURE'):
            photo = None
            thumb_caption={'FRONT':self.ui('ด้านหน้า','Front'),'BACK':self.ui('ด้านหลัง','Back'),'DETAIL':self.ui('ตัวกางเกง','Denim'),'TEXTURE':self.ui('เนื้อผ้า','Texture')}
            thumb = tk.Button(thumbs, text=thumb_caption[view], image=photo or '', compound='top',
                              command=lambda x=view: self.set_product_view(p, x), font=self.font(8, True),
                              bg=SOFT if state['view'] == view else WHITE, bd=0, cursor='hand2', pady=5,wraplength=84)
            thumb._image = photo
            thumb.pack(fill='x', pady=3)
            from support import image_jobs
            def load_thumb(v=view):
                image=gallery_assets.lower_body_preview(p['id'],state['color'],v)
                if image is not None:image.thumbnail((68,68))
                return image
            def show_thumb(image,button=thumb):
                if image is not None:
                    photo=gallery_assets.to_photo(image,master=self);button.configure(image=photo);button._image=photo
            image_jobs.submit(self,thumb,load_thumb,show_thumb)
        art = tk.Frame(left, bg=SOFT,highlightbackground=LINE,highlightthickness=1)
        art.pack(side='left', fill='both', expand=True, padx=(8, 15))
        self.label(art, view_labels[state['view']], 10, True, bg=SOFT, fg=MID).pack(anchor='w', padx=14, pady=(12, 4))
        self.product_picture(art, p, state['color'], state['view'], expand=True,lower_body=True)
        self.button(art, self.ui('ดูภาพใหญ่ / ซูม +', 'OPEN LARGE / ZOOM +'), lambda: self.zoom_product(p, state['color'], state['view'],lower_body=True), compact=True).pack(pady=8)
        r = tk.Frame(wrap, bg=WHITE, width=390)
        r.pack(side='right',fill='both',expand=True,padx=(12,5))
        r.pack_propagate(False)
        purchase=tk.Frame(r,bg=WHITE);purchase.pack(side='bottom',fill='x',pady=(12,0))
        tk.Frame(purchase,bg=LINE,height=1).pack(fill='x',pady=(0,10))
        purchase_row=tk.Frame(purchase,bg=WHITE);purchase_row.pack(fill='x',pady=(0,10))
        r = self.scroll_content(r)
        self._new_product_ui=dict(content=r,art=art,thumbs=thumbs,state=state)
        self.label(r,'JPZ / DENIM COLLECTION',10,True,fg=MID).pack(anchor='w',pady=(10,8))
        self.label(r, p['name'], 24, True, fg=DENIM, wraplength=600, justify='left').pack(anchor='w')
        self.label(r, self.fit_label(p['fit']), 10, True, fg=MID).pack(anchor='w')
        unit_price=db.price_for_size(p,state['size'])
        promo=loyalty.daily()
        offer=product_promotions.setting(p['id'])
        quote=product_promotions.cart_quote({(p['id'],state['color'],state['size']):state['qty']},self.user['id'])
        price_box=tk.Frame(r,bg=WHITE);price_box.pack(anchor='w',fill='x',pady=(10,6))
        if offer['enabled'] and offer['kind']=='price':self.label(price_box,self.ui('ราคาพิเศษ','SPECIAL PRICE'),10,True,bg='#8C2635',fg='white',padx=10,pady=5).pack(anchor='w',pady=(0,8))
        price_line=tk.Frame(price_box,bg=WHITE);price_line.pack(anchor='w')
        self._product_price_ui={'quote':quote,'original':None,'current':None}
        if quote['discount_amount']:
            old_font=tkfont.Font(self,font=self.font(13));old_font.configure(overstrike=1)
            original=self.label(price_line,f'฿{unit_price:,.2f}',13,fg=MID);original.configure(font=old_font);original._price_font=old_font;original.pack(side='left',padx=(0,10))
            self._product_price_ui['original']=original
        effective_price=quote['total']/state['qty']
        current=self.label(price_line,f'฿{effective_price:,.2f}',18,True,fg='#BB2020' if quote['discount_amount'] else INK);current.pack(side='left')
        self._product_price_ui['current']=current
        if quote['discount_amount']:
            percent=quote['discount_amount']/quote['subtotal']*100
            badge=self.label(price_line,f"(−{percent:.2f}%)",12,True,fg='#BB2020');badge.pack(side='left',padx=(8,0));self._product_price_ui['percent']=badge
        if quote['discount_amount']:
            self.label(price_box,self.ui(f"ราคาต่อชิ้นเมื่อซื้อ {state['qty']} ตัว · ลดรวม ฿{quote['discount_amount']:,.2f}",f"Per item when buying {state['qty']} · Save ฿{quote['discount_amount']:,.2f} total"),11,fg=MID,wraplength=600,justify='left').pack(anchor='w',pady=(5,0))
        price_explanation=state.get('price_explanation',False)
        def toggle_price_explanation():
            state['price_explanation']=not state.get('price_explanation',False)
            self._product_detail(p)
        self.button(price_box,self.ui('รายละเอียดราคา / โปรโมชัน','Price / promotion details'),toggle_price_explanation,compact=True).pack(anchor='w',pady=5)
        if promo['enabled'] and price_explanation:
            self.label(price_box,self.ui(f"ลด {promo['percent']}% เมื่อยอดครบ ฿{promo['minimum']:,.2f} · สูงสุด ฿{promo['cap']:,.2f} ต่อคำสั่งซื้อ",f"{promo['percent']}% off orders from ฿{promo['minimum']:,.2f} · Maximum ฿{promo['cap']:,.2f} per order"),11,fg=MID,wraplength=600,justify='left').pack(anchor='w',pady=(5,0))
        if quote['discount_amount'] and price_explanation:
            self.label(price_box,product_promotions.label(quote['discount_kind'],self.lang)+' · '+self.ui('ไม่ลดซ้อน เลือกส่วนลดที่คุ้มกว่าตอนสั่งซื้อ','No stacking; the better order discount applies at checkout.'),10,fg=MID,wraplength=600,justify='left').pack(anchor='w',pady=(5,0))
        self.label(r,self.ui('ราคานี้รวม VAT 7% แล้ว','Price includes VAT 7%'),11,fg=MID).pack(anchor='w',pady=(0,14))
        if price_explanation:self.price_before_vat(r,effective_price,unit=True)
        tk.Frame(r,bg=LINE,height=1).pack(fill='x',pady=16)
        self.label(r, self.tr('color'), 11, True).pack(anchor='w')
        cr = tk.Frame(r, bg=WHITE)
        cr.pack(anchor='w', pady=5)
        swatches = {'black': '#191919', 'dark_indigo': '#23344D', 'raw_indigo': '#263D59',
                    'washed_blue': '#6E93AC', 'light_blue': '#B1CDDF', 'vintage_blue': '#64869B', 'grey': '#8B8D90'}
        for i, color in enumerate(colors):
            selected = state['color'] == color
            choice = tk.Frame(cr, bg=WHITE, highlightbackground=INK if selected else LINE,
                              highlightthickness=2 if selected else 1, cursor='hand2')
            choice.grid(row=i // 2, column=i % 2, padx=(0, 6), pady=(0,6), sticky='ew')
            chip = tk.Canvas(choice, width=22, height=22, bg=swatches.get(color, '#777777'),
                             highlightthickness=1, highlightbackground=LINE, cursor='hand2')
            chip.pack(side='left', padx=6, pady=6)
            caption = self.label(choice, ('✓ ' if selected else '') + self.color_label(color), 8, selected)
            caption.pack(side='left', padx=(0, 8))
            for widget in (choice, chip, caption):
                widget.bind('<Button-1>', lambda event, x=color: self.set_product_option(p, 'color', x))
        for column in range(2):cr.grid_columnconfigure(column,uniform='product_colors')
        self.label(r, self.tr('size'), 11, True).pack(anchor='w', pady=(12, 0))
        sr = tk.Frame(r, bg=WHITE)
        sr.pack(anchor='w', pady=5)
        sizes=sorted({v['size'] for v in variants if v['color']==state['color']})
        size_buttons=[]
        for i,size in enumerate(sizes):
            stock=db.variant_stock(p['id'],state['color'],size)
            label=db.size_label(size)+(self.ui(' · หมด',' · Sold out') if not stock else '')
            size_button=self.button(sr,label,lambda x=size:self.set_product_option(p,'size',x),dark=state['size']==size,compact=True)
            size_button.configure(font=ui_font(11),text_color='white' if state['size']==size else INK if stock else '#7A8590')
            size_button.grid(row=i//4,column=i%4,padx=(0,6),pady=(0,6),sticky='ew')
            size_buttons.append(size_button)
        for column in range(4):sr.grid_columnconfigure(column,weight=1,uniform='product_sizes')
        sr.pack_configure(fill='x')
        size_layout=[None]
        def arrange_sizes(event):
            needed=max((button.winfo_reqwidth() for button in size_buttons),default=80)+6
            columns=max(1,min(4,event.width//needed))
            if columns==size_layout[0]:return
            size_layout[0]=columns
            for column in range(4):sr.grid_columnconfigure(column,weight=1 if column<columns else 0,minsize=0,uniform='product_sizes' if column<columns else '')
            for index,button in enumerate(size_buttons):button.grid_configure(row=index//columns,column=index%columns)
        sr.bind('<Configure>',arrange_sizes)
        self._product_size_buttons=size_buttons
        qr = tk.Frame(purchase_row, bg=WHITE)
        qr.pack(side='left', pady=5)
        self.button(qr, '−', lambda: self.change_qty(p, -1), compact=True).pack(side='left')
        self.label(qr, str(state['qty']), 11, True).pack(side='left', padx=15)
        self.button(qr, '+', lambda: self.change_qty(p, 1), compact=True).pack(side='left')
        stock = db.variant_stock(p['id'], state['color'], state['size'])
        self.label(r, self.ui('หมด' if stock==0 else f'คงเหลือ {stock} ตัว','Sold out' if stock==0 else f'{stock} in stock'), 8, fg='#BB2020' if stock<5 else MID).pack(anchor='w', pady=(2, 8))
        self.label(r,self.ui('เลือกแต่ละรุ่นรวมทุกสีและไซซ์ได้ไม่เกิน 20 ตัว','Up to 20 units per product across colors and sizes.'),11,fg=MID,wraplength=600).pack(anchor='w',pady=4)
        self.product_error=self.label(r,'',11,True,fg='#BB2020')
        self.product_error.pack(anchor='w',pady=4)
        add_button=self.button(purchase_row, self.tr('add_bag'), lambda: self.add_cart(p), dark=True);add_button.pack(side='left',fill='x',expand=True,padx=10)
        if not colors:
            add_button.configure(state='disabled')
            self.product_error.configure(text=self.ui('สินค้านี้ยังไม่มีสีที่จำหน่าย','This product has no selling colors yet.'))
        favorite_text = self.tr('remove_favorite') if db.is_favorite(self.user['id'], p['id']) else self.tr('save_favorite')
        saved = db.is_favorite(self.user['id'], p['id'])
        heart = self.favorite_button(purchase_row, p, saved=saved,compact=True)
        heart.configure(fg='#D93648' if saved else INK, activeforeground='#D93648')
        heart.pack(side='right', pady=5)
        measurements=sizing.for_size(p,state['size'])
        dimension_names={'waist':('รอบเอว','Waist'),'hip':('รอบสะโพก','Hip'),'thigh':('รอบต้นขา','Thigh'),'rise':('ความยาวเป้าหน้า','Front rise'),'inseam':('ความยาวขาด้านใน','Inseam'),'leg_opening':('รอบปลายขา','Leg opening')}
        dimension_text=' / '.join(f"{self.ui(*dimension_names[key])} {measurements[key]:g} {self.ui('นิ้ว','in')}" for key in sizing.FIELDS)
        dimension_text+=' · '+self.ui('ขนาดตามตารางไซซ์ของรุ่น','Model size chart dimensions')
        self.button(r,self.ui('ตารางไซซ์ / วิธีวัด','Size chart / How to measure'),lambda:self.size_chart(p),dark=True).pack(fill='x',pady=10)
        signature=(p.get('design_th') or p.get('design','')) if self.lang=='TH' else p.get('design','')
        if signature:
            self.label(r,self.ui('เอกลักษณ์ของรุ่นนี้','SIGNATURE DETAILS'),10,True).pack(anchor='w',pady=(12,3))
            self.label(r,signature,10,fg=MID,wraplength=600,justify='left').pack(anchor='w',pady=(0,5))
        details = [('product_details', f"{self.fit_label(p['fit'])} / {option_name(self.lang, p['style'])}"), ('measurements', dimension_text), ('fit_details', self.fit_label(p['fit'])), ('care', self.ui('ซักด้วยน้ำเย็น แยกซักจากผ้าสีอ่อน','Wash cold, separately from light colors'))]
        for key, val in details:
            self.label(r, '+ ' + self.tr(key), 9, True).pack(anchor='w', pady=(13, 2))
            self.label(r, val, 11, fg=MID, wraplength=600, justify='left').pack(anchor='w')

    # เปิดสินค้าที่แนะนำพร้อมเลือกไซซ์ตามผลการคำนวณ
    def open_recommended(self,p):
        self.product_state[p['id']]=dict(color=p['color'],size=p.get('recommended_size',32),qty=1,view='FRONT')
        self.product_detail(p)

    # เปลี่ยนมุมภาพสินค้า
    def set_product_view(self, p, v):
        self.product_state[p['id']]['view'] = v
        self._product_detail(p)

    # เปลี่ยนสีหรือไซซ์ที่เลือกในหน้ารายละเอียดสินค้า
    def set_product_option(self, p, key, value):
        self.product_state[p['id']][key] = value
        self._product_detail(p)

    # ปรับจำนวนที่ต้องการซื้อ โดยจำกัดตามสต็อก
    def change_qty(self, p, delta):
        s = self.product_state[p['id']]
        stock = db.variant_stock(p['id'], s['color'], s['size'])
        s['qty'] = max(1, min(stock or 1, db.MAX_PRODUCT_QUANTITY, s['qty'] + delta))
        self._product_detail(p)

    # ตรวจสต็อกและจำนวนรวมไม่เกิน 20 ตัวต่อรุ่น ก่อนเพิ่มลงตะกร้า
    def add_cart(self, p):
        qty=self.product_state[p['id']]['qty']
        if db.product_cart_quantity(self.cart,p['id'])+qty>db.MAX_PRODUCT_QUANTITY:
            self.product_error.configure(text=self.ui('รุ่นนี้ในตะกร้ารวมทุกสีและไซซ์ได้ไม่เกิน 20 ตัว','Maximum 20 units of this product in your bag, across colors and sizes.'));return
        s = self.product_state[p['id']]
        key = (p['id'], s['color'], s['size'])
        stock = db.variant_stock(*key)
        if self.cart.get(key, 0) + s['qty'] > stock:
            return messagebox.showwarning(self.tr('bag'), self.tr('out_stock'))
        self.cart[key] = self.cart.get(key, 0) + s['qty']
        self.toast('✓ ' + self.tr('added'))
        self._product_detail(p)

    # เปิดหน้าช่วยเลือกยีนส์ที่ใช่
    def fit_page(self, push=True):
        self.navigate('fit', self._fit_page, push=push)

    # ฟอร์มสองคอลัมน์ พร้อมคำแนะนำการวัดและตัวอย่างทรงที่เลือกได้
    # J20 | หน้าเลือกทรงยีนส์
    def _fit_page(self):
        b=self.shell();wrap=tk.Frame(b,bg=WHITE);wrap.pack(fill='both',expand=True,padx=30,pady=10)
        holder=tk.Frame(wrap,bg=WHITE);holder.pack(side='left',fill='both',expand=True)
        left=self.scroll_content(holder)
        self.label(left,'02 / FIND YOUR FIT',10,True,fg=MID).pack(anchor='w')
        self.label(left,self.tr('find_fit'),27,True,wraplength=650,justify='left').pack(anchor='w',pady=8)
        self.label(left,self.ui('กรอกขนาดร่างกาย แล้วเลือกทรงที่ชอบ เราจะช่วยหารุ่นและไซซ์ที่ใกล้เคียง','Enter your body measurements and choose a fit. We will suggest a model and size.'),12,fg=MID,wraplength=650,justify='left').pack(anchor='w',pady=(0,12))
        steps=tk.Frame(left,bg='#E9EEF3');steps.pack(fill='x',pady=(0,12))
        self.label(steps,self.ui('1 วัดสัดส่วน   >   2 เลือกทรง   >   3 ดูยีนส์ที่แนะนำ','1 MEASURE   >   2 CHOOSE A FIT   >   3 SEE YOUR JEANS'),11,True,bg='#E9EEF3',fg='#243E55',wraplength=650,justify='left').pack(anchor='w',padx=14,pady=12)
        fields=tk.Frame(left,bg=WHITE);fields.pack(fill='x');self.inputs={};boxes=[]
        measures=[('height','ส่วนสูง (เซนติเมตร)','Height (cm)','วัดจากศีรษะถึงพื้นโดยไม่ใส่รองเท้า','Measure head to floor without shoes.'),('waist','รอบเอว (นิ้ว)','Waist (in)','วัดรอบเอวบริเวณที่ใส่ขอบกางเกง','Measure around where your waistband sits.'),('hip','รอบสะโพก (นิ้ว)','Hip (in)','วัดรอบส่วนที่กว้างที่สุดของสะโพก','Measure around the fullest part of your hips.'),('thigh','รอบต้นขา (นิ้ว)','Thigh (in)','วัดรอบต้นขาบริเวณที่กว้างที่สุด','Measure around the fullest part of your thigh.')]
        for key,th,en,hth,hen in measures:
            box=tk.Frame(fields,bg=WHITE);boxes.append(box)
            self.inputs[key]=self.entry(box,self.ui(th,en))
            previous_input=getattr(self,'last_fit_input',{}).get(key)
            if previous_input is not None:self.inputs[key].insert(0,str(previous_input))
            hint=self.label(box,self.ui(hth,hen),11,fg=MID,wraplength=300,justify='left',anchor='w');hint.pack(fill='x',pady=(6,12))
            box.bind('<Configure>',lambda event,label=hint:label.configure(wraplength=max(120,event.width-8)))
        last=[None]
        def arrange(event):
            columns=2 if event.width>=620 else 1
            if columns==last[0]:return
            last[0]=columns
            for column in range(2):fields.columnconfigure(column,weight=1 if column<columns else 0)
            for index,box in enumerate(boxes):box.grid(row=index//columns,column=index%columns,sticky='nsew',padx=(0,12) if columns==2 and index%2==0 else (0,0))
        fields.bind('<Configure>',arrange)
        self.label(left,self.ui('เลือกทรงที่ชอบ','CHOOSE YOUR FIT'),14,True).pack(anchor='w',pady=(10,4))
        self.label(left,self.ui('กดภาพเพื่อเลือกทรงที่อยากใส่','Select the picture of the fit you like.'),11,fg=MID).pack(anchor='w',pady=(0,8))
        tiles=tk.Frame(left,bg=WHITE);tiles.pack(fill='x');self.pref=tk.StringVar(value='baggy');buttons=[];self._fit_tile_images=[]
        products=db.products()
        def choose(value):
            self.pref.set(value)
            for fit,button in buttons:
                button._selected=fit==value;button.configure(highlightbackground='#A89167' if fit==value else LINE,highlightthickness=3 if fit==value else 1);button._draw_caption()
            self._fit_any_button.configure(fg_color='#243E55' if value=='any' else '#F8F6F0',text_color=WHITE if value=='any' else '#243E55',border_color='#B8A88E',border_width=1)
        self._fit_any_button=self.button(left,self.ui('ยังไม่มีทรงที่ชอบ / ดูทุกทรง','No preferred fit / consider every fit'),lambda:choose('any'),compact=True)
        self._fit_any_button.pack(fill='x',padx=4,pady=(0,10),before=tiles)
        from support import image_jobs
        for fit in FITS:
            product=next((product for product in products if product['fit']==fit),None)
            button=tk.Canvas(tiles,height=220,bg=SOFT,bd=0,highlightthickness=1,highlightbackground=LINE,cursor='hand2')
            button._fit_choice=fit;button._selected=False;button._source=None;button._last_size=None;button._generation=0;button._resize_job=None
            buttons.append((fit,button))
            button.bind('<Button-1>',lambda event,value=fit:choose(value))
            button.bind('<Return>',lambda event,value=fit:choose(value));button.configure(takefocus=True)
            def caption(tile=button,value=fit):
                tile.delete('fit_caption')
                w=max(120,tile.winfo_width());h=max(100,tile.winfo_height())
                title=('✓ ' if tile._selected else '')+self.fit_label(value)
                import tkinter.font as tkfont
                label_width=min(w-24,tkfont.Font(self,font=self.font(10,True)).measure(title)+28)
                x=(w-label_width)/2;y=h-47
                tile.create_rectangle(x,y,x+label_width,y+34,fill='#243E55' if tile._selected else '#F8F6F0',outline='#A89167' if tile._selected else '#D8D2C7',tags='fit_caption')
                tile.create_text(w/2,y+17,text=title,font=self.font(10,True),fill=WHITE if tile._selected else INK,tags='fit_caption')
            button._draw_caption=caption
            def render(tile=button):
                if not tile.winfo_exists():return
                tile._draw_caption();size=(tile.winfo_width(),tile.winfo_height())
                if tile._source is None or min(size)<40 or size==tile._last_size:return
                tile._last_size=size;tile._generation+=1;generation=tile._generation;source=tile._source
                def prepare():return ImageOps.fit(source,size,method=Image.Resampling.LANCZOS,centering=(.5,.65))
                def display(picture):
                    if picture is None or generation!=tile._generation:return
                    tile.delete('fit_photo');photo=gallery_assets.to_photo(picture,master=self);tile._image=photo
                    tile.create_image(0,0,image=photo,anchor='nw',tags='fit_photo');tile.tag_lower('fit_photo');tile._draw_caption()
                image_jobs.submit(self,tile,prepare,display)
            button._render_fit=render
            def resize(event,tile=button):
                if tile._resize_job:
                    try:tile.after_cancel(tile._resize_job)
                    except tk.TclError:pass
                def update():tile._resize_job=None;tile._render_fit()
                tile._resize_job=tile.after(80,update)
            button.bind('<Configure>',resize)
            def cleanup(event,tile=button):
                if event.widget is tile and tile._resize_job:
                    try:tile.after_cancel(tile._resize_job)
                    except tk.TclError:pass
                    tile._resize_job=None
            button.bind('<Destroy>',cleanup)
            if product:
                def load(p=product):return gallery_assets.lower_body_preview(p['id'],p['color'],gallery_assets.standing_view(p))
                def ready(picture,tile=button):
                    tile._source=picture;tile._render_fit()
                image_jobs.submit(self,button,load,ready)
        tile_columns=[None]
        def arrange_tiles(event):
            columns=max(1,min(5,event.width//150))
            if columns==tile_columns[0]:return
            tile_columns[0]=columns
            for column in range(5):tiles.columnconfigure(column,weight=1 if column<columns else 0)
            for index,(_,button) in enumerate(buttons):button.grid(row=index//columns,column=index%columns,sticky='ew',padx=4,pady=5)
        tiles.bind('<Configure>',arrange_tiles);choose(getattr(self,'last_fit_input',{}).get('preferred_fit','baggy'))
        self.button(left,self.tr('analyze'),self.run_fit,dark=True).pack(anchor='w',pady=18)
        self.label(left,self.ui('เทียบขนาดร่างกายกับตารางไซซ์ของแต่ละรุ่นและไซซ์ที่มีสต็อก','We compare your measurements with each model’s size chart and available sizes.'),11,fg=MID,wraplength=650,justify='left').pack(anchor='w',pady=(0,15))
        art_holder=tk.Frame(wrap,bg=SOFT,width=340);art_holder.pack(side='right',fill='both',padx=(20,0));art_holder.pack_propagate(False)
        art=self.scroll_content(art_holder);art.configure(bg=SOFT)
        self.label(art,'FIT / BODY / DENIM',10,True,bg=SOFT,fg=MID).pack(anchor='w',padx=20,pady=18)
        drawing=tk.Canvas(art,bg=SOFT,height=200,highlightthickness=0);drawing.pack(fill='x',padx=20)
        def draw(event):
            drawing.delete('all');cx=event.width/2-12
            outline=[cx-50,22,cx+50,22,cx+70,175,cx+15,175,cx,80,cx-15,175,cx-70,175,cx-50,22]
            drawing.create_polygon(*outline,fill='#D2DCE5',outline='#42576A',width=2)
            for y,label in ((22,'A'),(58,'B'),(102,'C')):
                drawing.create_line(cx-85,y,cx+85,y,fill='#42576A',dash=(4,4))
                drawing.create_text(cx+94,y,text=label,anchor='w',font=self.font(12,True),fill='#243E55')
        drawing.bind('<Configure>',draw)
        self.label(art,'FIND THE FORM\nTHAT WORKS.',23,True,bg=SOFT,justify='left',wraplength=280).pack(anchor='w',padx=20,pady=15)
        for th,en in [('A รอบเอว — วัดรอบตำแหน่งขอบกางเกง','A WAIST — around your waistband'),('B รอบสะโพก — วัดรอบส่วนที่กว้างที่สุด','B HIP — around the fullest part'),('C รอบต้นขา — วัดรอบส่วนที่กว้างที่สุด','C THIGH — around the fullest part')]:
            self.label(art,self.ui(th,en),12,bg=SOFT,fg='#243E55',wraplength=280,justify='left',anchor='w').pack(fill='x',padx=20,pady=6)
        self.label(art,self.ui('ใช้สายวัดแนบตัวพอดี ไม่รัดแน่น\nรอบเอว สะโพก และต้นขาใช้หน่วยนิ้ว\n1 นิ้ว = 2.54 เซนติเมตร','Keep the tape snug, without pulling tight.\nUse inches for waist, hip and thigh.\n1 inch = 2.54 cm'),11,bg=SOFT,fg=MID,wraplength=280,justify='left').pack(anchor='w',padx=20,pady=15)
        self.button(art,self.ui('ดูวิธีวัดไซซ์','OPEN SIZE GUIDE'),self.size_guide,compact=True).pack(anchor='w',padx=20,pady=(0,20))

    # ตรวจสัดส่วนที่กรอกและคำนวณรายการสินค้าและไซซ์ที่แนะนำ
    # J53 | ตัวเลือกไม่มีทรงที่ชอบและผลแนะนำ
    def run_fit(self):
        try:
            vals = {k: float(v.get()) for k, v in self.inputs.items()}
            if not all(math.isfinite(v) and v>0 for v in vals.values()):raise ValueError()
        except ValueError:
            return messagebox.showerror('FIT', self.tr('invalid_measure'))
        admin_data.log_event(self.user['id'], 'fit_search')
        self.fit_results = recommend(
            sizing.candidates(db.products()),
            vals['waist'],
            vals['hip'],
            vals['thigh'],
            vals['height'],
            self.pref.get(),
        )
        self.last_fit_input = {
            'height': vals['height'],
            'waist': vals['waist'],
            'hip': vals['hip'],
            'thigh': vals['thigh'],
            'preferred_fit': self.pref.get(),
        }
        db.save_fit_history(
            self.user['id'],
            vals['height'],
            vals['waist'],
            vals['hip'],
            vals['thigh'],
            self.pref.get(),
            [product['id'] for product, reasons in self.fit_results],
        )
        self.navigate('fit_results', self._fit_results)

    # แสดงผลการแนะนำยีนส์พร้อมไซซ์ที่แนะนำ
    def _fit_results(self):
        b = self.scroll_content(self.shell())
        self.label(b, '03 / YOUR FITS', 9, True, fg=MID).pack(anchor='w', padx=30, pady=(15, 0))
        self.label(b, self.tr('recommended'), 32, True).pack(anchor='w', padx=30, pady=(0, 10))
        fit_input = getattr(self, 'last_fit_input', None)
        cards = []
        if not self.fit_results:
            empty = tk.Frame(b, bg='#F8F6F1', highlightbackground='#E6E0D6', highlightthickness=1)
            empty.pack(fill='x', padx=30, pady=16)
            self.label(empty, self.ui('ยังไม่มีรุ่นและไซซ์ที่เหมาะกับสัดส่วนนี้','No suitable model and size found'), 21, True, bg='#F8F6F1', wraplength=800).pack(anchor='w', padx=24, pady=(24, 12))
            self.label(empty, self.ui('จากสินค้าและไซซ์ที่มีสต็อกตอนนี้ ยังไม่มีตัวที่ผ่านเงื่อนไขเอว สะโพก และต้นขา\nตรวจหน่วยและสัดส่วนที่กรอกอีกครั้ง หรือดูตารางไซซ์และติดต่อร้านเพื่อช่วยเลือก', 'None of the sizes currently in stock meets the waist, hip and thigh requirements.\nCheck your measurements and units, or consult the size chart and ask the store for help.'), 12, fg=MID, bg='#F8F6F1', wraplength=800).pack(anchor='w', padx=24, pady=(0, 24))
            empty.bind('<Configure>', lambda event: [w.configure(wraplength=max(200,event.width-52)) for w in empty.winfo_children() if isinstance(w,tk.Label)])
            self.button(empty, self.ui('ติดต่อร้าน','CONTACT THE STORE'), self.contact, compact=True).pack(anchor='w', padx=20, pady=(0, 20))
        else:
            self.label(b, self.ui('รุ่นและไซซ์ที่มีสต็อก พร้อมเหตุผลประกอบการเลือก','Available models and sizes, with reasons for each suggestion'), 12, fg=MID, wraplength=850).pack(anchor='w', padx=30, pady=(0, 12))
        grid = tk.Frame(b, bg=WHITE)
        grid.pack(fill='x', padx=25)
        for i, (p, reasons) in enumerate(self.fit_results):
            c = card(grid); cards.append(c)
            picture = self.product_picture(c, p, p['color'], gallery_assets.standing_view(p), height=200, expand=True, lower_body=True)
            picture.pack_configure(fill='x', expand=False);picture.pack_propagate(False)
            self.label(c, f"0{i + 1}  {p['name']} / {self.tr('size')} {db.size_label(p.get('recommended_size',32))}", 14, True, wraplength=300).pack(anchor='w', padx=14, pady=(12, 8))
            recommended_price=db.price_for_size(p,p.get('recommended_size',32))
            self.label(c,f"฿{recommended_price:,.2f}",15,True).pack(anchor='w',padx=14,pady=4)
            self.price_before_vat(c,recommended_price,padx=14,unit=True)
            self.label(c,self.ui('ขนาดตามตารางไซซ์ของรุ่น','Dimensions from the model’s size chart'),10,fg=MID,wraplength=300).pack(anchor='w',padx=14,pady=(0,10))
            if fit_input:
                details = fit_details(p, fit_input['waist'], fit_input['hip'], fit_input['thigh'], fit_input['height'])
                comparison = tk.Frame(c, bg='#F8F6F1');comparison.pack(fill='x', padx=12, pady=(0, 8))
                self.label(comparison, self.ui('ทำไมแนะนำไซซ์นี้','WHY THIS SIZE'), 11, True, bg='#F8F6F1').pack(anchor='w', padx=12, pady=(12, 8))
                if details:
                    unit = self.ui('นิ้ว','in')
                    for key, th, en in [('waist','เอว','Waist'),('hip','สะโพก','Hip'),('thigh','ต้นขา','Thigh')]:
                        room = details[key+'_room']
                        feel = self.ui('พอดีตามขนาด' if room <= .5 else 'มีระยะเผื่อเล็กน้อย', 'Close by measurement' if room <= .5 else 'A little room') if key=='waist' else self.ui('มีระยะเผื่อตามทรง','Room for this silhouette')
                        text = f"{self.ui(th,en)}: {fit_input[key]:g} → {p[key]:g} {unit}\n{feel} (+{room:g} {unit})"
                        self.label(comparison, text, 11, bg='#F8F6F1', fg=MID, wraplength=280).pack(anchor='w', padx=12, pady=(0, 10))
                    match = p['fit'] == fit_input['preferred_fit']
                    if fit_input['preferred_fit']=='any':
                        text=self.ui('ทรงที่ผ่านเงื่อนไขสัดส่วน: ','A fit meeting your measurements: ')
                    else:text = self.ui('ตรงกับทรงที่คุณเลือก: ' if match else 'ทรงทางเลือกที่ผ่านเงื่อนไขสัดส่วน: ', 'Your preferred fit: ' if match else 'An alternative fit meeting your measurements: ')
                    self.label(comparison, text+self.fit_label(p['fit']), 11, True, bg='#F8F6F1', fg='#243E55', wraplength=280).pack(anchor='w', padx=12, pady=(0, 10))
                    self.label(comparison, self.ui(f"ขาด้านใน {p['inseam']:g} นิ้ว · เทียบความยาวจากส่วนสูง", f"Inseam {p['inseam']:g} in · length compared using height"), 10, fg=MID, bg='#F8F6F1', wraplength=280).pack(anchor='w', padx=12, pady=(0, 12))
            self.button(c, self.tr('view_product'), lambda z=p: self.open_recommended(z), compact=True).pack(anchor='w', padx=8, pady=(0, 8))
            self.button(c, self.ui('ดูตารางไซซ์','SIZE CHART'), lambda z=p: self.size_chart(z), compact=True).pack(anchor='w', padx=8, pady=(0, 12))
            def wrap_card(event, widget=c):
                def update_labels(parent):
                    for child in parent.winfo_children():
                        if isinstance(child, tk.Label):child.configure(wraplength=max(160,event.width-52))
                        elif isinstance(child, tk.Frame):update_labels(child)
                update_labels(widget)
            c.bind('<Configure>', wrap_card)
        previous = [None]
        def arrange(event):
            columns = max(1, min(3, event.width//360))
            if columns == previous[0]:return
            previous[0] = columns
            for column in range(3):grid.columnconfigure(column, weight=1 if column < columns else 0)
            for index, widget in enumerate(cards):widget.grid(row=index//columns, column=index%columns, padx=6, pady=6, sticky='nsew')
        grid.bind('<Configure>', arrange)
        self._fit_results_ui = {'cards': cards, 'empty': not bool(self.fit_results)}
        actions = tk.Frame(b, bg=WHITE)
        actions.pack(fill='x', padx=30, pady=15)
        self.button(actions, self.tr('adjust'), self.fit_page).pack(side='left')
        self.button(actions, self.tr('view_all'), self.shop).pack(side='left', padx=8)

    # เปิดหน้าคู่มือวัดไซซ์
    def size_guide(self, push=True):
        self.navigate('guide', self._size_guide, push=push)

    # แสดงวิธีวัด ข้อมูลหน่วย และภาพอธิบายตำแหน่งการวัด
    def _size_guide(self):
        b = self.scroll_content(self.shell())
        wrap = tk.Frame(b, bg=WHITE)
        wrap.pack(fill='both', expand=True, padx=35, pady=15)
        left = tk.Frame(wrap, bg=WHITE)
        left.pack(side='left', fill='both', expand=True)
        self.label(left, '05 / SIZE GUIDE', 9, True, fg=MID).pack(anchor='w')
        self.label(left, self.tr('guide_title'), 34, True, justify='left').pack(anchor='w', pady=8)
        self.label(left, self.tr('guide_sub'), 9, fg=MID).pack(anchor='w', pady=(0, 12))
        for key in ('waist_guide', 'hip_guide', 'thigh_guide', 'rise_guide', 'inseam_guide', 'opening_guide'):
            self.label(left, self.tr(key), 10, justify='left').pack(anchor='w', pady=5)
        tools=tk.Frame(left,bg='#F8F6F1',highlightbackground='#E6E0D6',highlightthickness=1)
        tools.pack(fill='x',padx=(0,24),pady=(26,0))
        graphic=tk.Canvas(tools,width=185,height=210,bg='#F8F6F1',highlightthickness=0)
        # สมุดบันทึก ดินสอ และสายวัด เป็นภาพวาดในโปรแกรม ไม่โหลดรูปภายนอก
        graphic.create_rectangle(22,26,123,154,fill='#FFFFFF',outline='#B6A180',width=1)
        for y in (48,72,96,120):graphic.create_line(37,y,104,y,fill='#D7DBDF',width=1)
        graphic.create_line(29,26,29,154,fill='#B6A180')
        graphic.create_polygon(136,28,144,30,113,121,105,126,108,115,fill='#243E55',outline='#243E55')
        graphic.create_polygon(105,126,108,115,113,121,fill='#B6A180',outline='#B6A180')
        graphic.create_line(39,165,70,165,70,180,143,180,143,145,fill='#B6A180',width=16,joinstyle='round')
        for x in range(80,139,10):graphic.create_line(x,174,x,184,fill='#655B4D',width=1)
        graphic.create_rectangle(136,134,151,149,fill='#9AA7B1',outline='#677989')
        conversion=tk.Frame(tools,bg='#F8F6F1')
        self.label(conversion,self.ui('แปลงหน่วย','UNIT CONVERTER'),17,True,bg='#F8F6F1',fg='#243E55').pack(anchor='w',pady=(4,14))
        inputs=tk.Frame(conversion,bg='#F8F6F1');inputs.pack(fill='x')
        inches=tk.StringVar(value='');centimeters=tk.StringVar(value='');variables={'IN':inches,'CM':centimeters}
        for index,(unit,label) in enumerate([('IN',self.ui('นิ้ว','Inches')),('CM',self.ui('เซนติเมตร','Centimeters'))]):
            box=tk.Frame(inputs,bg='#F8F6F1');box.grid(row=0,column=index,sticky='nsew',padx=(0,12) if index==0 else 0);inputs.columnconfigure(index,weight=1)
            self.label(box,label,12,bg='#F8F6F1',fg=MID).pack(anchor='w',pady=(0,6))
            tk.Entry(box,textvariable=variables[unit],font=self.font(16),width=9,bg=WHITE,fg=INK,relief='solid',bd=1).pack(fill='x',ipady=8)
        status=self.label(conversion,'1 in = 2.54 cm',11,bg='#F8F6F1',fg='#877354');status.pack(anchor='w',pady=(12,0))
        changing=[False]
        def convert(source):
            if changing[0]:return
            changing[0]=True
            try:
                text=variables[source].get().strip();target='CM' if source=='IN' else 'IN'
                if not text:variables[target].set('');status.configure(text='1 in = 2.54 cm',fg='#877354');return
                value=float(text)
                if not math.isfinite(value) or value<0:raise ValueError()
                result=value*2.54 if source=='IN' else value/2.54
                if not math.isfinite(result):raise ValueError()
                variables[target].set(f'{result:.2f}'.rstrip('0').rstrip('.'))
                status.configure(text='1 in = 2.54 cm',fg='#877354')
            except (ValueError,OverflowError):
                variables['CM' if source=='IN' else 'IN'].set('');status.configure(text=self.ui('กรอกตัวเลขตั้งแต่ 0 ขึ้นไป','Enter a number of 0 or more'),fg='#BB2020')
            finally:changing[0]=False
        inches.trace_add('write',lambda *args:convert('IN'));centimeters.trace_add('write',lambda *args:convert('CM'))
        placement=[None]
        def arrange_tools(event):
            stacked=event.width<500
            if placement[0]==stacked:return
            placement[0]=stacked;graphic.grid_forget();conversion.grid_forget()
            graphic.grid(row=0,column=0,sticky='w',padx=(8,0),pady=(12,0))
            conversion.grid(row=1 if stacked else 0,column=0 if stacked else 1,sticky='ew',padx=20,pady=20)
            tools.columnconfigure(0,weight=1 if stacked else 0);tools.columnconfigure(1,weight=0 if stacked else 1)
        tools.bind('<Configure>',arrange_tools)
        self._guide_converter={'inches':inches,'centimeters':centimeters,'status':status,'panel':tools}
        self.measurement_art(wrap)

    # วาดภาพกางเกงและตำแหน่ง A–F พร้อมตารางไซซ์สากล
    # J52 | ตัวอักษร A–F บนรูปวิธีวัด
    def measurement_art(self,parent):
        art=tk.Canvas(parent,bg='#E5E8EB',width=640,height=700,highlightthickness=0)
        art.pack(fill='both',expand=True,padx=20,pady=15)
        def draw(event):
            art.delete('all');w=max(1,event.width);h=max(1,event.height);sx=min(w/640,h/700);ox=(w-640*sx)/2
            def xy(points):return [ox+v*sx if i%2==0 else v*sx for i,v in enumerate(points)]
            art._measurement_scale=(sx,sx)
            art.create_text(w/2,26*sx,text=self.ui('วิธีวัดกางเกง · หน่วยนิ้ว / เซนติเมตร','JEANS MEASUREMENTS · INCHES / CM'),font=self.font(round(max(11,14*sx)),True),fill=INK)
            outline=[155,90,390,90,420,440,325,440,273,215,245,440,140,440,155,90]
            art.create_polygon(*xy(outline),fill='#486781',outline='#1C344B',width=3)
            art.create_line(*xy([155,112,390,112]),fill='#C4CDCD',width=2)
            art.create_line(*xy([270,90,273,215]),fill='#C4CDCD',width=2)
            art.create_line(*xy([180,112,190,160,230,168]),fill='#C4CDCD',width=2,smooth=True)
            art.create_line(*xy([368,112,360,160,318,168]),fill='#C4CDCD',width=2,smooth=True)
            annotations=[('A รอบเอว',[150,78,390,78],470,90),('B รอบสะโพก',[150,166,398,166],470,160),('C รอบต้นขา',[148,220,270,220],470,225),('D เป้าหน้า',[274,91,274,213],470,285),('E ขาด้านใน',[280,220,327,437],470,355),('F รอบปลายขา',[140,451,245,451],470,425)]
            badge_positions=[(270,61),(124,166),(122,220),(298,150),(330,320),(192,475)]
            art._measurement_keys={}
            for index,(text,coords,x,y) in enumerate(annotations):
                if self.lang=='EN':text=('A Waist','B Hip','C Thigh','D Front rise','E Inseam','F Leg opening')[index]
                key='ABCDEF'[index]
                line=art.create_line(*xy(coords),fill='#FFDE8C',width=3,arrow='both',tags=('measure_'+key,))
                bx,by=badge_positions[index];cx,cy=xy([bx,by]);radius=max(10,12*sx)
                art.create_oval(cx-radius,cy-radius,cx+radius,cy+radius,fill='#193244',outline='#FFDE8C',width=1)
                label=art.create_text(cx,cy,text=key,fill='#FFF9EC',font=self.font(round(max(11,11*sx)),True),tags=('measure_label_'+key,))
                art._measurement_keys[key]=(line,label)
                art.create_text(ox+x*sx,y*sx,text=text,anchor='w',font=self.font(round(max(11,10*sx)),True),fill=INK,width=160*sx)
            art.create_text(ox+25*sx,495*sx,text=self.ui('A / B / C / F: วัดความกว้างตอนวางราบ แล้วคูณ 2 เพื่อได้รอบวง\nD / E: วัดความยาวตามแนวตะเข็บ ไม่ต้องคูณ 2','A / B / C / F: Flat width × 2 gives circumference.\nD / E: Measure seam length without multiplying.'),anchor='nw',font=self.font(round(max(11,12*sx))),fill=INK,width=590*sx)
            art.create_text(ox+25*sx,575*sx,text=self.ui('ไซซ์สากล: XXS · XS · S · M · L · XL · 2XL · 3XL · 4XL · 5XL\nเลือกไซซ์แล้วดูขนาดเฉพาะรุ่นในตาราง ขนาดแต่ละทรงอาจต่างกัน\n1 นิ้ว = 2.54 เซนติเมตร','SIZES: XXS · XS · S · M · L · XL · 2XL · 3XL · 4XL · 5XL\nCheck measurements for your chosen model; fits can differ.\n1 inch = 2.54 cm'),anchor='nw',font=self.font(round(max(11,12*sx))),fill=INK,width=590*sx)
        art.bind('<Configure>',draw);return art


    # เปิดหน้าตะกร้าสินค้า
    def bag(self, push=True):
        self.navigate('bag', self._bag, push=push)

    def selected_cart(self):
        excluded=getattr(self,'cart_excluded',set()) & self.cart.keys()
        self.cart_excluded=excluded
        return {key:qty for key,qty in self.cart.items() if key not in excluded}

    def select_cart_item(self,key,selected):
        self.selected_cart()
        if selected:self.cart_excluded.discard(key)
        else:self.cart_excluded.add(key)
        self._bag()

    def select_all_cart(self,selected):
        self.cart_excluded=set() if selected else set(self.cart)
        self._bag()

    def move_cart_selection(self,key,target):
        # คงการเลือกแถวที่รวม หากผู้ใช้เลือกแถวเดิมแถวใดแถวหนึ่งไว้
        excluded=getattr(self,'cart_excluded',set())
        selected=key not in excluded or (target in self.cart and target not in excluded)
        excluded.discard(key)
        if selected:excluded.discard(target)
        else:excluded.add(target)
        self.cart_excluded=excluded

    # แสดงรูปสินค้าในตะกร้า พร้อมเปลี่ยนไซซ์ จำนวน และสรุปยอด
    # J23 | ตะกร้า
    def _bag(self):
        b=self.scroll_content(self.shell())
        self.label(b,self.tr('your_bag'),28,True).pack(anchor='w',padx=30,pady=15)
        selected_items=self.selected_cart()
        self._cart_selection_ui={'items':{},'selected':selected_items}
        if self.cart:
            selection_bar=tk.Frame(b,bg=WHITE);selection_bar.pack(fill='x',padx=30,pady=(0,8))
            all_selected=tk.IntVar(value=int(len(selected_items)==len(self.cart)))
            select_all=check_field(selection_bar,text=self.ui('เลือกทั้งหมด','Select all'),variable=all_selected,command=lambda:self.select_all_cart(all_selected.get()==1),font=self.font(12,True),bg=WHITE,activebackground=WHITE)
            select_all.pack(side='left')
            if selected_items and len(selected_items)!=len(self.cart):all_selected.set(-1)
            self.label(selection_bar,self.ui(f'เลือก {len(selected_items)} จาก {len(self.cart)} รายการ',f'{len(selected_items)} of {len(self.cart)} items selected'),11,fg=MID).pack(side='left',padx=16)
            self._cart_selection_ui.update(all=select_all,all_variable=all_selected)
        total=0
        if not self.cart:self.label(b,self.tr('empty_bag'),12).pack(padx=30,pady=20)
        for key,qty in list(self.cart.items()):
            pid,color,size=key;p=db.product(pid)
            if not p:continue
            price=db.price_for_size(p,size)
            if key in selected_items:total+=price*qty
            row=tk.Frame(b,bg=WHITE,highlightbackground=LINE,highlightthickness=1);row.pack(fill='x',padx=30,pady=6)
            checked=tk.BooleanVar(value=key in selected_items)
            selector=check_field(row,variable=checked,command=lambda k=key,v=checked:self.select_cart_item(k,v.get()),bg=WHITE,activebackground=WHITE,takefocus=True)
            selector.pack(side='left',padx=(10,0))
            self._cart_selection_ui['items'][key]={'button':selector,'variable':checked}
            from support import cart_images,image_jobs
            stage=tk.Frame(row,bg=SOFT,width=110,height=130)
            stage.pack(side='left',padx=12,pady=12);stage.pack_propagate(False)
            picture=tk.Label(stage,bg=SOFT,cursor='hand2',text=self.ui('กำลังโหลดรูป…','Loading…'),font=self.font(8),wraplength=104)
            picture.pack(fill='both',expand=True);picture._cart_thumbnail=True
            self._cart_selection_ui['items'][key]['thumbnail']=picture
            def ready(result,label=picture,product_id=pid,selected_color=color):
                if result is None:label.configure(text=self.ui('ยังไม่มีรูปสีนี้','No photo for this color'));return
                image,view,cropped=result
                label._image=gallery_assets.to_photo(image,master=self)
                label.configure(image=label._image,text='');label._cart_source=(product_id,selected_color,view,cropped)
            image_jobs.submit(self,picture,lambda product_id=pid,selected_color=color:cart_images.thumbnail(product_id,selected_color),ready)
            def open_item(event=None,product=p,selected_color=color,selected_size=size):
                state=self.product_state.setdefault(product['id'],dict(color=selected_color,size=selected_size,qty=1,view='FRONT'))
                state['color']=selected_color;state['size']=selected_size
                state['view']=gallery_assets.standing_view(dict(product,color=selected_color))
                self.product_detail(product)
            picture.bind('<Button-1>',open_item)
            info=tk.Frame(row,bg=WHITE);info.pack(side='left',fill='both',expand=True,padx=(0,15),pady=12)
            self.label(info,p['name'],13,True,wraplength=450).pack(anchor='w')
            # เลือกสีจากตะกร้าได้โดยคงไซซ์และจำนวนเดิม ตรวจสต็อกก่อนย้ายรายการ
            colors=tk.Frame(info,bg=WHITE);colors.pack(anchor='w',pady=(5,10))
            palette={'black':'#191919','dark_indigo':'#23344D','raw_indigo':'#263D59','washed_blue':'#6E93AC','light_blue':'#B1CDDF','vintage_blue':'#64869B','grey':'#8B8D90'}
            for index,option in enumerate(sorted({v['color'] for v in db.variants(pid)})):
                selected=option==color;stock=db.variant_stock(pid,option,size)
                choice=tk.Frame(colors,bg=WHITE,highlightbackground=INK if selected else LINE,highlightthickness=2 if selected else 1,cursor='hand2',takefocus=True)
                choice.grid(row=index//3,column=index%3,sticky='w',padx=(0,6),pady=3)
                chip=tk.Canvas(choice,width=22,height=22,bg=palette.get(option,'#777777'),highlightthickness=1,highlightbackground=LINE,cursor='hand2');chip.pack(side='left',padx=6,pady=6)
                caption=('✓ ' if selected else '')+self.color_label(option)
                if not stock:caption+=self.ui(' · หมดในไซซ์นี้',' · Sold out in this size')
                text=self.label(choice,caption,10,selected,fg=INK if stock else MID);text.pack(side='left',padx=(0,8))
                choice._cart_color=(key,option)
                for widget in (choice,chip,text):widget.bind('<Button-1>',lambda event,k=key,c=option:self.cart_color(k,c))
                choice.bind('<Return>',lambda event,k=key,c=option:self.cart_color(k,c))
                choice.bind('<space>',lambda event,k=key,c=option:self.cart_color(k,c))
            controls=tk.Frame(info,bg=WHITE);controls.pack(fill='x')
            self.label(controls,self.tr('size'),11).pack(side='left',padx=(0,8))
            choices=[db.size_label(v['size']) for v in db.variants(pid) if v['color']==color]
            picker=select_field(controls,values=choices,state='readonly',width=7);picker.set(db.size_label(size));picker.pack(side='left')
            picker.bind('<<ComboboxSelected>>',lambda e,k=key,c=picker:self.cart_size(k,db.size_key(c.get())))
            self.label(controls,f"฿{price*qty:,.2f}",12,True).pack(side='right',padx=(12,0))
            self.price_before_vat(info,price,unit=True)
            if qty>1:self.price_before_vat(info,price*qty)
            self.button(controls,'ลบ',lambda k=key:self.remove_cart(k),compact=True).pack(side='right',padx=(8,0))
            self.button(controls,'+',lambda k=key:self.cart_change(k,1),compact=True).pack(side='right')
            self.label(controls,str(qty),12,True).pack(side='right',padx=10)
            self.button(controls,'−',lambda k=key:self.cart_change(k,-1),compact=True).pack(side='right')
        self.cart_warning=self.label(b,'',12,True,fg='#BB2020');self.cart_warning.pack(anchor='w',padx=30,pady=10)
        try:
            if selected_items:db.validate_cart_quantities(selected_items)
        except ValueError as exc:self.cart_warning.configure(text=str(exc))
        if self.cart:self.reward_summary(b,total,cart=selected_items)
        self._cart_selection_ui['subtotal']=total
        checkout_button=self.button(b,self.tr('checkout'),self.checkout,dark=True)
        checkout_button.configure(state='normal' if selected_items else 'disabled');checkout_button.pack(anchor='e',padx=30,pady=15)
        self._cart_selection_ui['checkout']=checkout_button
        self.button(b,self.tr('continue_shop'),self.shop).pack(anchor='e',padx=30,pady=10)


    # เพิ่มหรือลดจำนวนในตะกร้า โดยตรวจสต็อกและจำนวนสั่งซื้อสูงสุด
    def cart_change(self,key,d):
        if key not in self.cart:return
        target=self.cart[key]+d
        if d>0 and db.product_cart_quantity(self.cart,key[0])+d>db.MAX_PRODUCT_QUANTITY:
            self.cart_warning.configure(text=self.ui('เลือกสินค้าแต่ละรุ่นได้ไม่เกิน 20 ตัว','Maximum 20 units per product.'));return
        self.cart[key]=max(0,min(db.variant_stock(*key),target))
        if not self.cart[key]:
            del self.cart[key]
            getattr(self,'cart_excluded',set()).discard(key)
        self._bag()


    # ลบรายการที่เลือกออกจากตะกร้า
    def remove_cart(self, key):
        self.cart.pop(key, None)
        getattr(self,'cart_excluded',set()).discard(key)
        self._bag()

    # เปิดหน้ากรอกข้อมูลจัดส่งเมื่อมีสินค้าในตะกร้า
    def checkout(self, push=True):
        if not self.selected_cart():
            return messagebox.showwarning(self.tr('bag'),self.ui('กรุณาเลือกสินค้าอย่างน้อย 1 รายการ','Select at least one item.'))
        self.navigate('checkout', self._checkout, push=push)

    # แสดงข้อมูลจัดส่งที่บันทึกไว้และยอดชำระก่อนยืนยันคำสั่งซื้อ
    # J25 | หน้าสั่งซื้อ
    def _checkout(self):
        b=self.scroll_content(self.shell());self.user=db.user(self.user['id'])
        self.label(b,self.ui('ข้อมูลจัดส่ง','Delivery details'),26,True).pack(anchor='w',padx=30,pady=15)
        f=tk.Frame(b,bg=WHITE);f.pack(fill='x',padx=30)
        self.cn=self.entry(f,self.tr('customer_name'))
        name=self.user['delivery_name'] or (self.user['first_name']+' '+self.user['last_name']).strip()
        self.cn.insert(0,'' if name.casefold()=='demo customer' else name)
        self.cp=self.phone_entry(f);self.cp.insert(0,self.user['phone'])
        self.ca=self.entry(f,self.tr('address'));self.ca.insert(0,self.user['address'])
        self.cz=self.entry(f,self.ui('รหัสไปรษณีย์ (5 หลัก)','Postal code (5 digits)'));self.cz.insert(0,self.user['postal_code'])
        self.label(f,self.ui('บัญชีรับเงินคืน (กรอกได้ หากต้องการ)','Refund account (optional)'),17,True).pack(anchor='w',pady=(18,6))
        self.checkout_bank={}
        for key,column,th,en in [('bank','refund_bank','ธนาคาร','Bank'),('name','refund_name','ชื่อเจ้าของบัญชี','Account holder'),('account','refund_account','เลขบัญชี','Account number')]:
            entry=self.entry(f,self.ui(th,en));entry.insert(0,self.user.get(column,'') or '');self.checkout_bank[key]=entry
        self.label(f,self.ui('ข้อมูลจัดส่งจะบันทึกไว้ในบัญชีนี้ แก้ไขได้ก่อนยืนยันคำสั่งซื้อ','Delivery details are saved to this account and can be changed before ordering.'),11,fg=MID,wraplength=850).pack(anchor='w',pady=12)
        selected_items=self.selected_cart()
        subtotal=sum(db.price_for_size(db.product(k[0]),k[2])*qty for k,qty in selected_items.items())
        self.label(f,self.ui('รายการสินค้า','Order items'),17,True).pack(anchor='w',pady=(16,6))
        from support import order_amounts
        totals=product_promotions.cart_quote(selected_items,self.user['id'])
        rows=[dict(name=db.product(pid)['name'],color=color,size=size,quantity=qty,price=db.price_for_size(db.product(pid),size)) for (pid,color,size),qty in selected_items.items()]
        for item in order_amounts.lines(rows,totals['total']):
            self.label(f,f"{item['name']} / {self.color_label(item['color'])} / {db.size_label(item['size'])} × {item['quantity']}",12,wraplength=1000,justify='left').pack(anchor='w',pady=4)
            prices=tk.Frame(f,bg=WHITE);prices.pack(anchor='w',pady=(0,8))
            if item['net_total']<item['original_total']:
                font=tkfont.Font(self,font=self.font(11));font.configure(overstrike=1)
                old=self.label(prices,f"฿{item['original_total']:,.2f}",11,fg=MID);old.configure(font=font);old._price_font=font;old.pack(side='left',padx=(0,10))
            self.label(prices,f"฿{item['net_total']:,.2f}",12,True,fg='#8C2635').pack(side='left')
        if len(rows)>1 and totals['discount_amount']:self.label(f,self.ui('ยอดแต่ละรายการแบ่งส่วนลดตามสัดส่วนราคาสินค้า','Line totals allocate the order discount in proportion to item prices.'),10,fg=MID,wraplength=900).pack(anchor='w')
        self.reward_summary(f,subtotal,cart=selected_items,padx=0)
        self.checkout_error=self.label(f,'',12,True,fg='#BB2020');self.checkout_error.pack(anchor='w',pady=8)
        self.button(f,self.tr('create_order'),self.place_order,dark=True).pack(anchor='w',pady=18)


    # ตรวจข้อมูล สร้างคำสั่งซื้อ บันทึกที่อยู่ และเปิดหน้าชำระเงิน
    def place_order(self):
        try:
            if not self.cz.get().strip():raise ValueError('กรอกรหัสไปรษณีย์ 5 หลัก')
            selected_items=self.selected_cart()
            if not selected_items:raise ValueError(self.ui('กรุณาเลือกสินค้าอย่างน้อย 1 รายการ','Select at least one item.'))
            oid=db.create_order(self.user['id'],self.cn.get(),self.cp.get(),self.ca.get(),selected_items,self.cz.get(),refund_details={k:v.get() for k,v in self.checkout_bank.items()})
        except (ValueError,PermissionError) as exc:self.checkout_error.configure(text=str(exc));return
        for key in selected_items:
            self.cart.pop(key,None)
            self.cart_excluded.discard(key)
        self.user=db.user(self.user['id']);self.my_orders();self.receipt_window(oid)


    # เปิดหน้าประวัติคำสั่งซื้อของบัญชี
    def my_orders(self, push=True):
        self.navigate('orders', self._orders, push=push)

    # แสดงประวัติคำสั่งซื้อ ปุ่มดูสินค้า การจัดส่ง และหลักฐานชำระเงิน
    # J27 | หน้ารายการคำสั่งซื้อ
    def _orders(self):
        b = self.shell()
        self.label(b, self.tr('orders'), 30, True).pack(anchor='w', padx=35, pady=(18, 10))
        self.label(b, self.user['email'], 9, fg=MID).pack(anchor='w', padx=35, pady=(0, 5))
        self.button(b, self.ui('รีเฟรชคำสั่งซื้อ', 'Refresh orders'), self._orders, compact=True).pack(anchor='w', padx=35, pady=(0, 8))
        orders = db.orders(self.user['id'])
        if not orders:
            self.orders_empty_state(b)
            return
        holder = tk.Frame(b, bg=WHITE)
        holder.pack(fill='both', expand=True, padx=35, pady=(0, 15))
        scroll = ctk.CTkScrollbar(holder,orientation='vertical',fg_color=WHITE,button_color='#ADB8C3',button_hover_color='#52697D')
        scroll.pack(side='right', fill='y')
        canvas = tk.Canvas(holder, bg=WHITE, highlightthickness=0, yscrollcommand=scroll.set)
        canvas.pack(fill='both', expand=True)
        scroll.configure(command=canvas.yview)
        rows = tk.Frame(canvas, bg=WHITE)
        item = canvas.create_window((0, 0), window=rows, anchor='nw')
        rows.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(item, width=e.width))
        canvas.bind_all('<MouseWheel>', lambda e: canvas.yview_scroll(int(-e.delta / 120), 'units'))
        for o in orders:
            r = tk.Frame(rows, bg=WHITE, highlightbackground=LINE, highlightthickness=1)
            r.pack(fill='x', pady=4)
            header = tk.Frame(r, bg=WHITE)
            header.pack(fill='x', padx=12, pady=(10, 3))
            self.label(header, self.ui('หมายเลขคำสั่งซื้อ','Order number')+f" {db.order_number(o)}   ฿{o['total']:,.2f}", 12, True, justify='left').pack(side='left')
            self.order_badges(r,o).pack(anchor='w',padx=12,pady=3)
            if o['payment_status'] == 'paid':
                self.button(header, self.ui('ชำระเงินสำเร็จ / ใบเสร็จ', 'Payment success / receipt'), lambda oid=o['id']: self.payment_result(oid), compact=True).pack(side='right')
                self.button(r,self.ui('ดูใบเสร็จ','View receipt'),lambda oid=o['id']:self.receipt_window(oid),compact=True).pack(anchor='w',padx=12,pady=6)
                self.button(r,self.ui('บันทึกใบเสร็จ PDF','Save receipt PDF'),lambda oid=o['id']:self.save_receipt(oid),compact=True).pack(anchor='w',padx=12,pady=6)
            self.button(r, self.ui('รายละเอียดสินค้า / การจัดส่ง', 'Items / delivery details'), lambda oid=o['id']: self.order_detail(oid), compact=True).pack(anchor='w', padx=12, pady=6)
            if o['payment_status'] in ('waiting_payment','rejected') and o['order_status']=='waiting_payment':
                self.button(r, self.ui('ชำระเงิน', 'Pay now'), lambda oid=o['id']: self.receipt_window(oid), dark=True, compact=True).pack(anchor='w', padx=12, pady=6)
            if db.latest_payment(o['id']):self.button(r,self.ui('ดู / แก้ไขหลักฐาน','View / replace proof'),lambda oid=o['id']:self.proof_window(oid),compact=True).pack(anchor='w',padx=12,pady=8)
            if o['tracking']:
                self.label(r, self.ui('พัสดุ: ', 'Tracking: ') + o['tracking'], 8, fg=MID, wraplength=600, justify='left').pack(anchor='w', padx=12, pady=(0, 8))
            if o['payment_status'] in ('waiting_payment', 'rejected', 'under_review') and o['order_status'] == 'waiting_payment':
                self.button(header, self.tr('upload_receipt'), lambda x=o: self.upload(x), compact=True).pack(side='right', padx=8)

    # จัดหน้าว่างด้วยตัวอักษรแบรนด์และเส้นทอง ปรับเป็นแนวตั้งในหน้าต่างแคบ
    def orders_empty_state(self, parent):
        paper, gold, navy = '#F8F6F1', '#B6A180', '#243E55'
        body = self.scroll_content(parent)
        panel = tk.Frame(body, bg=paper, highlightbackground='#E6E0D6', highlightthickness=1)
        panel.pack(fill='x', padx=35, pady=(12, 28))
        self.label(panel, 'JPZ  /  THE DENIM JOURNAL', 10, fg=navy, bg=paper).pack(anchor='w', padx=30, pady=(24, 14))
        tk.Frame(panel, bg=gold, height=1).pack(fill='x', padx=30)
        row = tk.Frame(panel, bg=paper)
        row.pack(padx=26, pady=28)
        visual = tk.Canvas(row, bg=paper, width=280, height=300, highlightthickness=0)
        visual.create_rectangle(12, 12, 268, 288, outline=gold, width=1)
        visual.create_line(36, 78, 244, 78, fill='#E1D9CB')
        visual.create_text(140, 51, text='PIZZA JEANS', fill='#877354', font=('Georgia', 10))
        visual.create_text(140, 147, text='JPZ.', fill=navy, font=('Georgia', 55, 'bold'))
        visual.create_line(112, 210, 168, 210, fill=gold, width=1)
        visual.create_text(140, 243, text='DENIM MADE\nPERSONAL.', fill='#877354', font=('Georgia', 11), justify='center')
        copy = tk.Frame(row, bg=paper)
        self.label(copy, '01  /  YOUR DENIM JOURNEY', 10, fg='#877354', bg=paper).pack(anchor='w', pady=(4, 20))
        tk.Label(copy, text='YOUR FIRST PAIR.', font=('Georgia', 27, 'bold'), bg=paper, fg=navy, anchor='w').pack(anchor='w')
        self.label(copy, self.tr('orders_empty_title'), 22, True, bg=paper).pack(anchor='w', pady=(14, 8))
        description = self.label(copy, self.ui('เริ่มต้นด้วยยีนส์ที่เป็นคุณ\nเมื่อสั่งซื้อแล้ว ดูรายการและติดตามการจัดส่งได้ที่นี่', 'Start with denim that feels like you.\nYour orders and delivery updates will appear here.'), 12, fg=MID, bg=paper, wraplength=460)
        description.pack(anchor='w', pady=(0, 24))
        actions = tk.Frame(copy, bg=paper)
        actions.pack(anchor='w')
        browse = self.button(actions, self.tr('browse_denim'), self.shop, dark=True)
        browse.pack(side='left', padx=(0, 12))
        fit = self.button(actions, self.tr('find_fit'), self.fit_page)
        fit.pack(side='left')
        self.label(copy, 'DENIM MADE PERSONAL. / JPZ', 9, fg='#877354', bg=paper).pack(anchor='w', pady=(28, 4))
        layout = {'narrow': None}
        def arrange(event):
            narrow = event.width < 1000
            if narrow == layout['narrow']:return
            layout['narrow'] = narrow
            visual.grid_forget();copy.grid_forget()
            if narrow:
                visual.grid(row=0, column=0, sticky='w', pady=(0, 24))
                copy.grid(row=1, column=0, sticky='w')
                description.configure(wraplength=max(240, min(460, event.width-110)))
                fit.pack_forget();browse.pack_forget()
                browse.pack(anchor='w', pady=(0, 10));fit.pack(anchor='w')
            else:
                visual.grid(row=0, column=0, sticky='n', padx=(0, 46))
                copy.grid(row=0, column=1, sticky='w')
                description.configure(wraplength=460)
                fit.pack_forget();browse.pack_forget()
                browse.pack(side='left', padx=(0, 12));fit.pack(side='left')
        panel.bind('<Configure>', arrange)
        self._orders_empty_ui = {'panel': panel, 'visual': visual, 'browse': browse, 'fit': fit, 'layout': layout}

    # ตรวจไฟล์หลักฐาน JPG หรือ PNG แล้วผูกภาพกับคำสั่งซื้อของบัญชี
    def upload(self, o):
        path = filedialog.askopenfilename(filetypes=[('JPG / JPEG / PNG / WebP', '*.png *.jpg *.jpeg *.jfif *.webp')])
        if not path:
            return
        try:
            from support import payment_uploads
            payment_uploads.save(self.user['id'],o['id'],path)
        except (ValueError,PermissionError,OSError) as exc:
            return messagebox.showerror('JPZ',str(exc))
        self.payment_result(o['id'])

    # เรียกคิวใบเสร็จตามรอบเมื่อร้านเปิดและตั้งค่าการส่งอีเมล
    def receipt_worker(self):
        receipts.start_worker()
        self.after(15000, self.receipt_worker)

    # เปิดหน้าผลการส่งหลักฐานหรือผลการชำระเงิน
    def payment_result(self, oid, push=True):
        self.navigate('payment_result', self._payment_result, oid, push=push)

    # แสดงสถานะล่าสุดและภาพหลักฐานของคำสั่งซื้อ
    # J29 | หน้าผลการชำระเงิน
    def _payment_result(self, oid):
        order = receipts.order_for(self.user['id'], oid)
        if order is None:
            return self.my_orders()
        paid = order['payment_status'] == 'paid'
        b = self.scroll_content(self.shell())
        panel = tk.Frame(b, bg=SOFT, highlightbackground=LINE, highlightthickness=1)
        panel.pack(fill='x', padx=35, pady=25)

        title = self.ui('ชำระเงินสำเร็จ', 'Payment successful') if paid else self.ui('ส่งหลักฐานแล้ว · รอตรวจสอบ', 'Proof submitted · awaiting approval') if order['payment_status']=='under_review' else self.status_label(order['payment_status'])
        self.label(panel, title, 26, True, bg=SOFT).pack()
        self.order_badges(panel,order).pack(pady=8)
        self.label(panel, f"{self.ui('หมายเลขคำสั่งซื้อ','Order number')} {db.order_number(order)}    ฿{order['total']:,.2f}", 14, True, bg=SOFT).pack(pady=12)
        self.price_before_vat(panel,order['total'],bg=SOFT).pack_configure(anchor='center')
        detail = self.ui('ร้านยืนยันการชำระเงินแล้ว เปิดใบเสร็จด้านล่างได้','Payment approved. Your receipt is ready.') if paid else self.ui('เมื่อแอดมินยืนยันยอดชำระ หน้านี้จะอัปเดตเป็นชำระเงินสำเร็จ', 'This page updates after your payment is approved.')
        self.label(panel, detail, 11, fg=MID, bg=SOFT, wraplength=650, justify='center').pack(pady=8)
        if paid:
            info = receipts.delivery(oid)
            status = {'sent': self.ui('ส่งใบเสร็จทางอีเมลแล้ว', 'Receipt email sent'), 'pending': self.ui('ใบเสร็จอยู่ในคิวส่งอีเมล', 'Receipt email queued'), 'failed': self.ui('ส่งอีเมลไม่สำเร็จ · ร้านสามารถลองส่งใหม่ได้', 'Email failed · the store can retry'), 'sending': self.ui('กำลังส่งใบเสร็จ', 'Sending receipt')}
            configured = receipts.configured()
            text = status.get(info['status'], '') if info else self.ui('กำลังเตรียมใบเสร็จ', 'Preparing receipt')
            if not configured and (not info or info['status'] != 'sent'):
                text = self.ui('ใบเสร็จพร้อมแล้ว · เปิดดูและบันทึกได้', 'Receipt ready · view and save it below') if not receipts.enabled() else self.ui('ใบเสร็จพร้อมแล้ว · รอร้านตั้งค่าผู้ส่งอีเมล', 'Receipt ready · store email setup required')
            self.label(panel, text, 10, fg=MID, bg=SOFT).pack(pady=8)
            self.email_delivery_notice(panel,bg=SOFT).pack_configure(anchor='center')
            self.button(panel, self.ui('เปิดใบเสร็จ', 'View receipt'), lambda: self.receipt_window(oid), dark=True).pack(pady=8)
            self.button(panel, self.ui('บันทึกใบเสร็จ PDF', 'Save receipt PDF'), lambda: self.save_receipt(oid), dark=True).pack(pady=10)
        self.button(panel, self.tr('orders'), self.my_orders).pack(pady=(5, 25))
        if paid and oid not in getattr(self, '_shown_paid_receipts', set()):
            self._shown_paid_receipts = getattr(self, '_shown_paid_receipts', set()) | {oid}
            self.after(150, lambda: self.receipt_window(oid) if self.current_page == 'payment_result' else None)
        if db.latest_payment(oid):self.proof_preview(panel,oid)
        if not paid and order['payment_status']=='under_review':self.after(3000,lambda:self.poll_payment(oid,'under_review'))

    # บันทึกใบเสร็จรับเงินของคำสั่งซื้อที่ชำระแล้ว
    def save_receipt(self, oid):
        try:
            from support import receipt_pdf
            order,_=receipt_pdf.receipt_data(self.user['id'],oid)
            path = filedialog.asksaveasfilename(defaultextension='.pdf', initialfile=f'JPZ_receipt_{db.order_number(order)}.pdf', filetypes=[('PDF receipt', '*.pdf')])
            if path:
                receipt_pdf.export(self.user['id'],oid,path)
                messagebox.showinfo('JPZ', self.ui('บันทึกใบเสร็จ PDF แล้ว เปิดไฟล์เพื่อดูหรือพิมพ์ได้', 'PDF receipt saved. Open it to view or print.'))
        except (ValueError, PermissionError, OSError) as exc:
            messagebox.showerror('JPZ', str(exc))

    # เปิดหน้าข้อมูลบัญชี
    def profile(self, push=True):
        self.navigate('profile', self._profile, push=push)

    # อ่านข้อมูลบัญชีล่าสุดและแสดงรูปโปรไฟล์กับที่อยู่จัดส่ง
    # J34 | หน้าโปรไฟล์ลูกค้า
    def _profile(self):
        self.user=db.user(self.user['id']);b=self.scroll_content(self.shell())
        content=tk.Frame(b,bg=WHITE);content.pack(fill='x',padx=30,pady=22)
        # เส้นทองและตัวอักษรแบรนด์เป็นของตกแต่งนิ่ง จึงไม่เพิ่มตัวจับเวลา
        self.label(content,'JPZ / YOUR PERSONAL SPACE',10,True,fg='#877354').pack(anchor='w',pady=(0,8))
        self.label(content,self.ui('ข้อมูลบัญชี','My account'),28,True,fg=INK).pack(anchor='w',pady=(0,12))
        tk.Frame(content,bg='#B8A88E',height=1).pack(fill='x',pady=(0,20))
        header=card(content,color='#243E55');header.pack(fill='x',pady=(0,18))
        inner=tk.Frame(header,bg='#243E55');inner.pack(fill='x',padx=28,pady=24)
        from support.portraits import avatar
        portrait=ImageTk.PhotoImage(avatar(BASE_DIR,self.user.get('avatar',''),size=144),master=self)
        preview=tk.Label(inner,image=portrait,bg='#243E55',cursor='hand2');preview._image=portrait;preview.pack(side='left',padx=(0,24))
        preview.bind('<Button-1>',lambda event:self.edit_avatar())
        self.profile_photo_preview=preview
        identity=tk.Frame(inner,bg='#243E55');identity.pack(side='left',fill='both',expand=True)
        self.label(identity,'JPZ / MEMBER',10,True,fg='#D6C6A9',bg='#243E55').pack(anchor='w',pady=(0,8))
        name=(self.user['first_name']+' '+self.user['last_name']).strip()
        self.label(identity,name or self.ui('บัญชีของคุณ','Your account'),21,True,fg=WHITE,bg='#243E55').pack(anchor='w')
        self.label(identity,self.user['email'],12,fg='#E2E7EA',bg='#243E55').pack(anchor='w',pady=(5,10))
        self.label(identity,self.ui('กดรูปเพื่อจัดตำแหน่งและปรับขนาด','Click your photo to reposition and zoom.'),11,fg='#D6C6A9',bg='#243E55').pack(anchor='w',pady=(0,12))
        photo_actions=tk.Frame(identity,bg='#243E55');photo_actions.pack(anchor='w')
        self.button(photo_actions,self.ui('เพิ่ม / เปลี่ยนรูปโปรไฟล์','Change photo'),self.change_avatar,compact=True).pack(side='left')
        self.button(photo_actions,self.ui('จัดตำแหน่งรูป','Adjust photo'),self.edit_avatar,compact=True).pack(side='left',padx=8)
        self._profile_camera_button=self.button(photo_actions,self.ui('เปิดกล้อง','Open camera'),self.open_profile_camera,compact=True)
        self._profile_camera_button.pack(side='left',padx=(0,8))
        panels=tk.Frame(content,bg=WHITE);panels.pack(fill='x')
        personal=card(panels);personal.grid(row=0,column=0,sticky='nsew',padx=(0,9))
        delivery=card(panels);delivery.grid(row=0,column=1,sticky='nsew',padx=(9,0))
        panels.columnconfigure(0,weight=1,uniform='profile');panels.columnconfigure(1,weight=1,uniform='profile')
        def details(panel,title,values):
            words=tk.Frame(panel,bg=WHITE);words.pack(fill='both',expand=True,padx=24,pady=22)
            self.label(words,'01 / ACCOUNT' if panel is personal else '02 / DELIVERY',10,True,fg='#877354').pack(anchor='w',pady=(0,8))
            self.label(words,title,18,True,fg=INK).pack(anchor='w',pady=(0,12))
            tk.Frame(words,bg='#D8CEBE',height=1).pack(fill='x',pady=(0,10))
            labels=[]
            for key,value in values:
                row=tk.Frame(words,bg='#F8F6F0');row.pack(fill='x',pady=4)
                self.label(row,key,11,True,fg='#877354',bg='#F8F6F0').pack(anchor='w',padx=14,pady=(10,3))
                label=self.label(row,value or self.ui('ยังไม่ได้ระบุ','Not provided'),12,bg='#F8F6F0',fg=INK,wraplength=450,anchor='w')
                label.pack(anchor='w',fill='x',padx=14,pady=(0,11));labels.append(label)
            words.bind('<Configure>',lambda event:[label.configure(wraplength=max(160,event.width-28)) for label in labels])
        details(personal,self.ui('ข้อมูลส่วนตัว','Personal details'),[(self.ui('ชื่อ','Name'),name),(self.ui('อีเมล','Email'),self.user['email']),(self.ui('เบอร์โทรศัพท์','Phone'),self.user['phone'])])
        details(delivery,self.ui('ที่อยู่จัดส่ง','Delivery address'),[(self.ui('ชื่อผู้รับ','Recipient'),self.user['delivery_name']),(self.ui('ที่อยู่','Address'),self.user['address']),(self.ui('รหัสไปรษณีย์','Postal code'),self.user['postal_code'])])
        placement=[None]
        def arrange(event):
            stacked=event.width<820
            if stacked==placement[0]:return
            placement[0]=stacked
            personal.grid_configure(padx=0 if stacked else (0,9))
            delivery.grid_configure(row=1 if stacked else 0,column=0 if stacked else 1,padx=0 if stacked else (9,0),pady=(14,0) if stacked else 0)
            panels.columnconfigure(1,weight=0 if stacked else 1)
        panels.bind('<Configure>',arrange)
        actions=tk.Frame(content,bg=WHITE);actions.pack(fill='x',pady=18)
        self.button(actions,self.ui('แก้ไขข้อมูล / ที่อยู่จัดส่ง','Edit account / address'),self.edit_account,dark=True).pack(side='left')
        self.button(actions,self.tr('logout'),self.logout).pack(side='right')

    # บันทึกข้อมูลบัญชีผ่านตัวจัดการข้อมูลเดิม
    def save_profile(self):
        if db.update_profile(self.user['id'], self.pfn.get(), self.pln.get(), self.pem.get(), self.ppw.get()):
            self.user.update(first_name=self.pfn.get(), last_name=self.pln.get(), email=self.pem.get())
            messagebox.showinfo(self.tr('profile'), self.tr('saved'))
        else:
            messagebox.showerror(self.tr('profile'), 'Email already exists.')

    # เปิดหน้าบัญชีแอดมิน
    def admin_profile(self, push=True):
        self.navigate('admin_profile', self._admin_profile, push=push)

    # แสดงข้อมูลบัญชีแอดมินและปุ่มแก้ไข
    # J35 | หน้าโปรไฟล์แอดมิน
    def _admin_profile(self):
        self.admin_tab='account';b=self.admin_shell()
        self.user=db.user(self.user['id'])
        content=self.scroll_content(b,native=True)
        self.label(content,self.ui('บัญชีแอดมิน','Admin account'),32,True).pack(anchor='w',padx=12,pady=(12,8))
        self.label(content,self.ui('ข้อมูลผู้ดูแลร้าน JPZ','Your JPZ store administrator profile'),13,fg=MID).pack(anchor='w',padx=12,pady=(0,24))
        hero=card(content);hero.pack(fill='x',padx=12,pady=(0,22))
        inner=tk.Frame(hero,bg=WHITE);inner.pack(fill='x',padx=28,pady=28)
        from support.portraits import avatar
        photo=gallery_assets.to_photo(avatar(BASE_DIR,self.user.get('avatar',''),size=190),master=self)
        portrait=tk.Label(inner,image=photo,bg=WHITE);portrait._image=photo;portrait.pack(side='left',padx=(0,30))
        identity=tk.Frame(inner,bg=WHITE);identity.pack(side='left',fill='both',expand=True)
        self.label(identity,'JPZ / STORE ADMIN',12,True,fg='#877354').pack(anchor='w',pady=(16,12))
        name=(self.user.get('first_name','')+' '+self.user.get('last_name','')).strip()
        name_label=self.label(identity,name or self.ui('ผู้ดูแลร้าน','Store administrator'),28,True,wraplength=900)
        name_label.pack(anchor='w',pady=(0,8))
        email_label=self.label(identity,self.user['email'],15,fg=MID,wraplength=900);email_label.pack(anchor='w',pady=(0,16))
        edit=self.button(identity,self.ui('แก้ไขข้อมูลบัญชี','Edit account details'),self.edit_account,dark=True);edit.pack(anchor='w')
        photo_actions=tk.Frame(identity,bg=WHITE);photo_actions.pack(anchor='w',pady=10)
        self.button(photo_actions,self.ui('เปลี่ยนรูป','Change photo'),self.change_avatar,compact=True).pack(side='left',padx=(0,8))
        self.button(photo_actions,self.ui('จัดรูป','Adjust photo'),self.edit_avatar,compact=True).pack(side='left',padx=(0,8))
        self.button(photo_actions,self.ui('เปิดกล้อง','Open camera'),self.open_profile_camera,compact=True).pack(side='left')
        portrait.configure(cursor='hand2');portrait.bind('<Button-1>',lambda event:self.edit_avatar())
        password_button=self.button(identity,self.ui('เปลี่ยนรหัสผ่าน','Change password'),self.admin_password_dialog,compact=True);password_button.pack(anchor='w',pady=(0,8))
        identity.bind('<Configure>',lambda event:[label.configure(wraplength=max(200,event.width-10)) for label in (name_label,email_label) if int(label.cget('wraplength'))!=max(200,event.width-10)])
        details=card(content);details.pack(fill='x',padx=12,pady=(0,24))
        self.label(details,self.ui('ข้อมูลบัญชี','Account details'),22,True).pack(anchor='w',padx=28,pady=(24,18))
        fields=tk.Frame(details,bg=WHITE);fields.pack(fill='x',padx=24,pady=(0,24));boxes=[]
        for th,en,key in [('ชื่อ','First name','first_name'),('นามสกุล','Last name','last_name'),('อีเมล','Email','email'),('เบอร์โทรศัพท์','Phone number','phone')]:
            box=tk.Frame(fields,bg='#F5F6F7');boxes.append(box)
            self.label(box,self.ui(th,en),12,fg=MID,bg='#F5F6F7').pack(anchor='w',padx=20,pady=(16,6))
            value=self.label(box,self.user.get(key) or self.ui('ยังไม่ได้ระบุ','Not provided'),18,True,bg='#F5F6F7',wraplength=500)
            value.pack(anchor='w',padx=20,pady=(0,18))
            box.bind('<Configure>',lambda event,label=value:label.configure(wraplength=max(200,event.width-44)) if int(label.cget('wraplength'))!=max(200,event.width-44) else None)
        account_columns=[None]
        def arrange(event):
            columns=2 if event.width>=700 else 1
            if columns==account_columns[0]:return
            account_columns[0]=columns
            for column in range(2):fields.columnconfigure(column,weight=1 if column<columns else 0,uniform='admin_account')
            for index,box in enumerate(boxes):box.grid(row=index//columns,column=index%columns,sticky='nsew',padx=6,pady=6)
        fields.bind('<Configure>',arrange)
        from support import store_details
        public_address=store_details.address()
        address_card=card(content);address_card.pack(fill='x',padx=12,pady=(0,24))
        self.label(address_card,self.ui('ที่อยู่ร้าน · แสดงในหน้าติดต่อร้าน','Store address · shown on the contact page'),20,True).pack(anchor='w',padx=28,pady=(24,12))
        text='\n'.join(value for value in (public_address['name'],public_address['address'],public_address['postal_code']) if value) if public_address['address'] else self.ui('ยังไม่ได้ระบุที่อยู่ร้าน · กดแก้ไขข้อมูลบัญชีเพื่อเพิ่ม','Store address not provided · edit account details to add it')
        address_label=self.label(address_card,text,15,wraplength=1200);address_label.pack(anchor='w',padx=28,pady=(0,24))
        address_card.bind('<Configure>',lambda event:address_label.configure(wraplength=max(200,event.width-60)) if int(address_label.cget('wraplength'))!=max(200,event.width-60) else None)
        self._admin_profile_ui={'hero':hero,'details':details,'edit':edit,'fields':boxes,'password':password_button,'portrait':portrait}

    def admin_password_dialog(self):
        admin_data.query(self.user['id'],'SELECT 1')
        win=tk.Toplevel(self);win.title(self.ui('เปลี่ยนรหัสผ่านแอดมิน','Change administrator password'));win.geometry('560x620');win.configure(bg=WHITE);win.transient(self)
        footer=tk.Frame(win,bg=WHITE);footer.pack(side='bottom',fill='x',padx=24,pady=16)
        body=self.scroll_content(win)
        current=self.password_field(body,self.ui('รหัสผ่านปัจจุบัน','Current password'))
        new=self.password_field(body,self.ui('รหัสผ่านใหม่','New password'))
        confirm=self.password_field(body,self.ui('ยืนยันรหัสผ่านใหม่','Confirm new password'))
        self.label(body,self.ui('อย่างน้อย 8 ตัว มีตัวพิมพ์ใหญ่ พิมพ์เล็ก และตัวเลข','At least 8 characters with uppercase, lowercase letters and digits.'),11,wraplength=480,justify='left').pack(pady=12)
        error=self.label(body,'',11,fg='#BB2020',wraplength=480);error.pack(pady=8)
        def save():
            try:
                if new.get()!=confirm.get():raise ValueError(self.ui('รหัสผ่านใหม่ทั้งสองช่องไม่ตรงกัน','New passwords do not match.'))
                db.change_admin_password(self.user['id'],current.get(),new.get())
                for entry in (current,new,confirm):entry.delete(0,'end')
                win.destroy();messagebox.showinfo('JPZ',self.ui('เปลี่ยนรหัสผ่านแล้ว ใช้รหัสใหม่ครั้งถัดไป','Password changed. Use it the next time you sign in.'))
            except (ValueError,PermissionError) as exc:error.configure(text=str(exc))
        self.button(footer,self.ui('ยกเลิก','Cancel'),win.destroy).pack(side='left')
        button=self.button(footer,self.ui('บันทึกรหัสผ่านใหม่','Save new password'),save,dark=True);button.pack(side='right')
        self._admin_password_ui=dict(window=win,current=current,new=new,confirm=confirm,save=button,error=error)



    # บันทึกข้อมูลบัญชีแอดมินและแสดงข้อมูลใหม่
    def save_admin_profile(self):
        if db.update_profile(self.user['id'], self.pfn.get(), self.pln.get(), self.pem.get(), self.ppw.get()):
            self.user.update(first_name=self.pfn.get(), last_name=self.pln.get(), email=self.pem.get())
            messagebox.showinfo('ADMIN', self.tr('saved'))
            self._admin_profile()

    # ยืนยันการออกจากระบบ ล้างข้อมูลในหน้าจอ และกลับหน้าล็อกอิน
    def logout(self):
        title = 'JPZ.'
        message = (
            'ต้องการออกจากระบบหรือไม่?'
            if self.lang == 'TH'
            else 'Do you want to log out?'
        )
        if not messagebox.askyesno(title, message):
            return

        self.user = None
        self.cart = {}
        self.cart_excluded = set()
        self.page_history = []
        self.lang = 'TH'
        self.show_login(push=False)

    # สร้างช่องเบอร์โทร จำกัดตัวเลขไม่เกิน 10 หลักและแจ้งข้อมูลไม่ครบ
    def phone_entry(self,parent):
        entry=self.entry(parent,self.ui('เบอร์โทรศัพท์ (10 หลัก)','Phone (10 digits)'))
        error=self.label(parent,'',11,fg='#BB2020')
        def notice(text):
            error.configure(text=text)
            if text:error.pack(anchor='w',pady=(3,0),after=entry)
            else:error.pack_forget()
        def validate(value):
            valid=len(value)<=10 and (not value or value.isascii() and value.isdigit())
            notice('' if valid else self.ui('เบอร์โทรศัพท์ต้องเป็นตัวเลข ห้ามเกิน 10 หลัก','Phone must contain at most 10 digits.'))
            return valid
        entry.configure(validate='key',validatecommand=(entry.register(validate),'%P'))
        entry.bind('<FocusOut>',lambda e:notice('' if len(entry.get())==10 else self.ui('กรอกเบอร์โทรศัพท์ให้ครบ 10 หลัก','Enter all 10 phone digits.')))
        return entry

    # ย้ายรายการในตะกร้าไปไซซ์ที่เลือกเมื่อสต็อกเพียงพอ
    def cart_size(self,key,size):
        if key not in self.cart:return
        qty=self.cart.get(key,0);target=(key[0],key[1],size)
        if target==key:return
        if db.variant_stock(*target)<qty+self.cart.get(target,0):
            self.cart_warning.configure(text='ไซซ์ที่เลือกหมด หรือมีจำนวนไม่เพียงพอ');return
        self.move_cart_selection(key,target)
        self.cart.pop(key,None);self.cart[target]=self.cart.get(target,0)+qty;self._bag()

    # เปลี่ยนสีโดยไม่เปลี่ยนไซซ์หรือจำนวน รวมรายการซ้ำเฉพาะเมื่อสต็อกเพียงพอ
    def cart_color(self,key,color):
        if key not in self.cart:return
        target=(key[0],color,key[2])
        if target==key:return
        stock=db.variant_stock(*target);needed=self.cart[key]+self.cart.get(target,0)
        if stock<needed:
            message=self.ui('สีนี้หมดในไซซ์ที่เลือก กรุณาเลือกไซซ์อื่นก่อน', 'This color is sold out in the selected size. Choose another size first.') if not stock else self.ui(f'สีนี้ในไซซ์ {db.size_label(key[2])} เหลือ {stock} ตัว ไม่เพียงพอกับจำนวนในตะกร้า',f'This color has {stock} items in size {db.size_label(key[2])}, fewer than the quantity in your cart.')
            self.cart_warning.configure(text=message);return
        self.move_cart_selection(key,target)
        self.cart.pop(key);self.cart[target]=needed;self._bag()

    # อ่านรูปที่จัดเก็บไว้และแสดงโดยรักษาสัดส่วนภาพ
    def file_picture(self,parent,path,width=320,height=320):
        from PIL import Image,ImageTk
        path=Path(path)
        if not path.is_absolute():path=BASE_DIR/path
        if not path.is_file():
            path=BASE_DIR/'payment_uploads'/path.name
        if not path.is_file():
            label=self.label(parent,'ไม่พบไฟล์ภาพ',11);label.pack(pady=10);return label
        with Image.open(path) as picture:
            picture=picture.convert('RGB');picture.thumbnail((width,height))
            photo=ImageTk.PhotoImage(picture,master=self)
        label=tk.Label(parent,image=photo,bg=parent.cget('bg'));label._image=photo;label.pack(pady=10)
        return label

    # เลือกรูปต้นฉบับแล้วเปิดหน้าปรับตำแหน่ง ยังไม่บันทึกจนผู้ใช้กดยืนยัน
    def change_avatar(self):
        path=filedialog.askopenfilename(filetypes=[('รูป JPG / PNG','*.jpg *.jpeg *.png')])
        if not path:return
        try:
            with Image.open(path) as picture:image=ImageOps.exif_transpose(picture).convert('RGB')
            self.open_avatar_editor(image)
        except (OSError,ValueError) as exc:messagebox.showerror('JPZ',str(exc))

    # J61 | เปิดกล้องรูปโปรไฟล์
    def open_profile_camera(self):
        from support.camera import CameraDialog
        old=getattr(self,'_profile_camera',None)
        if old is not None and old.winfo_exists():old.lift();return
        self._profile_camera=CameraDialog(self,self.open_avatar_editor)

    # กดรูปปัจจุบันเพื่อกลับมาปรับใหม่ โดยใช้ต้นฉบับที่เก็บไว้ ถ้ายังไม่มีให้เลือกรูปก่อน
    def edit_avatar(self):
        from support.portraits import read_photo
        self.user=db.user(self.user['id'])
        image=read_photo(BASE_DIR,self.user.get('avatar_source','')) or read_photo(BASE_DIR,self.user.get('avatar',''))
        if image is None:return self.change_avatar()
        import json
        try:settings=json.loads(self.user.get('avatar_crop','') or '{}') if self.user.get('avatar_source') else {}
        except (ValueError,TypeError):settings={}
        self.open_avatar_editor(image,settings)

    # เปิดหน้าต่างปรับรูป และกำหนดฟังก์ชันบันทึกของบัญชีปัจจุบัน
    # J62 | จัดตำแหน่งและขยายรูปโปรไฟล์
    def open_avatar_editor(self,image,settings=None):
        from support.avatar_editor import AvatarEditor
        self._avatar_editor=AvatarEditor(self,image,self.save_avatar_crop,settings)

    # เก็บต้นฉบับและภาพที่ตัดแล้วแยกไฟล์ พร้อมอัปเดตรูปวงกลมหลังบันทึก
    def save_avatar_crop(self,cropped,original,settings=None):
        import json
        folder=BASE_DIR/'user_uploads';folder.mkdir(exist_ok=True)
        token=uuid.uuid4().hex;prefix=f"user_{self.user['id']}_{token}"
        source=folder/f'{prefix}_source.png';dest=folder/f'{prefix}.png'
        try:
            original=original.copy();original.thumbnail((2048,2048));original.save(source)
            cropped.save(dest)
            db.save_customer_details(self.user['id'],{'avatar':str(dest.relative_to(BASE_DIR)),'avatar_source':str(source.relative_to(BASE_DIR)),'avatar_crop':json.dumps(settings or {})})
        except Exception:
            source.unlink(missing_ok=True);dest.unlink(missing_ok=True);raise
        self.after_idle(self._admin_profile if self.user.get('role')=='admin' else self._profile)

    # เปิดหน้าแก้ไขในโปรแกรมหลัก แทนหน้าต่างเล็กที่บังข้อมูลบัญชี
    def edit_account(self):
        self._account_return_admin=self.current_page=='admin_profile'
        self.navigate('account_edit',self._edit_account)

    # แบ่งฟอร์มบัญชีกับที่อยู่ และตรึงปุ่มบันทึกไว้ด้านล่างเสมอ
    # J60 | แก้ไขข้อมูลบัญชีและที่อยู่
    def _edit_account(self):
        self.user=db.user(self.user['id'])
        store_mode=getattr(self,'_account_return_admin',False)
        from support import store_details
        public_address=store_details.address() if store_mode else {}
        body=self.admin_shell() if store_mode else self.shell()
        footer=tk.Frame(body,bg=WHITE);footer.pack(side='bottom',fill='x',padx=30,pady=12)
        error=self.label(footer,'',11,fg='#BB2020',wraplength=650)
        error.pack(anchor='w',pady=(0,6))
        buttons=tk.Frame(footer,bg=WHITE);buttons.pack(fill='x')
        content=self.scroll_content(body)
        form=tk.Frame(content,bg=WHITE);form.pack(fill='x',padx=30,pady=20)
        self.label(form,self.ui('แก้ไขข้อมูลบัญชี','Edit account'),26,True).pack(anchor='w')
        self.label(form,self.ui('แก้ไขบัญชีและที่อยู่ร้าน ที่อยู่ร้านจะแสดงในหน้าติดต่อร้าน','Update your account and store address. The store address appears on the contact page.') if store_mode else self.ui('แก้ไขข้อมูลและที่อยู่จัดส่ง แล้วกดบันทึก','Update your details and delivery address, then save.'),12,fg=MID).pack(anchor='w',pady=(8,20))
        panels=tk.Frame(form,bg=WHITE);panels.pack(fill='x')
        personal=card(panels);delivery=card(panels)
        personal.grid(row=0,column=0,sticky='nsew',padx=(0,10))
        delivery.grid(row=0,column=1,sticky='nsew',padx=(10,0))
        panels.columnconfigure(0,weight=1,uniform='account');panels.columnconfigure(1,weight=1,uniform='account')
        fields={}
        # ช่องที่อยู่หลายบรรทัดช่วยให้อ่านและแก้ไขที่อยู่ยาวได้สะดวก
        groups=[(personal,self.ui('ข้อมูลบัญชี','Account details'),[
            ('first_name',self.ui('ชื่อ','First name')),('last_name',self.ui('นามสกุล','Last name')),
            ('email',self.ui('อีเมล','Email')),('phone',self.ui('เบอร์โทรศัพท์','Phone'))]),
            (delivery,self.ui('ที่อยู่ร้าน','Store address') if store_mode else self.ui('ที่อยู่จัดส่ง','Delivery address'),[
            ('delivery_name',self.ui('ชื่อร้าน','Store name') if store_mode else self.ui('ชื่อผู้รับ','Recipient')),('address',self.ui('ที่อยู่ร้าน','Store address') if store_mode else self.ui('ที่อยู่จัดส่ง','Address')),
            ('postal_code',self.ui('รหัสไปรษณีย์','Postal code'))])]
        for panel,title,items in groups:
            inner=tk.Frame(panel,bg=WHITE);inner.pack(fill='both',expand=True,padx=22,pady=20)
            self.label(inner,title,18,True).pack(anchor='w',pady=(0,6))
            for key,label in items:
                value=public_address.get('name' if key=='delivery_name' else key,'') if store_mode and key in ('delivery_name','address','postal_code') else self.user[key] or ''
                if key=='address':
                    self.label(inner,label,11,True,fg=MID).pack(anchor='w',pady=(12,6))
                    entry=tk.Text(inner,width=20,height=5,font=ui_font(14),wrap='word',bg=SOFT,fg=INK,relief='solid',bd=1,padx=12,pady=10)
                    entry.pack(fill='x');entry.insert('1.0',value)
                else:
                    entry=self.phone_entry(inner) if key=='phone' else self.entry(inner,label)
                    entry.insert(0,value)
                fields[key]=entry
        layout=[None]
        def arrange(event):
            stacked=event.width<820
            if layout[0]==stacked:return
            layout[0]=stacked
            personal.grid_configure(padx=0 if stacked else (0,10))
            delivery.grid_configure(row=1 if stacked else 0,column=0 if stacked else 1,padx=0 if stacked else (10,0),pady=(16,0) if stacked else 0)
            panels.columnconfigure(1,weight=0 if stacked else 1)
        panels.bind('<Configure>',arrange)
        def finish():
            self.admin_profile(push=False) if getattr(self,'_account_return_admin',False) else self.profile(push=False)
        def save():
            try:
                values={key:(entry.get('1.0','end-1c') if key=='address' else entry.get()).strip() for key,entry in fields.items()}
                if not values['first_name'] or not values['last_name']:
                    raise ValueError(self.ui('กรอกชื่อและนามสกุลให้ครบ','Enter your first and last name.'))
                if store_mode:
                    store_details.save_account(self.user['id'],values,{'name':values['delivery_name'],'address':values['address'],'postal_code':values['postal_code']})
                else:db.save_customer_details(self.user['id'],values)
            except Exception as exc:
                error.configure(text=str(exc));return
            finish()
        cancel=self.button(buttons,self.ui('ยกเลิก','Cancel'),finish,compact=True);cancel.pack(side='left')
        save_button=self.button(buttons,self.ui('บันทึกข้อมูล','Save changes'),save,dark=True,compact=True);save_button.pack(side='right')
        self._account_edit_ui={'fields':fields,'save':save_button,'cancel':cancel,'error':error,'panels':panels}

    # เลือกข้อความสถานะคำสั่งซื้อให้ตรงกับสถานะการชำระและจัดส่ง
    def order_status_text(self,order):
        if order['order_status'] in ('cancelled','refunded'):return self.status_label(order['order_status'])
        if order['payment_status']=='under_review':return self.ui('กำลังตรวจสอบหลักฐาน','Payment proof under review')
        if order['payment_status']=='rejected':return self.ui('กรุณาส่งหลักฐานใหม่','Please replace payment proof')
        if order['payment_status']=='paid':return self.status_label(order['order_status'])
        return self.status_label(order['payment_status'])

    # ตรวจการเปลี่ยนสถานะชำระเงินแล้วปรับหน้าผลลัพธ์ให้เป็นปัจจุบัน
    def poll_payment(self,oid,old_status):
        if self.current_page!='payment_result' or self.current_args.get('args')!=(oid,):return
        order=receipts.order_for(self.user['id'],oid)
        if not order:return
        if order['payment_status']!=old_status:self._payment_result(oid)
        else:self.after(3000,lambda:self.poll_payment(oid,old_status))

    # แสดงรูปหลักฐานที่บัญชีส่ง พร้อมปุ่มเปลี่ยนภาพเมื่อยังแก้ไขได้
    def proof_preview(self,parent,oid):
        order=receipts.order_for(self.user['id'],oid)
        if not order:return
        proof=db.latest_payment(oid)
        if not proof:return
        self.label(parent,'หลักฐานที่คุณส่ง',13,True,bg=parent.cget('bg')).pack(pady=10)
        try:self.file_picture(parent,proof['receipt_path'],320,380)
        except OSError:self.label(parent,'ไม่สามารถเปิดภาพหลักฐานได้',11).pack()
        self.label(parent,receipts.local_time(proof['uploaded_at'])+' (เวลาไทย)',11,bg=parent.cget('bg')).pack(pady=4)
        if order['payment_status'] in ('waiting_payment','under_review','rejected') and order['order_status']=='waiting_payment':
            def replace_proof():
                self.upload(order)
                if hasattr(self,'_proof_dialog') and self._proof_dialog.winfo_exists():self._proof_dialog.destroy()
            self.button(parent,'เปลี่ยนภาพหลักฐาน',replace_proof).pack(pady=10)

    # เปิดหน้าต่างดูหลักฐานการชำระเงิน
    def proof_window(self,oid):
        win=tk.Toplevel(self);win.title('หลักฐานชำระเงิน');win.geometry('600x720')
        self._proof_dialog=win
        self.proof_preview(self.scroll_content(win),oid)

    # เปิดหน้าช่องทางติดต่อร้าน
    def contact(self,push=True):self.navigate('contact',self._contact,push=push)

    # แสดงรูปเจ้าของร้านและไอคอนช่องทางติดต่อ โดยจัดตามขนาดหน้าต่าง
    # J36 | หน้าติดต่อร้าน
    def _contact(self):
        import json
        import webbrowser
        b=self.scroll_content(self.shell())
        content=tk.Frame(b,bg=WHITE);content.pack(fill='x',padx=30,pady=25)
        hero=tk.Frame(content,bg='#F8F6F0',highlightbackground='#D8CEBE',highlightthickness=1);hero.pack(fill='x',pady=(0,22))
        tk.Frame(hero,bg='#B8A88E',height=2).pack(fill='x')
        self.label(hero,'JPZ / CUSTOMER CARE',10,True,fg='#877354',bg='#F8F6F0').pack(anchor='w',padx=24,pady=(20,8))
        self.label(hero,self.ui('ติดต่อร้าน JPZ','CONTACT JPZ'),28,True,fg=INK,bg='#F8F6F0').pack(anchor='w',padx=24)
        self.label(hero,self.ui('สอบถามสินค้า ไซซ์ และคำสั่งซื้อได้ผ่านช่องทางด้านล่าง','Contact us about products, sizing or your order using the channels below.'),12,fg=MID,bg='#F8F6F0').pack(anchor='w',padx=24,pady=(8,20))
        c=db.conn();record=c.execute("SELECT value FROM shop_metadata WHERE key='contact'").fetchone();c.close()
        values=json.loads(record['value']) if record else {'email':'supaza2549@gmail.com'}
        from support.portraits import owner_portrait
        layout=tk.Frame(content,bg=WHITE);layout.pack(fill='x',pady=(4,0))
        owner=ctk.CTkFrame(layout,fg_color='#243E55',corner_radius=16,border_width=1,border_color='#B8A88E');owner.grid(row=0,column=0,sticky='n',padx=(0,20))
        self.label(owner,'JPZ / AT YOUR SERVICE',10,True,bg='#243E55',fg='#D6C6A9').pack(anchor='w',padx=20,pady=(20,0))
        self.label(owner,self.ui('เจ้าของร้าน JPZ','MEET THE OWNER'),20,True,bg='#243E55',fg=WHITE).pack(anchor='w',padx=20,pady=(20,14))
        image=owner_portrait(BASE_DIR,values.get('photo',''),(336,392))
        picture=ImageTk.PhotoImage(image,master=self)
        portrait=tk.Label(owner,image=picture,bg='#243E55',highlightbackground='#B8A88E',highlightthickness=1);portrait._image=picture;portrait._owner_photo=True;portrait.pack(padx=20)
        self.label(owner,'JPZ / DENIM MADE PERSONAL.',12,True,bg='#243E55',fg=WHITE).pack(padx=20,pady=(14,8))
        self.label(owner,self.ui('สอบถามสินค้าได้ผ่านช่องทางติดต่อร้าน','Get in touch through our store channels.'),11,bg='#243E55',fg='#D7E0E8',wraplength=330).pack(padx=20,pady=(0,20))
        contact_cards=tk.Frame(layout,bg=WHITE);contact_cards.grid(row=0,column=1,sticky='nsew')
        layout.columnconfigure(1,weight=1);layout.columnconfigure(0,weight=0)
        placement=[None]
        def arrange_contact(event):
            stacked=event.width<850
            if placement[0]==stacked:return
            placement[0]=stacked
            owner.grid_configure(row=0,column=0,padx=0 if stacked else (0,20),pady=(0,16) if stacked else 0)
            contact_cards.grid_configure(row=1 if stacked else 0,column=0 if stacked else 1,sticky='nsew')
            layout.columnconfigure(0,weight=1 if stacked else 0);layout.columnconfigure(1,weight=0 if stacked else 1)
        layout.bind('<Configure>',arrange_contact)
        from support import store_details
        public_address=store_details.address()
        if public_address['address']:
            row=card(contact_cards);row.pack(fill='x',pady=(0,12));row._contact_channel='store_address'
            words=tk.Frame(row,bg=WHITE);words.pack(fill='x',padx=18,pady=18)
            self.label(words,self.ui('ที่อยู่ร้าน','Store address'),16,True).pack(anchor='w')
            text='\n'.join(value for value in (public_address['name'],public_address['address'],public_address['postal_code']) if value)
            address_label=self.label(words,text,13,wraplength=800);address_label.pack(anchor='w',pady=(8,0))
            words.bind('<Configure>',lambda event:address_label.configure(wraplength=max(200,event.width-10)))
        channels=[('facebook','Facebook'),('instagram','Instagram'),('line','LINE ID'),('phone',self.ui('โทรศัพท์','Phone')),('email',self.ui('อีเมล','Email'))]
        for number,(key,title) in enumerate(channels,1):
            value=values.get(key,'').strip()
            if not value and key not in ('facebook','instagram','phone','line'):continue
            row=card(contact_cards);row.pack(fill='x',pady=(0,12))
            tk.Frame(row,bg='#D8CEBE',height=1).pack(fill='x',padx=20,pady=(10,0))
            inner=tk.Frame(row,bg=WHITE);inner.pack(fill='x',padx=18,pady=16)
            self.label(inner,f'{number:02}',11,True,fg='#877354').pack(side='right',padx=(16,4))
            row._contact_channel=key
            # ไอคอน LINE สีเขียวพร้อมข้อความในกรอบสนทนา ไม่ต้องโหลดจากอินเทอร์เน็ต
            if key=='email':
                icon=tk.Canvas(inner,width=40,height=40,bg=WHITE,highlightthickness=0)
                icon.create_oval(0,0,39,39,fill='#F8F6F0',outline='#DDD6C8')
                icon.create_rectangle(8,12,31,28,outline='#243E55',width=2)
                icon.create_line(8,12,19.5,21,31,12,fill='#243E55',width=2)
                icon.pack(side='left',padx=(0,16));icon._email_icon=True
            if key=='line':
                icon=tk.Canvas(inner,width=40,height=40,bg=WHITE,highlightthickness=0)
                icon.create_polygon(8,1,32,1,39,8,39,32,32,39,8,39,1,32,1,8,fill='#06C755',smooth=True)
                icon.create_oval(5,7,35,29,fill=WHITE,outline=WHITE)
                icon.create_polygon(19,26,18,33,29,26,fill=WHITE,outline=WHITE)
                icon.create_text(20,18,text='LINE',font=('Arial',7,'bold'),fill='#06C755')
                icon.pack(side='left',padx=(0,16));icon._line_icon=True
            if key in ('facebook','instagram','phone'):
                icon=tk.PhotoImage(file=str(ASSET_DIR/f'{key}_icon.png'),master=self)
                picture=tk.Label(inner,image=icon,bg=WHITE);picture._image=icon;picture.pack(side='left',padx=(0,16))
            words=tk.Frame(inner,bg=WHITE);words.pack(side='left',fill='x',expand=True)
            self.label(words,title,13,True).pack(anchor='w')
            detail=self.label(words,value or self.ui('ร้านยังไม่ได้ระบุช่องทางนี้','This contact channel has not been added.'),12,fg=INK if value else MID)
            detail.pack(anchor='w',pady=(5,0))
            words.bind('<Configure>',lambda event,label=detail:label.configure(wraplength=max(140,event.width-8)))
            if key in ('facebook','instagram') and value.startswith(('https://','http://')):
                self.button(inner,self.ui('เปิด','OPEN'),lambda url=value:webbrowser.open(url),compact=True).pack(side='right',padx=(12,0))


# เริ่มโปรแกรม สร้างหรือปรับฐานข้อมูล และเปิดหน้าต่างหลัก
# J01 | เริ่มโปรแกรม
def run():
    db.create_database()
    app=App()
    app.mainloop()

if __name__=='__main__':run()
