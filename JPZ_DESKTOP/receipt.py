# ข้อมูลรับชำระ เอกสารใบเสร็จ และหน้ารายละเอียดคำสั่งซื้อ
# ใบเสร็จรับเงินออกหลังแอดมินยืนยันชำระแล้วเท่านั้น
# เปิดส่งเมื่อร้านตั้งค่าบริการและเปิดใช้งานอีเมลใบเสร็จ

"""Paid receipts and durable SMTP outbox; secrets stay in memory or environment."""
import os, json, html, ssl, smtplib, threading
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import formatdate,make_msgid
import db
from support import service_settings
EMAIL_ENABLED = False
_password = ''
_worker_lock = threading.Lock()

# เพิ่มตารางและคอลัมน์สำหรับเก็บใบเสร็จและเวลาที่รับชำระ
def migrate(c):
    c.execute('CREATE TABLE IF NOT EXISTS order_corrections(id INTEGER PRIMARY KEY,order_id INTEGER,actor_id INTEGER,snapshot TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
    c.execute('CREATE TABLE IF NOT EXISTS receipt_reference_history(trans_ref TEXT PRIMARY KEY,order_id INTEGER NOT NULL)')
    c.execute("CREATE TABLE IF NOT EXISTS receipt_approvals(order_id INTEGER PRIMARY KEY,payment_id INTEGER NOT NULL,amount REAL NOT NULL,actor_id INTEGER NOT NULL,method TEXT NOT NULL,trans_ref TEXT NOT NULL UNIQUE,created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    c.execute('INSERT OR IGNORE INTO receipt_reference_history SELECT UPPER(trans_ref),order_id FROM receipt_approvals')
    c.execute("CREATE TABLE IF NOT EXISTS receipt_outbox(order_id INTEGER PRIMARY KEY,user_id INTEGER,recipient TEXT,receipt TEXT,status TEXT DEFAULT 'pending',attempts INTEGER DEFAULT 0,error TEXT DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP,sent_at TEXT,claimed_at TEXT)")
    db.add_column_if_missing(c,'receipt_outbox','claimed_at','TEXT')
    db.add_column_if_missing(c,'orders','paid_at','TEXT')
    c.execute("UPDATE receipt_outbox SET status='pending' WHERE status='sending' AND (claimed_at IS NULL OR claimed_at<datetime('now','-10 minutes'))")

# อ่านคำสั่งซื้อเฉพาะเมื่อหมายเลขบัญชีเป็นเจ้าของคำสั่งซื้อนั้น
def order_for(uid, oid):
    c=db.conn()
    try:
        row=c.execute('SELECT * FROM orders WHERE id=? AND user_id=?',(oid,uid)).fetchone()
        return dict(row) if row else None
    finally:c.close()

# แปลงเวลา UTC ที่จัดเก็บเป็นเวลาไทย UTC+7 สำหรับแสดงผล
def local_time(value):
    if not value:return '—'
    try:return (datetime.fromisoformat(value)+timedelta(hours=7)).strftime('%d/%m/%Y %H:%M')
    except ValueError:return str(value)

# สร้างเอกสารใบเสร็จ HTML จากข้อมูลคำสั่งซื้อ รายการสินค้า และ VAT
def build_receipt(c, order):
    e=lambda v:html.escape(str(v))
    order=dict(order)
    tax=db.vat_breakdown(order['total'])
    from support import order_amounts
    rows=order_amounts.lines([dict(r) for r in c.execute('SELECT * FROM order_items WHERE order_id=? ORDER BY id',(order['id'],))],order['total'])
    discount_caption=('โปรโมชั่นรายสินค้า / Product offers' if order.get('discount_kind')=='product' else f"ส่วนลด DAILY DENIM {order['promo_day'] or '—'} / {order['promo_percent']}%")
    condition_note='' if order.get('discount_kind')=='product' else f"<br>เงื่อนไขขั้นต่ำ ฿{order.get('promo_minimum',0):g} / ลดสูงสุด ฿{order.get('promo_cap',0):g}"
    lines=''.join(f"<tr><td>{e(r['product_name'])}<br><small>{e(r['product_code'])} / {e(r['color'])} / {e(db.size_label(r['size']))}</small></td><td>{r['quantity']}</td><td>฿{r['price']:,.2f}</td><td><small>ก่อนส่วนลด ฿{r['original_total']:,.2f}</small><br><strong style=color:#8C2635>฿{r['net_total']:,.2f}</strong></td></tr>" for r in rows)
    return f'''<!doctype html><html lang="th"><meta charset="utf-8"><title>หมายเลขคำสั่งซื้อ {e(db.order_number(order))} / ใบเสร็จ JPZ</title><style>body{{font-family:Tahoma,sans-serif;max-width:850px;margin:45px auto;padding:45px;color:#151515;border:1px solid #dedede;background:#fff;line-height:1.6}}table{{width:100%;border-collapse:collapse}}td,th{{padding:14px;border-bottom:1px solid #ddd;text-align:left}}small{{color:#666}}.paid{{color:#26734d}}@media print{{button{{display:none}}}}</style><header style="border-bottom:3px solid #111;padding-bottom:22px"><h1 style="font-size:48px;letter-spacing:-3px;margin:0">JPZ.</h1><small>DENIM MADE PERSONAL.</small></header><h2>ใบเสร็จรับเงิน / RECEIPT</h2><p class="paid">ยืนยันชำระเงินแล้ว / PAID</p><p>เลขที่ {e(db.order_number(order))}<br>วันที่สั่งซื้อ {e(local_time(order['created_at']))}<br>วันที่ยืนยันรับชำระ {e(local_time(order['paid_at']))} (เวลาไทย)</p><p>ลูกค้า: {e(order['customer_name'])}<br>ที่อยู่จัดส่ง: {e(order['address'])}<br>รหัสไปรษณีย์: {e(order.get('postal_code',''))}<br>โทรศัพท์: {e(order['phone'])}</p><table><tr><th>สินค้า</th><th>จำนวน</th><th>ราคาต่อชิ้น</th><th>ยอดหลังส่วนลด</th></tr>{lines}</table><small>ยอดแต่ละรายการแบ่งส่วนลดตามสัดส่วนราคาสินค้า</small><p>ยอดก่อน VAT (หลังหักส่วนลดแล้ว) ฿{tax['before_vat']:,.2f}<br>VAT 7% ที่รวมอยู่ในยอดชำระ ฿{tax['vat']:,.2f}</p><h2>ยอดชำระแล้ว ฿{order['total']:,.2f}</h2><small>VAT รวมอยู่ในยอดชำระแล้ว</small><p>ขอบคุณที่เลือก JPZ / DENIM MADE PERSONAL.</p><small>เอกสารยืนยันการรับชำระเงิน ไม่ใช่ใบกำกับภาษี</small></html>'''

# เก็บสำเนาใบเสร็จของคำสั่งซื้อที่แอดมินยืนยันรับชำระแล้ว
def enqueue(c, oid):
    order=c.execute("SELECT * FROM orders WHERE id=? AND payment_status='paid'",(oid,)).fetchone()
    if not order:raise ValueError('A receipt requires approved payment.')
    user=c.execute('SELECT email FROM users WHERE id=?',(order['user_id'],)).fetchone()
    c.execute('INSERT OR IGNORE INTO receipt_outbox(order_id,user_id,recipient,receipt) VALUES(?,?,?,?)',(oid,order['user_id'],user['email'],build_receipt(c,order)))
    c.execute("UPDATE receipt_outbox SET receipt=?,status='pending',attempts=0,error='',sent_at=NULL,claimed_at=NULL WHERE order_id=? AND status='void'",(build_receipt(c,order),oid))

def record_approval(c, actor, oid, reference, verified_payment=None):
    from support import admin_data
    admin_data.require_admin(c,actor)
    reference=str(reference or '').strip().upper()
    if not reference or len(reference)>128 or any(ch.isspace() for ch in reference):
        raise ValueError('กรอกเลขอ้างอิงจากสลิปให้ครบ / Enter the complete slip transaction reference.')
    order=c.execute("SELECT total FROM orders WHERE id=? AND payment_status='paid'",(oid,)).fetchone()
    payment=c.execute('SELECT id FROM payments WHERE order_id=? ORDER BY id DESC LIMIT 1',(oid,)).fetchone()
    if not order or not payment:raise ValueError('Approved payment and slip required.')
    if c.execute('SELECT 1 FROM verified_slips WHERE UPPER(trans_ref)=? AND order_id!=?',(reference,oid)).fetchone():
        raise ValueError('เลขอ้างอิงนี้ใช้กับคำสั่งซื้ออื่นแล้ว / Reference already belongs to another order.')
    if c.execute('SELECT 1 FROM receipt_reference_history WHERE trans_ref=? AND order_id!=?',(reference,oid)).fetchone():
        raise ValueError('เลขอ้างอิงนี้ใช้กับคำสั่งซื้ออื่นแล้ว / Reference already belongs to another order.')
    try:
        c.execute('INSERT INTO receipt_approvals(order_id,payment_id,amount,actor_id,method,trans_ref) VALUES(?,?,?,?,?,?) ON CONFLICT(order_id) DO UPDATE SET payment_id=excluded.payment_id,amount=excluded.amount,actor_id=excluded.actor_id,method=excluded.method,trans_ref=excluded.trans_ref,created_at=CURRENT_TIMESTAMP',
                  (oid,payment['id'],order['total'],actor,'service' if verified_payment else 'manual',reference))
        c.execute('INSERT OR IGNORE INTO receipt_reference_history VALUES(?,?)',(reference,oid))
    except db.sqlite3.IntegrityError:raise ValueError('เลขอ้างอิงนี้ถูกใช้แล้ว / Transaction reference already used.') from None

def approval(oid):
    c=db.conn()
    try:
        row=c.execute('SELECT * FROM receipt_approvals WHERE order_id=?',(oid,)).fetchone()
        return dict(row) if row else None
    finally:c.close()

# อ่านหรือสร้างใบเสร็จเฉพาะคำสั่งซื้อที่ยืนยันชำระแล้ว
def receipt_html(uid, oid):
    c=db.conn()
    try:
        order=c.execute("SELECT * FROM orders WHERE id=? AND user_id=? AND payment_status='paid'",(oid,uid)).fetchone()
        if not order:raise PermissionError('Receipt unavailable for this account or payment status.')
        enqueue(c,oid)
        c.execute('UPDATE receipt_outbox SET receipt=? WHERE order_id=?',(build_receipt(c,order),oid));c.commit()
        return c.execute('SELECT receipt FROM receipt_outbox WHERE order_id=?',(oid,)).fetchone()['receipt']
    finally:c.close()

# อ่านการตั้งค่าระบบอีเมลเดิม ซึ่งปิดใช้งานในโปรแกรมนี้
def config():
    c=db.conn()
    try:
        row=c.execute("SELECT value FROM shop_metadata WHERE key='receipt_smtp'").fetchone()
        cfg=json.loads(row['value']) if row else {'sender':'','username':'','host':'','port':'587','security':'STARTTLS'}
        for field in ('sender','username','host','port','security'):
            override=service_settings.get('JPZ_SMTP_'+field.upper())
            if override:cfg[field]=override
        return cfg
    finally:c.close()

# ตรวจว่าระบบอีเมลเดิมมีการตั้งค่าหรือไม่
def enabled():
    return EMAIL_ENABLED or service_settings.get('JPZ_RECEIPT_EMAIL')=='1'

def configured():
    if not enabled():return False
    cfg=config()
    return bool(cfg.get('host') and cfg.get('sender') and cfg.get('security') in ('STARTTLS','SSL') and (not cfg.get('username') or _password or service_settings.get('JPZ_SMTP_PASSWORD')))

# เก็บค่าระบบอีเมลเดิมสำหรับความเข้ากันได้ ไม่มีช่องตั้งค่านี้ในหน้าร้าน
def save_config(actor, cfg, password=''):
    global _password
    if not EMAIL_ENABLED:raise ValueError('Email delivery is disabled.')
    from support import admin_data as admin
    clean={k:str(cfg.get(k,'')).strip() for k in ('host','port','sender','username','security')}
    if clean['security'] not in ('STARTTLS','SSL'):raise ValueError('Choose SSL or STARTTLS.')
    if not clean['host'] or '@' not in clean['sender'] or any('\n' in v or '\r' in v for v in clean.values()):raise ValueError('Enter valid SMTP host and sender.')
    port=int(clean['port'])
    if not 1<=port<=65535:raise ValueError('Invalid SMTP port.')
    with admin.transaction(actor) as c:
        c.execute("INSERT INTO shop_metadata VALUES('receipt_smtp',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(json.dumps(clean),))
        admin.audit(c,actor,'smtp_settings_saved','email','SMTP settings updated (password excluded)')
    if password:
        _password=password.replace(' ', '') if clean['host']=='smtp.gmail.com' else password

# ส่งอีเมลผ่านระบบเดิมเมื่อเปิดใช้งาน แต่ค่า EMAIL_ENABLED ปัจจุบันเป็น False
def delivery(oid):
    c=db.conn()
    try:
        r=c.execute('SELECT order_id,recipient,status,attempts,error,sent_at FROM receipt_outbox WHERE order_id=?',(oid,)).fetchone()
        return dict(r) if r else None
    finally:c.close()

# ปรับคิวใบเสร็จเดิมให้พร้อมลองใหม่
def retry(actor,oid=None):
    from support import admin_data as admin
    with admin.transaction(actor) as c:
        paid=c.execute("SELECT id FROM orders WHERE payment_status='paid'"+(' AND id=?' if oid is not None else ''),(oid,) if oid is not None else ()).fetchall()
        if oid is not None and not paid:raise ValueError('Paid order not found.')
        for row in paid:enqueue(c,row['id'])
        c.execute("UPDATE receipt_outbox SET status='pending',error='' WHERE status='failed' AND order_id IN (SELECT id FROM orders WHERE payment_status='paid')"+(' AND order_id=?' if oid is not None else ''),(oid,) if oid is not None else ())
        admin.audit(c,actor,'receipt_retry','email','Retry pending/failed paid receipts')
    start_worker()

# ส่งคิวใบเสร็จเฉพาะเมื่อเปิดใช้งานและเชื่อมอีเมลแล้ว
# J32 | ส่งใบเสร็จทางอีเมล
def process_pending():
    if not configured():return
    cfg=config();c=db.conn()
    try:
        ids=[r['order_id'] for r in c.execute("SELECT r.order_id FROM receipt_outbox r JOIN orders o ON o.id=r.order_id WHERE r.status='pending' AND o.payment_status='paid' AND (EXISTS(SELECT 1 FROM verified_slips v WHERE v.order_id=o.id AND v.amount=o.total AND v.payment_id=(SELECT MAX(id) FROM payments WHERE order_id=o.id)) OR EXISTS(SELECT 1 FROM receipt_approvals a WHERE a.order_id=o.id AND a.amount=o.total AND a.payment_id=(SELECT MAX(id) FROM payments WHERE order_id=o.id))) ORDER BY r.order_id LIMIT 20")]
        for oid in ids:
            cur=c.execute("UPDATE receipt_outbox SET status='sending',claimed_at=CURRENT_TIMESTAMP,attempts=attempts+1 WHERE order_id=? AND status='pending' AND EXISTS(SELECT 1 FROM orders WHERE id=receipt_outbox.order_id AND payment_status='paid')",(oid,));c.commit()
            if cur.rowcount!=1:continue
            row=c.execute('SELECT * FROM receipt_outbox WHERE order_id=?',(oid,)).fetchone()
            try:
                from support import mail_message,receipt_pdf,order_amounts
                order,lines=receipt_pdf.receipt_data(row['user_id'],oid)
                number=db.order_number(order)
                msg=mail_message.create(cfg['sender'],row['recipient'],'JPZ | ใบเสร็จรับเงิน '+number)
                amounts=order_amounts.lines(lines,order['total'])
                item_text='\n'.join(f"{item.get('product_name') or 'สินค้า'} / {item['color']} / {db.size_label(item['size'])} × {item['quantity']} = ฿{item['net_total']:,.2f}" for item in amounts)
                msg.set_content(f"JPZ Pizza Jeans\nใบเสร็จรับเงิน {number}\nยืนยันชำระแล้ว\n\n{item_text}\n\nยอดชำระแล้ว ฿{order['total']:,.2f} (รวม VAT 7%)\n\nแนบภาพใบเสร็จทุกหน้าและ PDF ให้ดาวน์โหลด\nขอบคุณที่เลือก JPZ")
                import tempfile
                from pathlib import Path
                from support import receipt_pdf
                with tempfile.TemporaryDirectory(dir=db.BASE_DIR) as folder:
                    pdf,images=receipt_pdf.email_files(row['user_id'],oid,folder)
                    # แสดงภาพใบเสร็จในอีเมล พร้อมไฟล์แนบที่ดาวน์โหลดได้ทุกหน้า
                    pictures=[];image_parts=[]
                    for index,path in enumerate(images):
                        cid=make_msgid(domain='jpz.receipt')
                        pictures.append(f'<img src="cid:{cid[1:-1]}" alt="ใบเสร็จหน้า {index+1}" style="display:block;width:100%;max-width:800px;height:auto;margin:16px auto">')
                        image_parts.append((path,cid))
                    item_html=''.join('<li>'+html.escape(line)+'</li>' for line in item_text.splitlines())
                    summary='<h2>JPZ Pizza Jeans · ใบเสร็จรับเงิน</h2><p>เลขที่ '+html.escape(number)+'</p><p>ยืนยันชำระแล้ว</p><ul>'+item_html+'</ul><p><strong>ยอดชำระแล้ว ฿'+f"{order['total']:,.2f}"+'</strong> (รวม VAT 7%)</p>'
                    msg.add_alternative('<html><body>'+summary+'<p>แนบภาพใบเสร็จทุกหน้าและ PDF ให้ดาวน์โหลด ขอบคุณที่เลือก JPZ</p>'+''.join(pictures)+'</body></html>',subtype='html')
                    html_part=msg.get_payload()[-1]
                    for path,cid in image_parts:
                        data=path.read_bytes()
                        html_part.add_related(data,maintype='image',subtype='png',cid=cid,filename=path.name,disposition='inline')
                        msg.add_attachment(data,maintype='image',subtype='png',filename=path.name)
                    msg.add_attachment(pdf.read_bytes(),maintype='application',subtype='pdf',filename=pdf.name)
                factory=smtplib.SMTP_SSL if cfg['security']=='SSL' else smtplib.SMTP
                with factory(cfg['host'],int(cfg['port']),timeout=20,**({'context':ssl.create_default_context()} if cfg['security']=='SSL' else {})) as smtp:
                    if cfg['security']=='STARTTLS':smtp.starttls(context=ssl.create_default_context())
                    if cfg.get('username'):smtp.login(cfg['username'],_password or service_settings.get('JPZ_SMTP_PASSWORD',''))
                    smtp.send_message(msg)
                c.execute("UPDATE receipt_outbox SET status='sent',error='',sent_at=CURRENT_TIMESTAMP WHERE order_id=?",(oid,))
            except Exception as exc:
                # บันทึกเฉพาะประเภทข้อผิดพลาด ไม่เก็บคำตอบเซิร์ฟเวอร์ อีเมล หรือรหัสลับ
                c.execute("UPDATE receipt_outbox SET status='failed',error=? WHERE order_id=?",(type(exc).__name__,oid))
            c.commit()
    finally:c.close()

# เรียกงานคิวใบเสร็จเบื้องหลังและป้องกันการเริ่มงานซ้ำพร้อมกัน
def start_worker():
    if not _worker_lock.acquire(blocking=False):return
    # ทำงานคิวใบเสร็จในเธรดและคืนล็อกเมื่อเสร็จ เพื่อไม่ให้เริ่มซ้ำ
    def run():
        try:process_pending()
        finally:_worker_lock.release()
    threading.Thread(target=run,daemon=True).start()


# อ่านรายการสินค้าของคำสั่งซื้อหลังตรวจสิทธิ์เจ้าของบัญชี
def customer_items(uid, oid):
    c=db.conn()
    try:
        if not c.execute('SELECT id FROM orders WHERE id=? AND user_id=?',(oid,uid)).fetchone():
            raise PermissionError('Order unavailable for this account.')
        return [dict(r) for r in c.execute("SELECT i.*,COALESCE(NULLIF(i.product_name,''),p.name,'Denim') name,COALESCE(NULLIF(i.product_code,''),p.code,'') code FROM order_items i LEFT JOIN products p ON p.id=i.product_id WHERE i.order_id=?",(oid,))]
    finally:c.close()

# อ่านข้อมูลรับชำระของร้าน หรือใช้ค่าตั้งต้นเมื่อยังไม่ได้บันทึก
def payment_settings():
    c=db.conn()
    try:
        r=c.execute("SELECT value FROM shop_metadata WHERE key='payment_details'").fetchone()
        if r:return json.loads(r['value'])
        from pathlib import Path
        defaults=Path(db.BASE_DIR)/'assets'/'payments'/'default_settings.json'
        return json.loads(defaults.read_text('utf-8')) if defaults.is_file() else {}
    finally:c.close()

# ตรวจสิทธิ์แอดมินและบันทึกผู้รับเงิน ธนาคาร บัญชี และรูป QR
def save_payment_settings(actor, name, bank, account, image=None, tax_id=None):
    from support import admin_data as admin
    from pathlib import Path
    import shutil,uuid
    cfg=payment_settings()
    # เก็บ Tax ID ของร้านในหน้าแอดมิน ช่องว่างหมายถึงยังไม่ได้ระบุ
    if tax_id is not None:
        tax_id=tax_id.strip()
        if tax_id and (len(tax_id)!=13 or not tax_id.isascii() or not tax_id.isdecimal()):raise ValueError('Tax ID ต้องเป็นตัวเลข 13 หลัก / Tax ID must contain 13 digits.')
        cfg['tax_id']=tax_id
    with admin.transaction(actor) as c:
        if image:
            source=Path(image)
            if source.suffix.lower() not in ('.png','.jpg','.jpeg','.webp'):raise ValueError('Choose PNG, JPG or WebP.')
            target=Path(db.BASE_DIR)/'assets'/'payments'
            target.mkdir(parents=True,exist_ok=True)
            path=target/f'qr_{uuid.uuid4().hex}.png'
            try:
                from PIL import Image
                with Image.open(source) as picture:picture.convert('RGB').save(path,'PNG')
            except ImportError:
                if source.suffix.lower()!='.png':raise ValueError('Without Pillow, choose a PNG QR image.')
                if source.read_bytes()[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError('Invalid PNG image.')
                shutil.copy2(source,path)
            cfg['qr']=path.relative_to(db.BASE_DIR).as_posix()
            cfg.pop('qr_crop',None)
        cfg.update(name=name.strip(),bank=bank.strip(),account=account.strip())
        c.execute("INSERT INTO shop_metadata VALUES('payment_details',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(json.dumps(cfg),))
        admin.audit(c,actor,'payment_settings_saved','payment','Store payment details updated')

# ค้นหาไฟล์ QR รับเงินที่ร้านตั้งค่าไว้
def qr_path():
    from pathlib import Path
    relative=payment_settings().get('qr')
    if not relative:return None
    base=Path(db.BASE_DIR).resolve();path=(base/relative).resolve()
    return path if path.is_relative_to(base) and path.is_file() else None


# ตรวจการเชื่อมต่อของระบบอีเมลเดิมที่ไม่ได้เปิดใช้งานในหน้าจอ
def check_connection():
    if not configured():raise ValueError('Enter the App Password first.')
    cfg=config();factory=smtplib.SMTP_SSL if cfg['security']=='SSL' else smtplib.SMTP
    with factory(cfg['host'],int(cfg['port']),timeout=20,**({'context':ssl.create_default_context()} if cfg['security']=='SSL' else {})) as smtp:
        if cfg['security']=='STARTTLS':smtp.starttls(context=ssl.create_default_context())
        if cfg.get('username'):smtp.login(cfg['username'],_password or service_settings.get('JPZ_SMTP_PASSWORD',''))
    return True


"""Customer order history, payment summary and receipt windows."""
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import db
import receipt as receipts
from support import gallery

class PaymentMixin:
    # เปิดหน้ารายละเอียดคำสั่งซื้อของบัญชี
    def order_detail(self, oid, push=True):
        self.navigate('order_detail', self._order_detail, oid, push=push)

    # แสดงรายการสินค้า ข้อมูลจัดส่ง สถานะ และปุ่มที่ใช้กับคำสั่งซื้อ
    # J28 | หน้ารายละเอียดคำสั่งซื้อและรูปสินค้า
    def _order_detail(self, oid):
        order=receipts.order_for(self.user['id'],oid)
        if not order:return self.my_orders()
        b=self.scroll_content(self.shell())
        self.label(b,self.ui('หมายเลขคำสั่งซื้อ','Order number')+f' {db.order_number(order)}',28,True).pack(anchor='w',padx=35,pady=(20,8))
        self.order_badges(b,order).pack(anchor='w',padx=35,pady=5)
        self.label(b,self.ui('สินค้าในคำสั่งซื้อ','Your items'),16,True).pack(anchor='w',padx=35,pady=10)
        self._order_item_photos=[]
        for item in receipts.customer_items(self.user['id'],oid):
            row=tk.Frame(b,bg='white',highlightbackground='#DADADA',highlightthickness=1);row.pack(fill='x',padx=35,pady=5)
            picture_box=tk.Frame(row,bg='#F1F3F5',width=100,height=120);picture_box.pack(side='left',padx=12,pady=12);picture_box.pack_propagate(False)
            picture=tk.Label(picture_box,text=self.ui('กำลังโหลดรูป…','Loading photo…'),font=self.font(9),bg='#F1F3F5',fg='#5D6975',wraplength=90);picture.pack(fill='both',expand=True)
            picture._order_item=(item['product_id'],item['color']);self._order_item_photos.append(picture)
            # อ่านภาพย่อของสีที่สั่งในงานเบื้องหลัง ไม่ใช้ภาพสีอื่นแทน
            def load_picture(pid=item['product_id'],color=item['color']):
                from PIL import ImageOps
                for view in ('DETAIL','FRONT','BACK'):
                    image=gallery.preview(pid,color,view)
                    if image is not None:return ImageOps.contain(image,(100,120))
            def apply_picture(image,label=picture):
                if image is None:label.configure(text=self.ui('ยังไม่มีรูปสีนี้','No photo for this color'));return
                photo=gallery.to_photo(image,master=self);label.configure(image=photo,text='');label._image=photo
            from support import image_jobs
            image_jobs.submit(self,picture,load_picture,apply_picture)
            info=tk.Frame(row,bg='white');info.pack(side='left',fill='x',expand=True)
            self.label(info,f"{item['name']}\n{item['code']} / {self.color_label(item['color'])} / {db.size_label(item['size'])}    × {item['quantity']}    ฿{item['price']*item['quantity']:,.2f}",11,True,justify='left').pack(anchor='w',padx=15,pady=(15,0))
            self.price_before_vat(info,item['price']*item['quantity'],padx=15)
            product=db.product(item['product_id'])
            if product:self.button(row,self.tr('view_product'),lambda p=product:self.product_detail(p),compact=True).pack(side='right',padx=10)
        self.label(b,self.ui('การจัดส่ง','Delivery'),16,True).pack(anchor='w',padx=35,pady=(20,8))
        text=f"{order['customer_name']}\n{order['phone']}\n{order['address']} {order.get('postal_code','')}"
        text+='\n'+self.ui('เลขติดตาม: ','Tracking: ')+(order['tracking'] or self.ui('ยังไม่มีเลขติดตาม','Not assigned yet'))
        self.label(b,text,11,justify='left',wraplength=750).pack(anchor='w',padx=35,pady=8)
        self.label(b,f"{self.ui('ยอดชำระ','Total')} ฿{order['total']:,.2f}",18,True).pack(anchor='w',padx=35,pady=15)
        self.price_before_vat(b,order['total'],padx=35)
        if order['payment_status']=='paid':
            self.button(b,self.ui('เปิดใบเสร็จรับเงิน','View receipt'),lambda:self.receipt_window(oid),dark=True).pack(anchor='w',padx=35,pady=8)
        elif order['payment_status'] in ('waiting_payment','rejected','under_review') and order['order_status']=='waiting_payment':
            self.button(b,self.ui('ชำระเงิน / ดูสรุปยอด','Pay / view summary'),lambda:self.receipt_window(oid),dark=True).pack(anchor='w',padx=35,pady=8)
        from support import returns
        if order['payment_status']=='paid' or returns.for_customer(self.user['id'],oid):
            self.button(b,self.ui('ขอคืนสินค้า / ดูคำขอ','Request / view return'),lambda:self.return_form(oid)).pack(anchor='w',padx=35,pady=8)
        self.button(b,self.ui('รีเฟรชสถานะ','Refresh status'),lambda:self._order_detail(oid)).pack(anchor='w',padx=35,pady=(5,20))
        if order['payment_status'] in ('waiting_payment','under_review','rejected') and order['order_status']=='waiting_payment':
            def cancel():
                if not messagebox.askyesno('JPZ',self.ui('ยืนยันยกเลิกคำสั่งซื้อ?','Cancel this order?')):return
                try:db.cancel_customer_order(self.user['id'],oid);self.order_detail(oid,push=False)
                except ValueError as exc:messagebox.showerror('JPZ',str(exc))
            self.button(b,self.ui('ยกเลิกคำสั่งซื้อ','Cancel order'),cancel).pack(anchor='w',padx=35,pady=10)

    # เปิดหน้าต่างชำระเงินหรือใบเสร็จ โดยแยกตามสถานะยืนยันรับเงิน
    # J30 | หน้าต่างใบเสร็จ
    def receipt_window(self, oid):
        order=receipts.order_for(self.user['id'],oid)
        if not order:return
        previous=getattr(self,'_receipt_ui',{})
        if previous.get('window') is not None:
            try:
                if previous['window'].winfo_exists():previous['close']()
            except tk.TclError:pass
        paid=order['payment_status']=='paid'
        # Capture only the shop window once. No animation or continuous screen capture.
        backdrop=tk.Toplevel(self);backdrop.withdraw();backdrop.overrideredirect(True)
        backdrop.configure(bg='#243440');backdrop.transient(self)
        bx,by=self.winfo_rootx(),self.winfo_rooty();bw,bh=self.winfo_width(),self.winfo_height()
        backdrop.geometry(f'{bw}x{bh}+{bx}+{by}')
        try:
            from PIL import ImageGrab,ImageFilter,Image
            shot=ImageGrab.grab(window=int(self.frame(),16))
            shot=shot.resize((max(1,bw//4),max(1,bh//4))).filter(ImageFilter.GaussianBlur(3))
            shot=Image.blend(shot.convert('RGB'),Image.new('RGB',shot.size,'#243440'),.22).resize((bw,bh))
            photo=gallery.to_photo(shot,master=backdrop)
            background=tk.Label(backdrop,image=photo,bd=0);background._image=photo;background.pack(fill='both',expand=True)
        except (ImportError,OSError,ValueError,tk.TclError):pass
        backdrop.deiconify()
        win=tk.Toplevel(backdrop);win.withdraw();win.transient(backdrop)
        win.title('JPZ / '+self.ui('ใบเสร็จรับเงิน','Receipt') if paid else 'JPZ / PAYMENT')
        screen_w,screen_h=self.winfo_screenwidth(),self.winfo_screenheight()
        width=min(1280,max(640,screen_w-70));height=min(800,max(480,screen_h-60))
        win.geometry(f'{width}x{height}+{max(0,(screen_w-width)//2)}+{max(0,(screen_h-height)//2-20)}')
        win.minsize(min(800,width),min(540,height));win.configure(bg='#F8F6F1')
        def close():
            try:win.grab_release();backdrop.destroy()
            except tk.TclError:pass
            self.focus_set()
        win.protocol('WM_DELETE_WINDOW',close);win.bind('<Escape>',lambda e:close())
        header=tk.Frame(win,bg='#243E55');header.pack(fill='x')
        self.label(header,'JPZ.',23 if height<720 else 27,True,fg='white',bg='#243E55').pack(side='left',padx=22,pady=8 if height<720 else 12)
        heading=self.ui('ใบเสร็จรับเงิน','PAYMENT RECEIPT') if paid else self.ui('ใบรอชำระเงิน','PAYMENT SUMMARY')
        self.label(header,heading,17 if height<720 else 19,True,fg='white',bg='#243E55').pack(side='left',padx=10)
        self.label(header,self.ui('ชำระเงินแล้ว','PAID') if paid else self.status_label(order['payment_status']),11,True,fg='#F0D9A6',bg='#243E55').pack(side='right',padx=22)
        actions=tk.Frame(win,bg='#F8F6F1');actions.pack(side='bottom',fill='x',padx=20,pady=10)
        self.button(actions,self.ui('ปิด','Close'),close).pack(side='right')
        body=tk.Frame(win,bg='#F8F6F1');body.pack(fill='both',expand=True,padx=18,pady=(8,0))
        body.columnconfigure(0,weight=1,uniform='sheet');body.columnconfigure(1,weight=1,uniform='sheet');body.rowconfigure(0,weight=1)
        def scroll_panel(column):
            holder=tk.Frame(body,bg='white',highlightthickness=1,highlightbackground='#DED9CD');holder.grid(row=0,column=column,sticky='nsew',padx=(0,7) if column==0 else (7,0))
            canvas=tk.Canvas(holder,bg='white',highlightthickness=0,yscrollincrement=24)
            bar=ttk.Scrollbar(holder,orient='vertical',command=canvas.yview)
            def position(a,b):
                bar.set(a,b)
                if float(b)-float(a)<.999:bar.pack(side='right',fill='y')
                else:bar.pack_forget()
            canvas.configure(yscrollcommand=position)
            canvas.pack(side='left',fill='both',expand=True)
            paper=tk.Frame(canvas,bg='white');item=canvas.create_window((0,0),window=paper,anchor='nw')
            paper.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
            canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width))
            return paper,canvas,bar
        left,left_canvas,left_bar=scroll_panel(0);right,right_canvas,right_bar=scroll_panel(1)
        self.label(left,db.order_number(order),12,True,wraplength=520,justify='left').pack(anchor='w',padx=20,pady=(15,3))
        self.label(left,receipts.local_time(order['created_at'])+self.ui(' (เวลาไทย)',' (Thailand time)'),10,fg='#777777').pack(anchor='w',padx=20)
        customer=self.label(left,f"{order['customer_name']}  ·  {order['phone']}\n{order['address']}  {order.get('postal_code','')}",11,justify='left',anchor='w',wraplength=520)
        customer.pack(fill='x',padx=20,pady=12)
        left.bind('<Configure>',lambda e:customer.configure(wraplength=max(160,e.width-40)),add='+')
        self.label(left,self.ui('รายการสินค้า','Order items'),13,True).pack(anchor='w',padx=20,pady=(0,5))
        from support import order_amounts
        products=order_amounts.lines(receipts.customer_items(self.user['id'],oid),order['total'])
        for product in products:
            line=tk.Frame(left,bg='#F4F4F4');line.pack(fill='x',padx=16,pady=3)
            text=self.label(line,f"{product['name']}\n{self.color_label(product['color'])} / {db.size_label(product['size'])} / × {product['quantity']}",11,True,justify='left',bg='#F4F4F4',wraplength=340)
            text.pack(anchor='w',padx=12,pady=(8,3))
            line.bind('<Configure>',lambda e,label=text:label.configure(wraplength=max(100,e.width-24)))
            self.label(line,f"฿{product['net_total']:,.2f}",12,True,bg='#F4F4F4',fg='#8C2635').pack(anchor='e',padx=12,pady=(0,8))
            if product['net_total']<product['original_total']:
                self.label(line,self.ui('ก่อนส่วนลด ','Before discount ')+f"฿{product['original_total']:,.2f}",9,bg='#F4F4F4',fg='#777777').pack(anchor='e',padx=12,pady=(0,6))
        self.label(right,self.ui('สรุปยอดชำระ','Payment total'),16,True).pack(anchor='w',padx=20,pady=(8,6))
        tax=db.vat_breakdown(order['total']);amount_labels=[]
        for caption,value,total in [(self.ui('ยอดก่อน VAT','Before VAT'),tax['before_vat'],False),('VAT 7%',tax['vat'],False),(self.ui('ยอดชำระแล้ว','Paid total') if paid else self.ui('ยอดที่ต้องชำระ','Amount to pay'),tax['total'],True)]:
            row=tk.Frame(right,bg='#F8F6F1' if total else 'white');row.pack(fill='x',padx=16,pady=3)
            self.label(row,caption,14 if total else 11,total,bg=row.cget('bg')).pack(side='left',padx=8,pady=5)
            label=self.label(row,f'฿{value:,.2f}',17 if total else 12,True,bg=row.cget('bg'));label.pack(side='right',padx=8,pady=5);amount_labels.append(label)
        self.label(right,self.ui('ยอดก่อน VAT หักส่วนลดแล้ว · VAT รวมในยอดชำระ','Before VAT is after discounts. Total includes VAT.'),9,fg='#777777',wraplength=520).pack(padx=16,pady=5)
        qr_size=130 if height<720 else 190
        if paid:
            self.label(right,self.ui('ขอบคุณที่เลือกซื้อสินค้าจาก JPZ','Thank you for shopping with JPZ'),12,True).pack(pady=18)
            self.button(actions,self.ui('บันทึกใบเสร็จ PDF','Save receipt PDF'),lambda:self.save_receipt(oid),dark=True).pack(side='left')
            info=receipts.delivery(oid)
            text=self.ui('ส่งใบเสร็จทางอีเมลแล้ว','Receipt emailed') if info and info['status']=='sent' else self.ui('เปิดอ่านใบเสร็จในหน้านี้ได้ทันที และบันทึก PDF ได้ตามต้องการ','Read your receipt here, or save a PDF when needed.')
            self.label(right,text,10,fg='#777777',wraplength=480,justify='center').pack(padx=20,pady=8)
            if order.get('paid_at'):self.label(right,self.ui('ยืนยันรับชำระ: ','Payment confirmed: ')+receipts.local_time(order['paid_at']),10,fg='#26734D').pack(pady=5)
            self.label(right,self.ui('เอกสารยืนยันการรับชำระเงิน ไม่ใช่ใบกำกับภาษี','Payment confirmation; not a tax invoice.'),9,fg='#777777',wraplength=480).pack(padx=20,pady=5)
            self.email_delivery_notice(right).pack_configure(padx=20)
        elif order['order_status']=='waiting_payment':
            cfg=receipts.payment_settings();path=receipts.qr_path()
            if path:
                try:
                    if gallery.Image is not None:
                        with gallery.Image.open(path) as picture:image=picture.convert('RGB').copy()
                        crop=cfg.get('qr_crop')
                        if isinstance(crop,list) and len(crop)==4 and 0<=crop[0]<crop[2]<=image.width and 0<=crop[1]<crop[3]<=image.height:image=image.crop(tuple(crop))
                        image.thumbnail((qr_size,qr_size));photo=gallery.to_photo(image,master=win)
                    else:
                        image=gallery.NativeImage(tk.PhotoImage(file=str(path),master=win));image.thumbnail((qr_size,qr_size));photo=image.photo
                    label=tk.Label(right,image=photo,bg='white');label._image=photo;label.pack(pady=4)
                except (OSError,tk.TclError):self.label(right,self.ui('ไม่สามารถอ่าน QR ได้ กรุณาติดต่อร้าน','Unable to read QR. Contact the store.'),10).pack(pady=8)
            else:self.label(right,self.ui('ร้านยังไม่ได้ตั้งค่า QR รับชำระ','Store payment QR has not been configured.'),10,fg='#777777').pack(pady=12)
            bank_info=' · '.join(str(cfg.get(key,'')) for key in ('name','bank') if cfg.get(key))
            if cfg.get('account'):bank_info+='\n'+str(cfg['account'])
            if bank_info:self.label(right,bank_info,10,True,justify='center',wraplength=500).pack(pady=2)
            self.label(right,self.ui('ตรวจชื่อผู้รับและยอดเงินก่อนโอน แล้วแนบหลักฐานชำระเงิน','Check recipient and amount before transferring, then attach payment proof.'),9,fg='#777777',wraplength=500,justify='center').pack(padx=16,pady=4)
            def upload():close();self.upload(order)
            self.button(actions,self.tr('upload_receipt'),upload,dark=True).pack(side='left')
        def wheel(event):
            widget=event.widget;target=left_canvas
            while widget is not None:
                if widget is right_canvas:target=right_canvas;break
                widget=getattr(widget,'master',None)
            target.yview_scroll(int(-event.delta/120),'units');return 'break'
        win.bind('<MouseWheel>',wheel)
        self._receipt_ui=dict(window=win,backdrop=backdrop,close=close,left=left,right=right,canvases=(left_canvas,right_canvas),actions=actions,paid=paid,amount_labels=amount_labels,items=products)
        win.deiconify();win.lift();win.grab_set();win.focus_set()
