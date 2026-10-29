"""EasySlip v2 adapter for the trusted shop/admin machine; fail closed until configured."""
import os,json,base64,hashlib,re,sqlite3
from pathlib import Path
from decimal import Decimal
from datetime import datetime,timezone,timedelta
from urllib.request import Request,urlopen
from urllib.error import URLError
import db
from support import service_settings
from support import admin_data

def migrate(c):
    c.execute('CREATE TABLE IF NOT EXISTS verified_slips(trans_ref TEXT PRIMARY KEY,order_id INTEGER NOT NULL,payment_id INTEGER NOT NULL,image_hash TEXT NOT NULL,amount REAL NOT NULL,bank_number TEXT NOT NULL,transfer_at TEXT NOT NULL,verified_at TEXT DEFAULT CURRENT_TIMESTAMP)')

def configured():return bool(service_settings.get('JPZ_EASYSLIP_API_KEY') and service_settings.get('JPZ_EASYSLIP_BANK_NUMBER'))

def digits(value):return re.sub(r'[^0-9]','',str(value))

def request_verification(image,total):
    key=service_settings.get('JPZ_EASYSLIP_API_KEY','')
    if not configured():raise ValueError('ยังไม่ได้เชื่อม EasySlip: ตั้ง API key และเลขบัญชีร้านบนเครื่องแอดมิน / Configure EasySlip API key and the store bank account on the admin machine.')
    request=Request('https://api.easyslip.com/v2/verify/bank',data=json.dumps(dict(base64='data:image/png;base64,'+base64.b64encode(image).decode('ascii'),matchAccount=True,matchAmount=float(total),checkDuplicate=True)).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    try:
        with urlopen(request,timeout=30) as response:return json.loads(response.read(1024*1024))
    except (URLError,TimeoutError,ValueError):raise ValueError('ตรวจสลิปไม่ได้ กรุณาลองใหม่ ยังไม่ยืนยันชำระ / Slip service unavailable; payment remains unapproved.') from None

def check_result(result,order):
    if not isinstance(result,dict):raise ValueError('ข้อมูลตรวจสลิปไม่ถูกต้อง / Invalid slip service response.')
    data=result.get('data',{}) if isinstance(result,dict) else {}
    if result.get('success') is not True or data.get('isDuplicate') is not False:raise ValueError('สลิปไม่ผ่านหรือเคยถูกใช้แล้ว / Invalid or duplicate slip.')
    matched=data.get('matchedAccount') or {};account=digits(matched.get('bankNumber',''))
    expected=digits(service_settings.get('JPZ_EASYSLIP_BANK_NUMBER',''))
    if not expected or account!=expected:raise ValueError('บัญชีผู้รับไม่ตรงกับร้าน / Receiver account does not match the store.')
    raw=data.get('rawSlip') or {};ref=str(raw.get('transRef','')).strip()
    try:
        amount=Decimal(str(data['amountInSlip']));raw_amount=Decimal(str(raw['amount']['amount']))
        transfer=datetime.fromisoformat(raw['date']);created=datetime.fromisoformat(order['created_at']).replace(tzinfo=timezone.utc)
    except (KeyError,ValueError,TypeError):raise ValueError('ข้อมูลสลิปไม่ครบ / Incomplete verified slip data.') from None
    if not amount.is_finite() or amount!=Decimal(str(order['total'])) or raw_amount!=amount or data.get('isAmountMatched') is not True:raise ValueError('ยอดโอนไม่ตรงกับคำสั่งซื้อ / Transfer amount does not match the order.')
    currency=(raw.get('amount',{}).get('local') or {}).get('currency')
    if currency!='THB' or not ref or len(ref)>128:raise ValueError('เลขอ้างอิงหรือสกุลเงินไม่ถูกต้อง / Invalid transaction reference or currency.')
    if transfer.tzinfo is None or transfer<created-timedelta(minutes=5) or transfer>datetime.now(timezone.utc)+timedelta(minutes=5):raise ValueError('วันเวลาโอนไม่ตรงกับคำสั่งซื้อ / Transfer time does not match this order.')
    return dict(trans_ref=ref,amount=float(amount),bank_number=account,transfer_at=raw['date'])

def verify_and_approve(actor,oid):
    import receipt
    # This callable is for an authenticated administrator, never a customer's client.
    rows=admin_data.query(actor,'SELECT * FROM orders WHERE id=?',(oid,))
    if not rows:raise ValueError('Order not found.')
    order=rows[0]
    if order['payment_status']!='under_review' or order['order_status']!='waiting_payment':raise ValueError('คำสั่งซื้อไม่อยู่ระหว่างตรวจชำระ / Order is not awaiting payment review.')
    payment=db.latest_payment(oid)
    if not payment:raise ValueError('No uploaded slip.')
    base=Path(db.BASE_DIR).resolve();path=Path(payment['receipt_path'])
    path=(base/path).resolve() if not path.is_absolute() else path.resolve()
    if not path.is_relative_to(base) or not path.is_file():raise ValueError('ไม่พบไฟล์สลิปในร้าน / Slip file unavailable.')
    from PIL import Image
    import io
    with Image.open(path) as source:
        image=source.convert('RGB');stream=io.BytesIO();image.save(stream,'PNG');content=stream.getvalue()
    if len(content)>4*1024*1024:raise ValueError('สลิปใหญ่เกิน 4 MB / Slip exceeds 4 MB.')
    image_hash=hashlib.sha256(content).hexdigest()
    cached=admin_data.query(actor,'SELECT * FROM verified_slips WHERE order_id=? AND payment_id=?',(oid,payment['id']))
    valid=cached[0] if cached and cached[0]['image_hash']==image_hash and cached[0]['bank_number']==digits(service_settings.get('JPZ_EASYSLIP_BANK_NUMBER','')) and Decimal(str(cached[0]['amount']))==Decimal(str(order['total'])) else None
    if not valid:
        valid=check_result(request_verification(content,order['total']),order)
        with admin_data.transaction(actor) as c:
            current=c.execute('SELECT payment_status,total FROM orders WHERE id=?',(oid,)).fetchone()
            latest=c.execute('SELECT id FROM payments WHERE order_id=? ORDER BY id DESC LIMIT 1',(oid,)).fetchone()
            if current['payment_status']!='under_review' or current['total']!=order['total'] or latest['id']!=payment['id']:raise ValueError('คำสั่งซื้อหรือสลิปเปลี่ยนแล้ว กรุณาตรวจใหม่ / Order or slip changed; verify again.')
            try:
                c.execute('INSERT INTO verified_slips(trans_ref,order_id,payment_id,image_hash,amount,bank_number,transfer_at) VALUES(?,?,?,?,?,?,?)',(valid['trans_ref'],oid,payment['id'],image_hash,valid['amount'],valid['bank_number'],valid['transfer_at']))
            except sqlite3.IntegrityError:raise ValueError('เลขอ้างอิงนี้ถูกผูกกับคำสั่งซื้อแล้ว / Transaction reference is already assigned.') from None
            admin_data.audit(c,actor,'slip_verified',oid,valid['trans_ref'])
    admin_data.change_order(actor,oid,'approve',verified_payment=payment['id'])
    receipt.start_worker()
    return valid['trans_ref']
