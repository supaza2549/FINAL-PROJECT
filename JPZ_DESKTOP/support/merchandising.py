"""รูปและสินค้าที่แอดมินเลือกโปรโมตบนหน้าแรก รวมอันดับขายจากยอดชำระจริง"""
import json
from pathlib import Path
from PIL import Image
import db
from support import admin_data, gallery

def settings():
    c=db.conn()
    try:
        row=c.execute("SELECT value FROM shop_metadata WHERE key='home_promotion'").fetchone()
        return json.loads(row['value']) if row else {'product_id':None,'photo':''}
    finally:c.close()

# รับเฉพาะรูปภายในโฟลเดอร์โปรแกรม และตรวจสินค้าที่ยังขายอยู่ก่อนบันทึก

def save(actor,product_id,photo=''):
    with admin_data.transaction(actor) as c:
        if product_id is not None and not c.execute('SELECT id FROM products WHERE id=? AND active=1',(product_id,)).fetchone():
            raise ValueError('สินค้านี้ไม่ได้เปิดขาย / Product is unavailable.')
        if photo:
            path=Path(photo)
            if path.is_absolute() or not (db.BASE_DIR/path).resolve().is_relative_to(db.BASE_DIR.resolve()) or not (db.BASE_DIR/path).is_file():
                raise ValueError('ไม่พบรูปโปรโมต / Promotion image is unavailable.')
        value={'product_id':product_id,'photo':photo}
        c.execute("INSERT INTO shop_metadata VALUES('home_promotion',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(json.dumps(value),))
        admin_data.audit(c,actor,'home_promotion_updated',product_id or '',photo)
    return value

# ใช้รูปที่แอดมินอัปโหลดก่อน ถ้าไม่มีให้ใช้รูปสินค้าที่เลือก หรือภาพคอลเลกชันเดิม

def picture(config):
    photo=config.get('photo','')
    if photo:
        path=(db.BASE_DIR/photo).resolve()
        if path.is_relative_to(db.BASE_DIR.resolve()) and path.is_file():
            with Image.open(path) as image:return image.convert('RGB')
    product=db.product(config.get('product_id')) if config.get('product_id') else None
    if product and product.get('active',1):
        source=gallery.source(product['id'],product['color'],'FRONT')
        if source is not None:return source.copy()
    with Image.open(db.BASE_DIR/'assets/home_new_panel.png') as image:return image.convert('RGB')

# รวมยอดเป็นรุ่นเดียวแม้ซื้อคนละสี/ไซซ์ ไม่นับออเดอร์ยกเลิกหรือคืนเงิน
# ถ้าจำนวนขายเท่ากันใช้รหัสสินค้าเป็นตัวตัดสินเพื่อให้ลำดับคงที่

def best_sellers():
    c=db.conn()
    try:
        rows=c.execute("""SELECT i.product_id,SUM(i.quantity) AS quantity
            FROM order_items i JOIN orders o ON o.id=i.order_id
            JOIN products p ON p.id=i.product_id
            WHERE o.payment_status='paid' AND o.order_status NOT IN ('cancelled','refunded') AND p.active=1
            GROUP BY i.product_id HAVING SUM(i.quantity)>0
            ORDER BY quantity DESC,i.product_id ASC LIMIT 5""").fetchall()
        return {row['product_id']:index+1 for index,row in enumerate(rows)}
    finally:c.close()
