"""Store genuine JPEG, PNG and WebP slip images in a single PNG format."""
from pathlib import Path
import uuid
from PIL import Image,ImageOps,UnidentifiedImageError
import db

def save(uid,oid,source):
    # Check ownership and payment state before opening or writing an image.
    c=db.conn()
    try:order=c.execute('SELECT user_id,payment_status,order_status FROM orders WHERE id=?',(oid,)).fetchone()
    finally:c.close()
    if not order or order['user_id']!=uid:raise PermissionError('ไม่สามารถส่งสลิปของบัญชีอื่น / This order belongs to another account.')
    if order['payment_status'] not in ('waiting_payment','rejected','under_review') or order['order_status']!='waiting_payment':raise ValueError('คำสั่งซื้อไม่สามารถรับสลิปใหม่ / This order cannot accept a new slip.')
    try:
        with Image.open(source) as check:
            if check.format not in ('JPEG','PNG','WEBP'):raise ValueError('เลือกรูป JPG/JPEG, PNG หรือ WebP / Choose JPEG, PNG or WebP.')
            check.verify()
        with Image.open(source) as image:picture=ImageOps.exif_transpose(image).convert('RGB').copy()
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError):raise ValueError('ไฟล์ภาพเสียหรือไม่ใช่รูปภาพ กรุณาเลือก JPG/JPEG หรือ PNG / Invalid image. Choose a valid JPEG or PNG file.') from None
    folder=Path(db.BASE_DIR)/'payment_uploads';folder.mkdir(exist_ok=True)
    target=folder/f'order_{oid}_{uuid.uuid4().hex}.png'
    try:
        picture.save(target,'PNG');db.add_payment(oid,target.relative_to(db.BASE_DIR).as_posix(),uid)
    except Exception:
        target.unlink(missing_ok=True);raise
    return target
