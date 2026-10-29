# หน้าล็อกอิน สมัครสมาชิก และกู้รหัสผ่าน
# ใช้เป็นส่วนหนึ่งของ App ใน main.py และเรียกฟังก์ชันบันทึกข้อมูลจาก db.py

"""Login and registration. Run this file to start JPZ."""
import tkinter as tk
from tkinter import ttk,messagebox,filedialog
from pathlib import Path
from PIL import Image,ImageTk
import db
from support import admin_data, email_otp
import threading
import queue
from support.theme import ctk,card,field,DENIM,BACKDROP,surface
BASE_DIR=Path(__file__).resolve().parent
ASSET_DIR=BASE_DIR/'assets'
WHITE='#FFFFFF';INK='#080808';SOFT='#F4F4F4';MID='#505050';LINE='#DADADA';PIL_AVAILABLE=True

class StartprogramMixin:
    def password_field(self,parent,title):
        self.label(parent,title,11,True,fg=MID).pack(anchor='w',pady=(12,6))
        row=tk.Frame(parent,bg=WHITE);row.pack(fill='x')
        entry=field(row,show='•');entry.pack(side='left',fill='x',expand=True)
        visible=[False]
        def toggle():
            visible[0]=not visible[0];entry.configure(show='' if visible[0] else '•')
            button.configure(text=self.ui('ซ่อน','Hide') if visible[0] else self.ui('ดู','Show'))
        button=self.button(row,self.ui('ดู','Show'),toggle,compact=True);button.pack(side='right',padx=(8,0))
        entry._visibility_button=button
        return entry

    # จัดหน้าล็อกอินและสมัครสมาชิก แบ่งภาพแบรนด์กับฟอร์มกรอกข้อมูล
    def auth_layout(self,title,subtitle):
        self.clear()
        root=ctk.CTkFrame(self,fg_color=WHITE,corner_radius=0);root.pack(fill='both',expand=True)
        header=tk.Frame(root,bg=WHITE,height=78);header.pack(fill='x');header.pack_propagate(False)
        brand=tk.Frame(header,bg=WHITE);brand.pack(side='left',padx=30,pady=12)
        self.brand_mark(brand,25).pack(side='left')
        self.label(brand,'PIZZA JEANS',10,True,fg=MID).pack(side='left',padx=16)
        self.lang_switch(header)
        self.label(header,'DENIM MADE PERSONAL.',11,True,fg=DENIM).pack(side='right',padx=20)
        tk.Frame(root,bg=LINE,height=1).pack(fill='x')
        content=tk.Frame(root,bg=WHITE);content.pack(fill='both',expand=True)
        left=tk.Frame(content,bg=INK);left.place(relx=0,rely=0,relwidth=.54,relheight=1)
        campaign_path=ASSET_DIR/'login_campaign_final.png'
        if campaign_path.exists():
            with Image.open(campaign_path) as image:campaign=image.convert('RGB').copy()
            photo_label=tk.Label(left,bg=INK,bd=0);photo_label.pack(fill='both',expand=True)
            last=[None]
            def cover(event):
                size=(max(1,event.width),max(1,event.height))
                if size==last[0]:return
                last[0]=size
                from PIL import ImageOps
                photo=ImageTk.PhotoImage(ImageOps.fit(campaign,size,method=Image.Resampling.LANCZOS,centering=(.25,.5)),master=self)
                photo_label.configure(image=photo);photo_label._image=photo
            photo_label.bind('<Configure>',cover)
        right=ctk.CTkFrame(content,fg_color=WHITE,corner_radius=0)
        right.place(relx=.54,rely=0,relwidth=.46,relheight=1)
        panel=card(right);panel.place(relx=.5,rely=.5,anchor='center',relwidth=.86,relheight=.88)
        body=self.scroll_content(panel)
        form=tk.Frame(body,bg=WHITE);form.pack(fill='x',padx=30,pady=22)
        self.label(form,'JPZ / MEMBER',11,True,fg=DENIM).pack(anchor='w',pady=(0,12))
        self.label(form,title,27,True).pack(anchor='w',pady=(0,6))
        if subtitle:self.label(form,subtitle,11,fg=MID,wraplength=420,justify='left').pack(anchor='w',pady=(0,14))
        return form

    # แสดงฟอร์มเข้าสู่ระบบและเตรียมช่องอีเมลกับรหัสผ่าน
    # J02 | หน้าล็อกอิน
    def show_login(self,push=False):
        self._register_draft=None;self._register_pending=None;self._register_token=''
        self.current_page='login';self.current_args={}
        form=self.auth_layout(self.tr('login'),self.ui('เข้าสู่ระบบเพื่อเลือกยีนส์และดูคำสั่งซื้อของคุณ','Sign in to shop jeans and view your orders.'))
        self.email=self.entry(form,self.tr('email'))
        self.label(form,self.tr('password'),11,True,fg=MID).pack(anchor='w',pady=(12,6))
        row=tk.Frame(form,bg=WHITE);row.pack(fill='x')
        self.password=field(row,show='•');self.password.pack(side='left',fill='x',expand=True)
        self.password_visible=False
        self.password_toggle=self.button(row,self.ui('ดู','Show'),self.toggle_password_visibility,compact=True)
        self.password_toggle.pack(side='right',padx=(8,0))
        self.login_error=self.label(form,'',11,True,fg='#B3261E');self.login_error.pack(anchor='w',pady=4)
        self.email.bind('<KeyRelease>',self.clear_login_error)
        self.password.bind('<KeyRelease>',self.clear_login_error)
        self.password.bind('<Return>',lambda event:self.login())
        self.button(form,self.tr('forgot_password'),self.forgot_password_page,compact=True).pack(anchor='e',pady=4)
        self.button(form,self.tr('login'),self.login,dark=True).pack(fill='x',pady=(16,8))
        self.button(form,self.tr('create_account'),self.register_page).pack(fill='x',pady=(0,12))
        self.label(form,'FIND YOUR FIT. / JPZ',11,True,fg=MID).pack(pady=(14,0))

    # สลับการแสดงหรือซ่อนรหัสผ่านในช่องกรอก
    def toggle_password_visibility(self):
        self.password_visible = not self.password_visible

        if self.password_visible:
            self.password.configure(show='')
            button_text = 'HIDE' if self.lang == 'EN' else 'ซ่อน'
        else:
            self.password.configure(show='•')
            button_text = 'SHOW' if self.lang == 'EN' else 'ดู'

        self.password_toggle.configure(text=button_text)


    # ล้างข้อความแจ้งข้อผิดพลาดเมื่อผู้ใช้เริ่มแก้ข้อมูล
    def clear_login_error(self, event=None):
        if hasattr(self, 'login_error'):
            self.login_error.configure(text='')


    # ตรวจบัญชีและรหัสผ่าน แล้วเปิดหน้าร้านหรือหน้าแอดมินตามสิทธิ์
    def login(self):
        status,user = db.login_status(self.email.get(), self.password.get())
        if status=='banned':
            self.login_error.configure(text=self.ui('บัญชีนี้ถูกแบน กรุณาติดต่อร้าน','This account is banned. Please contact the store.'),wraplength=520,justify='left')
            return
        if not user:
            self.login_error.configure(text=self.tr('bad_login'))
            return

        self.user = user
        admin_data.log_event(user['id'], 'login')
        self.lang = user.get('language') or 'TH'
        self.page_history = []
        self.admin(push=False) if user['role'] == 'admin' else self.home(push=False)


    # แสดงฟอร์มสำหรับกู้รหัสผ่านของบัญชี
    # J06 | ลืมรหัสผ่าน
    def forgot_password_page(self):
        self.current_page='forgot_password';self.current_args={}
        self._reset_token=''
        f=self.auth_layout(self.ui('ลืมรหัสผ่าน','Forgot password'),self.ui('รับ OTP ทางอีเมลที่สมัครไว้ แล้วตั้งรหัสผ่านใหม่','Receive an OTP at your registered email, then set a new password.'))
        self.reset_email=self.entry(f,self.tr('email'))
        self._otp_send_button=self.button(f,self.ui('ส่ง OTP','Send OTP'),self.send_password_otp,dark=True)
        self._otp_send_button.pack(fill='x',pady=(12,6))
        self._otp_notice=self.label(f,'',11,fg=MID,wraplength=420,justify='left');self._otp_notice.pack(anchor='w',pady=5)
        self.email_delivery_notice(f)
        self.reset_code=self.entry(f,self.ui('รหัส OTP 6 หลักจากอีเมล','6-digit email OTP'))
        self.reset_new=self.password_field(f,self.tr('reset_new_password'))
        self.label(f,self.tr('password_rule'),11,fg=MID,wraplength=420,justify='left').pack(anchor='w',pady=5)
        self.reset_confirm=self.password_field(f,self.tr('reset_confirm_password'))
        self._otp_reset_button=self.button(f,self.tr('reset_password'),self.do_reset_password,dark=True)
        self._otp_reset_button.pack(fill='x',pady=(18,8))
        self.button(f,self.tr('back_login'),lambda:self.show_login(push=False)).pack(fill='x')

    def _otp_background(self, action, success):
        # Only the main UI thread touches Tk widgets; mail does not freeze the page.
        page=self._otp_send_button
        page_name=self.current_page
        if getattr(self,'_otp_busy',False):return
        self._otp_busy=True
        self._otp_send_button.configure(state='disabled');self._otp_reset_button.configure(state='disabled')
        results=queue.Queue()
        def run():
            try:results.put((True,action()))
            except Exception as exc:results.put((False,str(exc)))
        threading.Thread(target=run,daemon=True).start()
        def poll():
            try:ok,value=results.get_nowait()
            except queue.Empty:
                self.after(100,poll);return
            self._otp_busy=False
            if not page.winfo_exists() or self.current_page!=page_name:return
            self._otp_send_button.configure(state='normal');self._otp_reset_button.configure(state='normal')
            if ok:success(value)
            else:
                self._otp_notice.configure(text=self.ui('ทำรายการไม่สำเร็จ กรุณาตรวจข้อมูลแล้วลองใหม่','Request failed. Check the details and try again.'))
                messagebox.showerror('JPZ',value)
        self.after(100,poll)

    def send_password_otp(self):
        email=self.reset_email.get().strip()
        try:
            db.validate_email(email)
        except ValueError as exc:return messagebox.showwarning('JPZ',str(exc))
        self._reset_token=''
        self._otp_notice.configure(text=self.ui('กำลังส่ง OTP…','Sending OTP…'))
        def sent(token):
            self._reset_token=token;self._reset_identity=email.casefold()
            self._otp_notice.configure(text=self.ui('หากมีบัญชีนี้ ระบบส่ง OTP ทางอีเมลแล้ว รหัสใช้ได้ 10 นาที ตรวจโฟลเดอร์สแปมด้วย','If the account exists, an email OTP was sent. Valid for 10 minutes. Check spam too.'))
            self.reset_code.focus_set()
        self._otp_background(lambda:email_otp.send(email,'reset'),sent)

    def do_reset_password(self):
        email=self.reset_email.get().strip()
        new_password=self.reset_new.get();confirm=self.reset_confirm.get();code=self.reset_code.get().strip()
        if not self._reset_token or getattr(self,'_reset_identity',None)!=email.casefold():
            return messagebox.showwarning('JPZ',self.ui('กรุณาส่ง OTP สำหรับบัญชีนี้ก่อน','Request an OTP for this account first.'))
        try:db.validate_password(new_password)
        except ValueError as exc:return messagebox.showwarning('JPZ',str(exc))
        if new_password!=confirm:return messagebox.showwarning('JPZ',self.tr('password_mismatch'))
        token=self._reset_token
        def changed(result):
            self._reset_token='';messagebox.showinfo('JPZ',self.tr('reset_success'));self.show_login(push=False)
        self._otp_background(lambda:email_otp.complete(token,email,'reset',code,new_password),changed)


    # เปิดหน้าสมัครสมาชิก
    def register_page(self):
        self._register_draft=None;self._register_pending=None
        self.navigate('register', self.register_page_view)


    # สร้างฟอร์มสมัครสมาชิกสำหรับการย้อนกลับระหว่างหน้า
    # J03 | สมัครสมาชิก
    def register_page_view(self):
        draft=getattr(self,'_register_draft',None)
        self.current_page='register'
        self.current_args={}
        self._register_token=''
        f=self.auth_layout(self.ui('สมัครบัญชี','Create account'),'')
        names=tk.Frame(f,bg=WHITE);names.pack(fill='x');names.columnconfigure(0,weight=1);names.columnconfigure(1,weight=1)
        left=tk.Frame(names,bg=WHITE);left.grid(row=0,column=0,sticky='ew',padx=(0,8))
        right=tk.Frame(names,bg=WHITE);right.grid(row=0,column=1,sticky='ew',padx=(8,0))
        self.rfn=self.entry(left,self.tr('first_name'));self.rln=self.entry(right,self.tr('last_name'))
        self.rem=self.entry(f,self.tr('email'))
        self.rphone=self.phone_entry(f)
        self.rpw=self.password_field(f,self.tr('password'))
        self.label(f,self.tr('password_rule'),11,fg=MID,wraplength=420,justify='left').pack(anchor='w',pady=5)
        self.rconfirm=self.password_field(f,self.ui('ยืนยันรหัสผ่าน','Confirm password'))
        if draft:
            for widget,key in ((self.rfn,'first_name'),(self.rln,'last_name'),(self.rem,'email'),(self.rphone,'phone'),(self.rpw,'password'),(self.rconfirm,'password')):widget.insert(0,draft[key])
        self._otp_send_button=self.button(f,self.ui('สมัครบัญชี','Create account'),self.send_register_otp,dark=True)
        self._otp_send_button.pack(fill='x',pady=(12,6))
        self._otp_reset_button=self._otp_send_button
        self._otp_notice=self.label(f,'',11,fg=MID,wraplength=420,justify='left');self._otp_notice.pack(anchor='w',pady=5)
        self.email_delivery_notice(f)
        self.button(f,self.tr('back_login'),lambda:self.show_login(push=False)).pack(fill='x')

    # ตรวจข้อมูลสมัครสมาชิกและบันทึกบัญชีลง SQLite
    def registration_details(self):
        return dict(first_name=self.rfn.get().strip(),last_name=self.rln.get().strip(),phone=self.rphone.get().strip(),password=self.rpw.get(),language=self.lang)

    # J04 | ส่ง OTP สมัครสมาชิก
    def send_register_otp(self):
        if not all((x.get().strip() for x in (self.rfn, self.rln, self.rem, self.rpw))):
            return messagebox.showwarning('FIND YOUR FIT', self.tr('complete_fields'))
        email=self.rem.get().strip();details=self.registration_details()
        try:
            db.validate_email(email);db.validate_phone(details['phone']);db.validate_password(details['password'])
        except ValueError as exc:
            return messagebox.showerror('JPZ',str(exc))
        if details['password']!=self.rconfirm.get():return messagebox.showwarning('JPZ',self.tr('password_mismatch'))
        self._register_draft=dict(details,email=email)
        self._register_token='';self._otp_notice.configure(text=self.ui('กำลังส่ง OTP…','Sending OTP…'))
        def sent(token):
            self._register_token=token;self._register_pending=(email,details)
            self.register_otp_page()
        self._otp_background(lambda:email_otp.send(email,'register',details),sent)

    # J05 | หน้ากรอก OTP สมัครสมาชิก
    def register_otp_page(self):
        pending=getattr(self,'_register_pending',None)
        if not pending or not self._register_token:return self.register_page_view()
        self.current_page='register_otp';self.current_args={}
        email,details=pending
        f=self.auth_layout(self.ui('ยืนยันอีเมล','Verify email'),self.ui('ขั้นตอน 2 / 2 · กรอกรหัส OTP เพื่อสมัครบัญชีให้สำเร็จ','Step 2 / 2 · Enter the OTP to complete your account registration.'))
        self.label(f,self.ui('ส่งรหัสไปยัง','Code sent to'),11,fg=MID).pack(anchor='w',pady=(6,4))
        self.label(f,email,13,True,fg=DENIM,wraplength=420,justify='left').pack(anchor='w',pady=(0,12))
        self.register_code=self.entry(f,self.ui('รหัส OTP 6 หลักจากอีเมล','6-digit email OTP'))
        self._otp_notice=self.label(f,self.ui('รหัสใช้ได้ 10 นาที หากไม่พบอีเมลให้ตรวจสแปม','Valid for 10 minutes. Check spam if the email is missing.'),11,fg=MID,wraplength=420,justify='left');self._otp_notice.pack(anchor='w',pady=(8,12))
        self.email_delivery_notice(f)
        self._otp_reset_button=self.button(f,self.ui('ยืนยัน OTP และสมัครบัญชี','Verify OTP and create account'),self.do_register,dark=True);self._otp_reset_button.pack(fill='x',pady=(6,8))
        self._otp_send_button=self.button(f,self.ui('ส่ง OTP ใหม่','Resend OTP'),self.resend_register_otp);self._otp_send_button.pack(fill='x',pady=(0,8))
        self.button(f,self.ui('กลับไปแก้ข้อมูล','Back to edit details'),self.register_page_view).pack(fill='x',pady=(0,8))
        self.button(f,self.tr('back_login'),lambda:self.show_login(push=False)).pack(fill='x')
        self.register_code.focus_set()

    def resend_register_otp(self):
        if not getattr(self,'_register_pending',None):return
        email,details=self._register_pending
        self._otp_notice.configure(text=self.ui('กำลังส่ง OTP ใหม่…','Sending a new OTP…'))
        def sent(token):
            self._register_token=token;self.register_code.delete(0,'end')
            self._otp_notice.configure(text=self.ui('ส่งรหัสใหม่แล้ว ใช้ได้ 10 นาที รหัสเดิมใช้ไม่ได้แล้ว','New code sent. Valid for 10 minutes. The previous code is no longer valid.'))
        self._otp_background(lambda:email_otp.send(email,'register',details),sent)

    def do_register(self):
        if not self._register_token or not getattr(self,'_register_pending',None):
            return messagebox.showwarning('JPZ',self.ui('กรอกข้อมูลและกดสมัครบัญชีก่อน','Enter your details and create an account first.'))
        email,details=self._register_pending
        token=self._register_token;code=self.register_code.get().strip()
        def created(result):
            self._register_token='';self._register_pending=None;self._register_draft=None
            messagebox.showinfo('JPZ',self.tr('account_created'));self.show_login(push=False)
        self._otp_background(lambda:email_otp.complete(token,email,'register',code),created)



if __name__=='__main__':
    from main import run
    run()
