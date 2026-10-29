"""หน้าตั้งค่าบริการตรวจสลิปและส่งอีเมลสำหรับผู้ดูแลร้าน"""
import tkinter as tk
import queue,threading,json,ssl,smtplib,webbrowser
from urllib.request import Request,urlopen
from support import service_settings,admin_data
from support.theme import select_field,check_field
import db

def enable_paste(widget, label='วาง / Paste'):
    """วางข้อความเมื่อผู้ใช้สั่งเท่านั้น รองรับ Ctrl+V ขณะใช้แป้นพิมพ์ภาษาไทย"""
    native=getattr(widget,'_entry',widget)
    def paste(event=None):
        if str(native.cget('state'))!='normal':return 'break'
        try:text=native.clipboard_get()
        except tk.TclError:return 'break'
        if native.selection_present():
            position=native.index('sel.first')
            native.delete('sel.first','sel.last');native.icursor(position)
        native.insert('insert',text)
        native.xview('insert')
        return 'break'
    def shortcut(event):
        if event.keycode==86 or event.keysym.lower()=='v':return paste(event)
    menu=tk.Menu(native,tearoff=False)
    menu.add_command(label=label,command=paste)
    def popup(event):
        native.focus_set()
        try:menu.tk_popup(event.x_root,event.y_root)
        finally:menu.grab_release()
        return 'break'
    native.bind('<<Paste>>',paste)
    native.bind('<Control-KeyPress>',shortcut,add='+')
    native.bind('<Shift-Insert>',paste)
    native.bind('<Button-3>',popup)
    return paste

def test_connections(actor):
    c=db.conn()
    try:admin_data.require_admin(c,actor)
    finally:c.close()
    result=[]
    key=service_settings.get('JPZ_EASYSLIP_API_KEY')
    if key:
        try:
            request=Request('https://api.easyslip.com/v2/info',headers={'Authorization':'Bearer '+key})
            with urlopen(request,timeout=20) as response:info=json.loads(response.read(1024*1024))
            if info.get('success') is not True:raise ValueError('Unavailable')
            result.append('EasySlip ✓')
        except Exception:raise ValueError('เชื่อม EasySlip ไม่สำเร็จ ตรวจ API Key และสถานะบัญชี / EasySlip connection failed; check the key and account status.') from None
    else:result.append('EasySlip — ยังไม่ได้ตั้งค่า / not configured')
    if service_settings.get('JPZ_SMTP_PASSWORD') or service_settings.get('JPZ_RECEIPT_EMAIL')=='1':
        import receipt
        cfg=receipt.config()
        try:
            factory=smtplib.SMTP_SSL if cfg['security']=='SSL' else smtplib.SMTP
            with factory(cfg['host'],int(cfg['port']),timeout=20,**({'context':ssl.create_default_context()} if cfg['security']=='SSL' else {})) as smtp:
                if cfg['security']=='STARTTLS':smtp.starttls(context=ssl.create_default_context())
                smtp.login(cfg['username'],service_settings.get('JPZ_SMTP_PASSWORD'));smtp.noop()
            result.append('Email ✓ · เชื่อมต่อและเข้าสู่ระบบสำเร็จ / Connection and login succeeded')
        except Exception:raise ValueError('เชื่อมอีเมลไม่สำเร็จ ตรวจอีเมลผู้ส่ง รหัสผ่านแอป และการตั้งค่า SMTP / Email connection failed; check the sender, app password and SMTP settings.') from None
    else:result.append('Email — ปิดการส่ง / sending disabled')
    return '\n'.join(result)

# J46 | ตั้งค่าบริการ / วางรหัส
def show(app):
    c=db.conn()
    try:admin_data.require_admin(c,app.user['id'])
    finally:c.close()
    win=tk.Toplevel(app);win.title(app.ui('อีเมลร้าน · ใบเสร็จและ OTP','Store email · receipts and OTP'));win.geometry('780x860');win.configure(bg='white');win.transient(app)
    body=app.scroll_content(win);fields={}
    app.label(body,app.ui('เชื่อมบริการของร้าน','Connect store services'),22,True).pack(anchor='w',padx=24,pady=(20,10))
    app.label(body,app.ui('ตั้งค่าบนเครื่องแอดมิน รหัสลับบันทึกด้วยการป้องกันของบัญชี Windows นี้','Configure on the admin machine. Secrets are protected for this Windows account.'),11,wraplength=680,fg='#786D5B').pack(anchor='w',padx=24,pady=(0,18))
    try:cfg=service_settings.stored()
    except (OSError,ValueError):cfg={}
    host=tk.Frame(body,bg='white');host.pack(fill='x',padx=24)
    def entry(key,th,en,default='',secret=False):
        widget=app.entry(host,app.ui(th,en),show='•' if secret else None);fields[key]=widget
        paste=enable_paste(widget,app.ui('วาง','Paste'))
        if secret:app.button(host,app.ui('วางรหัส','Paste password'),paste,compact=True).pack(anchor='e',pady=(4,0))
        if not secret:widget.insert(0,service_settings.get(key,cfg.get(key,default)))
        return widget
    app.label(host,app.ui('อีเมลสำหรับส่งใบเสร็จและ OTP','Receipt and OTP sender'),17,True).pack(anchor='w',pady=(10,12))
    app.label(host,app.ui('OTP สมัครสมาชิกและลืมรหัสผ่านใช้อีเมลนี้ ไม่ต้องใช้ EasySlip','Registration and password recovery OTPs use this email. EasySlip is not required.'),11,wraplength=650,fg='#786D5B').pack(anchor='w',pady=(0,12))
    enabled=tk.BooleanVar(value=service_settings.get('JPZ_RECEIPT_EMAIL')=='1')
    check_field(host,text=app.ui('ส่งใบเสร็จหลังยืนยันเงินเข้า','Send receipts after confirmed payment'),variable=enabled).pack(anchor='w',pady=(0,12))
    entry('JPZ_SMTP_SENDER','อีเมลผู้ส่งของร้าน','Store sender email','jpzjeans01@gmail.com')
    entry('JPZ_SMTP_USERNAME','บัญชีเข้าสู่ระบบอีเมล · Gmail ใช้อีเมลเดียวกับผู้ส่ง','Mail login · Gmail uses the same email as sender','jpzjeans01@gmail.com')
    entry('JPZ_SMTP_PASSWORD','รหัสผ่านแอป · เว้นว่างเพื่อใช้ค่าเดิม','App password · leave blank to keep the saved password',secret=True)
    secret_status=app.label(host,'',10,wraplength=650,justify='left');secret_status.pack(anchor='w',pady=(4,10))
    def refresh_secret_status():
        saved=bool(service_settings.get('JPZ_SMTP_PASSWORD'))
        account=service_settings.get('JPZ_SMTP_USERNAME','')
        secret_status.configure(text=app.ui('บันทึกรหัสไว้แล้วสำหรับ '+account+' · เว้นช่องว่างเพื่อใช้รหัสเดิม','Password saved for '+account+' · leave the field blank to keep it') if saved else app.ui('ยังไม่มีรหัสที่บันทึกไว้ กรุณากรอกรหัสผ่านแอปแล้วกดบันทึก','No saved password. Enter the app password and save.'),fg='#26734D' if saved else '#786D5B')
    refresh_secret_status()
    reveal=tk.BooleanVar()
    def reveal_secrets():
        for key in ('JPZ_SMTP_PASSWORD','JPZ_EASYSLIP_API_KEY'):fields[key].configure(show='' if reveal.get() else '•')
    check_field(host,text=app.ui('แสดงรหัสที่กำลังกรอก','Show newly entered secrets'),variable=reveal,command=reveal_secrets).pack(anchor='w',pady=(0,16))
    security=tk.StringVar(value=service_settings.get('JPZ_SMTP_SECURITY','STARTTLS'))
    optional=tk.LabelFrame(host,text=app.ui('EasySlip · ตัวเลือกเสริม เว้นว่างได้','EasySlip · optional, may be left blank'),bg='white',fg='#786D5B')
    optional.pack(fill='x',pady=(16,8))
    original_host=host;host=optional
    entry('JPZ_EASYSLIP_BANK_NUMBER','เลขบัญชีร้านที่ลงทะเบียนใน EasySlip','Store bank account registered with EasySlip')
    entry('JPZ_EASYSLIP_API_KEY','API Key · เว้นว่างเพื่อใช้ค่าที่บันทึกไว้','API key · leave blank to keep the saved key',secret=True)
    host=original_host
    status=app.label(host,'',11,wraplength=650,justify='left');status.pack(anchor='w',pady=10)
    def save():
        try:
            values={k:v.get() for k,v in fields.items()};values['JPZ_RECEIPT_EMAIL']='1' if enabled.get() else '0';values.update({key:service_settings.get(key) for key in ('JPZ_SMTP_HOST','JPZ_SMTP_PORT','JPZ_SMTP_SECURITY')})
            if service_settings.get('JPZ_SMTP_HOST')=='smtp.gmail.com':values['JPZ_SMTP_PASSWORD']=values['JPZ_SMTP_PASSWORD'].replace(' ','')
            service_settings.save(app.user['id'],values)
            for key in ('JPZ_SMTP_PASSWORD','JPZ_EASYSLIP_API_KEY'):fields[key].delete(0,'end')
            refresh_secret_status()
            status.configure(text=app.ui('บันทึกรหัสแบบป้องกันไว้แล้ว ช่องรหัสถูกล้างเพื่อไม่แสดงรหัสเดิม กดตรวจการเชื่อมต่อได้','Password saved securely. The input was cleared to hide the saved password. You can check the connection.'),fg='#26734D')
        except (ValueError,PermissionError,OSError) as exc:status.configure(text=str(exc),fg='#BB2020')
    app.button(host,app.ui('บันทึกการเชื่อมต่อ','Save connections'),save,dark=True).pack(anchor='w',pady=8)
    def test():
        actor=app.user['id'];results=queue.Queue();test_button.configure(state='disabled');status.configure(text=app.ui('กำลังตรวจค่าที่บันทึกไว้…','Checking saved settings…'),fg='#786D5B')
        def worker():
            try:results.put((True,test_connections(actor)))
            except Exception as exc:results.put((False,str(exc) if isinstance(exc,(ValueError,PermissionError)) else app.ui('ตรวจการเชื่อมต่อไม่สำเร็จ','Connection check failed.')))
        def poll():
            if not win.winfo_exists():return
            try:ok,message=results.get_nowait()
            except queue.Empty:app.after(50,poll);return
            status.configure(text=message,fg='#26734D' if ok else '#BB2020');test_button.configure(state='normal')
        threading.Thread(target=worker,daemon=True).start();app.after(50,poll)
    test_button=app.button(host,app.ui('ตรวจการเชื่อมต่อ · ไม่ส่งอีเมล','Check connections · no email sent'),test);test_button.pack(anchor='w',pady=(8,20))
    app.label(host,app.ui('เปลี่ยนอีเมลผู้ส่งได้ โดยกรอกบัญชีและรหัสผ่านแอปของอีเมลใหม่ แล้วบันทึก อีเมลหน้าติดต่อร้านแก้แยกได้ในเมนูช่องทางติดต่อ','To change sender, enter the new account and its app password, then save. Contact email is edited separately in store contacts.'),11,wraplength=650,fg='#786D5B').pack(anchor='w',pady=(0,24))
    app.label(host,app.ui('Email ✓ ยืนยันการเชื่อมต่อเท่านั้น ไม่ได้ส่งข้อความทดสอบหรือยืนยันว่าอีเมลถึงกล่องขาเข้า','Email ✓ confirms the connection only. It does not send a test message or confirm inbox delivery.'),10,wraplength=650,fg='#786D5B').pack(anchor='w',pady=(0,16))
    app._service_setup_ui=dict(window=win,fields=fields,enabled=enabled,security=security,status=status,secret_status=secret_status,save=save,test=test)
    win.after_idle(lambda:body.master.yview_moveto(0) if body.winfo_exists() else None)
    return win
