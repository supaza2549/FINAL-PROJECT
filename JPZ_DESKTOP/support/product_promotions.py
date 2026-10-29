"""Admin-selected product offers; order pricing chooses the better offer without stacking."""
from decimal import Decimal,ROUND_HALF_UP
import math
from contextlib import nullcontext
import db
from support import admin_data,loyalty

def money(value):return Decimal(str(value)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)

def migrate(c):
    c.execute("CREATE TABLE IF NOT EXISTS product_promotions(product_id INTEGER PRIMARY KEY,kind TEXT NOT NULL,value REAL NOT NULL,enabled INTEGER NOT NULL DEFAULT 1)")
    db.add_column_if_missing(c,'orders','discount_kind',"TEXT DEFAULT 'daily'")

def setting(pid,c=None):
    if c is None:
        connection=db.conn()
        try:return setting(pid,connection)
        finally:connection.close()
    row=c.execute('SELECT * FROM product_promotions WHERE product_id=?',(pid,)).fetchone()
    return dict(row) if row else dict(product_id=pid,kind='percent',value=0,enabled=0)

def save(actor,pid,kind,value,enabled,connection=None):
    value=float(value)
    if kind not in ('percent','price') or not math.isfinite(value) or value<0:raise ValueError('กรอกโปรโมชั่นให้ถูกต้อง / Enter a valid promotion.')
    if kind=='percent' and value>100:raise ValueError('เปอร์เซ็นต์ต้องไม่เกิน 100 / Percentage must be 0–100.')
    with (nullcontext(connection) if connection is not None else admin_data.transaction(actor)) as c:
        admin_data.require_admin(c,actor)
        product=c.execute('SELECT price FROM products WHERE id=?',(pid,)).fetchone()
        if not product:raise ValueError('ไม่พบสินค้า / Product not found.')
        if kind=='price' and value>product['price']:raise ValueError('ราคาพิเศษต้องไม่สูงกว่าราคาปกติ / Special price cannot exceed the regular price.')
        c.execute('INSERT INTO product_promotions VALUES(?,?,?,?) ON CONFLICT(product_id) DO UPDATE SET kind=excluded.kind,value=excluded.value,enabled=excluded.enabled',(pid,kind,float(money(value)),int(bool(enabled))))
        admin_data.audit(c,actor,'product_promotion_saved',pid,f'{kind}: {value:g}, enabled={bool(enabled)}')

def sale_price(product,size,c):
    regular=money(db.price_for_size(product,size,c));offer=setting(product['id'],c)
    if not offer['enabled']:return regular
    if offer['kind']=='percent':return money(regular*(Decimal(100)-Decimal(str(offer['value'])))/100)
    # A special base price keeps the separately configured size surcharge.
    return min(regular,money(Decimal(str(offer['value']))+regular-money(product['price'])))

def cart_quote(cart,uid,c=None):
    if c is None:
        connection=db.conn()
        try:
            connection.execute('BEGIN IMMEDIATE');result=cart_quote(cart,uid,connection);connection.commit();return result
        except Exception:connection.rollback();raise
        finally:connection.close()
    subtotal=Decimal(0);saving=Decimal(0)
    for (pid,color,size),qty in cart.items():
        product=c.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
        if not product:raise ValueError('ไม่พบสินค้าในตะกร้า / Cart product unavailable.')
        product=dict(product);regular=money(db.price_for_size(product,size,c));subtotal+=regular*qty
        saving+=(regular-sale_price(product,size,c))*qty
    result=loyalty.redeem_quote(subtotal,uid,0,c)
    result['product_discount']=float(saving);result['daily_discount']=result['discount_amount']
    result['discount_kind']='daily' if result['discount_amount'] else 'none'
    if saving>money(result['discount_amount']):
        result.update(discount_amount=float(saving),total=float(subtotal-saving),promo_percent=0,promo_day='',promo_minimum=0,promo_cap=0,discount_kind='product')
    return result

def label(kind,lang='TH'):
    return ('โปรโมชั่นรายสินค้า' if lang=='TH' else 'Product promotion') if kind=='product' else ('ส่วนลดรายวัน' if lang=='TH' else 'Daily discount')
