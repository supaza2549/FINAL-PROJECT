# ชั้นจัดเก็บข้อมูลของโปรแกรม ใช้ SQLite ในไฟล์ find_your_fit.db
# เก็บบัญชี สินค้า สี ไซซ์ สต็อก คำสั่งซื้อ ที่อยู่ และหลักฐานชำระเงิน
# หน้าจอเรียกฟังก์ชันในไฟล์นี้เพื่ออ่านหรือบันทึกข้อมูล แทนการเก็บไว้เฉพาะในหน้าต่าง

import sqlite3
import hashlib
import secrets
import hmac
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB = BASE_DIR / 'find_your_fit.db'

# เปิดการเชื่อมต่อ SQLite และตั้งให้ผลลัพธ์อ่านได้ด้วยชื่อคอลัมน์
def conn():
    c = sqlite3.connect(str(DB))
    c.row_factory = sqlite3.Row
    return c

# สร้างค่ารหัสผ่านที่เข้ารหัสแบบ PBKDF2 พร้อม salt สุ่ม ไม่เก็บรหัสผ่านตรง ๆ
def hash_password(password):
    salt = secrets.token_hex(16)
    ph = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 120000).hex()
    return f'{salt}${ph}'

# คำนวณและเปรียบเทียบรหัสผ่านกับค่าที่เก็บอย่างปลอดภัย
def check_password(password, stored):
    try:
        salt, old = stored.split('$', 1)
    except ValueError:
        return False
    new = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 120000).hex()
    return hmac.compare_digest(new, old)

# อ่านรายชื่อคอลัมน์ของตารางใน SQLite
def column_names(connection, table_name):
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


# เพิ่มคอลัมน์เมื่อฐานข้อมูลเดิมยังไม่มี โดยเก็บข้อมูลเดิมไว้
def add_column_if_missing(connection, table_name, column_name, definition):
    existing_columns = column_names(connection, table_name)
    if column_name not in existing_columns:
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
        )


# ปรับโครงสร้างฐานข้อมูลเดิมให้รองรับโปรแกรมรุ่นปัจจุบัน
def migrate_database(connection):
    """Upgrade an older FIND YOUR FIT database without deleting user data."""
    add_column_if_missing(connection, "products", "style", "TEXT DEFAULT 'clean'")
    add_column_if_missing(connection, "orders", "stock_deducted", "INTEGER DEFAULT 0")
    add_column_if_missing(connection, "order_items", "color", "TEXT DEFAULT 'dark_indigo'")
    add_column_if_missing(connection, "order_items", "size", "INTEGER DEFAULT 32")
    add_column_if_missing(connection, "order_items", "product_name", "TEXT DEFAULT ''")
    add_column_if_missing(connection, "order_items", "product_code", "TEXT DEFAULT ''")
    connection.execute("UPDATE order_items SET product_name=COALESCE((SELECT name FROM products WHERE id=product_id),'') WHERE product_name=''")
    connection.execute("UPDATE order_items SET product_code=COALESCE((SELECT code FROM products WHERE id=product_id),'') WHERE product_code=''")
    from support import admin_data, loyalty
    admin_data.migrate(connection)
    loyalty.migrate(connection)
    from support import product_promotions
    product_promotions.migrate(connection)
    from support import sizing
    migrate_customer_details(connection)
    sizing.migrate(connection)
    migrate_order_numbers(connection)
    from support import product_colors
    product_colors.migrate(connection)


# หมายเลขสาธารณะใช้วันเวลาไทยและรหัสภายในเพื่อไม่ซ้ำกัน
# รหัสภายในยังใช้เชื่อมรายการสินค้าและหลักฐานเดิมตามปกติ
def order_number(order):
    if order.get('order_number'):return order['order_number']
    value=str(order.get('created_at') or '')
    try:
        stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
        if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=timezone.utc)
        stamp=stamp.astimezone(timezone(timedelta(hours=7))).strftime('%Y%m%d%H%M%S')
    except ValueError:stamp='00000000000000'
    return f"JPZ{stamp}{int(order['id']):06d}"

# เติมหมายเลขให้คำสั่งซื้อเดิมครั้งเดียว และเก็บลำดับร้านที่ไม่เปลี่ยนตามตัวกรอง
def migrate_order_numbers(c):
    add_column_if_missing(c,'orders','order_number',"TEXT DEFAULT ''")
    add_column_if_missing(c,'orders','order_sequence','INTEGER')
    sequence=c.execute('SELECT COALESCE(MAX(order_sequence),0) FROM orders').fetchone()[0]
    for row in c.execute('SELECT * FROM orders ORDER BY id').fetchall():
        row=dict(row)
        if row['order_number'] and row['order_sequence']:continue
        if not row['order_sequence']:sequence+=1;row['order_sequence']=sequence
        c.execute('UPDATE orders SET order_number=?,order_sequence=? WHERE id=?',
                  (order_number(row),row['order_sequence'],row['id']))
    c.execute('CREATE UNIQUE INDEX IF NOT EXISTS orders_public_number ON orders(order_number)')
    c.execute('CREATE UNIQUE INDEX IF NOT EXISTS orders_sequence_number ON orders(order_sequence)')

# สร้างตารางที่จำเป็นและเรียกปรับโครงสร้างฐานข้อมูล
def create_database():
    c = conn()
    q = c.cursor()
    q.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,first_name TEXT,last_name TEXT,email TEXT UNIQUE,password_hash TEXT,role TEXT DEFAULT 'customer',language TEXT DEFAULT 'TH',created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    q.execute('CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,code TEXT UNIQUE,price REAL,fit TEXT,style TEXT,color TEXT,waist REAL,hip REAL,thigh REAL,rise REAL,inseam REAL,leg_opening REAL,stock INTEGER DEFAULT 0)')
    q.execute('CREATE TABLE IF NOT EXISTS variants(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,color TEXT,size INTEGER,stock INTEGER DEFAULT 0,UNIQUE(product_id,color,size))')
    q.execute("CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,customer_name TEXT,phone TEXT,address TEXT,total REAL,payment_status TEXT DEFAULT 'waiting_payment',order_status TEXT DEFAULT 'waiting_payment',stock_deducted INTEGER DEFAULT 0,created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    q.execute('CREATE TABLE IF NOT EXISTS order_items(id INTEGER PRIMARY KEY AUTOINCREMENT,order_id INTEGER,product_id INTEGER,color TEXT,size INTEGER,quantity INTEGER,price REAL)')
    q.execute('CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY AUTOINCREMENT,order_id INTEGER,receipt_path TEXT,uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP)')
    q.execute('CREATE TABLE IF NOT EXISTS favorites(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,product_id INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(user_id,product_id))')
    q.execute('CREATE TABLE IF NOT EXISTS recently_viewed(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,product_id INTEGER,viewed_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(user_id,product_id))')
    q.execute('CREATE TABLE IF NOT EXISTS fit_history(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,height REAL,waist REAL,hip REAL,thigh REAL,preferred_fit TEXT,result_product_ids TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP)')

    # Upgrade older database files before inserting V2 product data.
    migrate_database(c)
    if q.execute("SELECT value FROM shop_metadata WHERE key='bootstrap_completed'").fetchone() or (
            q.execute('SELECT COUNT(*) FROM users').fetchone()[0] > 0 and
            q.execute('SELECT COUNT(*) FROM products').fetchone()[0] > 0):
        q.execute("INSERT OR IGNORE INTO shop_metadata VALUES('bootstrap_completed','1')")
        c.commit()
        c.close()
        return
    users = [('Demo', 'Customer', 'demo@findyourfit.local', 'demo1234', 'customer'), ('Admin', 'Account', 'admin@findyourfit.local', 'admin1234', 'admin')]
    for fn, ln, em, pw, role in users:
        if not q.execute('SELECT id FROM users WHERE email=?', (em,)).fetchone():
            q.execute('INSERT INTO users(first_name,last_name,email,password_hash,role,language) VALUES(?,?,?,?,?,?)', (fn, ln, em, hash_password(pw), role, 'TH'))
    seed = [('VOID BAGGY 01', 'VBG-01', 1290, 'baggy', 'clean', 'dark_indigo', 32, 42, 26, 12.5, 32, 19), ('RIPPED BAGGY 02', 'RBG-02', 1490, 'baggy', 'ripped', 'washed_blue', 32, 43, 26.5, 12.5, 32, 20), ('RAW STRAIGHT 03', 'RST-03', 1390, 'straight', 'raw', 'raw_indigo', 32, 40, 24, 11.5, 32, 16), ('BLACK SKINNY 04', 'BSK-04', 1290, 'skinny', 'clean', 'black', 32, 38, 21.5, 10.5, 31.5, 12), ('ARCHIVE WIDE 05', 'AWD-05', 1590, 'wide', 'washed', 'light_blue', 32, 44, 27, 13, 32.5, 21), ('GREY LOOSE 06', 'GLS-06', 1290, 'loose', 'washed', 'grey', 32, 42, 25.5, 12, 32, 18.5), ('FADED RELAX 07', 'FRX-07', 1190, 'relaxed', 'washed', 'washed_blue', 33, 43, 26, 12, 31.5, 18), ('70S FLARE 08', 'FLR-08', 1590, 'flare', 'vintage', 'vintage_blue', 31, 39, 23, 11.5, 33, 24), ('BOOTCUT 09', 'BTC-09', 1490, 'bootcut', 'clean', 'dark_indigo', 31, 39, 22.5, 11, 32.5, 19), ('UTILITY CARGO 10', 'CRG-10', 1690, 'cargo', 'washed', 'grey', 32, 43, 27, 12.5, 32, 20), ('WIDE STRAIGHT 11', 'WST-11', 1490, 'wide_straight', 'clean', 'dark_indigo', 32, 42, 25, 12, 32, 19), ('VINTAGE RELAX 12', 'VTR-12', 1390, 'relaxed', 'vintage', 'vintage_blue', 32, 42, 25, 12, 32, 18)]
    colors = ['dark_indigo', 'washed_blue', 'black']
    for row in seed:
        q.execute('INSERT OR IGNORE INTO products(name,code,price,fit,style,color,waist,hip,thigh,rise,inseam,leg_opening,stock) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', row + (15,))
        pid = q.execute('SELECT id FROM products WHERE code=?', (row[1],)).fetchone()['id']
        for color in colors:
            for size in (28, 30, 32, 34, 36):
                q.execute('INSERT OR IGNORE INTO variants(product_id,color,size,stock) VALUES(?,?,?,?)', (pid, color, size, 3))
    q.execute("INSERT OR IGNORE INTO shop_metadata VALUES('bootstrap_completed','1')")
    from support import catalogue
    catalogue.install(c)
    from support import sizing
    migrate_customer_details(c)
    sizing.migrate(c)
    c.commit()
    c.close()

# แปลงผลลัพธ์ SQLite เป็นข้อมูลแบบ dict
def _dict(r):
    return dict(r) if r else None

# ตรวจรหัสผ่านและสถานะบัญชีก่อนคืนข้อมูลผู้ใช้
def login_user(email, password):
    status,user=login_status(email,password)
    return user

def login_status(email,password):
    c = conn()
    r = c.execute('SELECT * FROM users WHERE lower(email)=lower(?)', (email.strip(),)).fetchone()
    c.close()
    if not r or not check_password(password,r['password_hash']):return 'invalid',None
    if not r['active']:return 'banned',None
    return 'ok',_dict(r)

# ตรวจข้อมูลและเพิ่มบัญชีสมาชิกใหม่ลงฐานข้อมูล
def validate_password(value):
    import re
    if (not isinstance(value,str) or len(value)<8 or not re.fullmatch(r'[A-Za-z0-9]+',value)
        or not re.search(r'[a-z]',value) or not re.search(r'[A-Z]',value) or not re.search(r'[0-9]',value)):
        raise ValueError('รหัสผ่านต้องมีอย่างน้อย 8 ตัว ใช้ A–Z, a–z และตัวเลข ต้องมีครบทั้งสามแบบ ห้ามใช้อักขระพิเศษ / Use at least 8 characters with uppercase, lowercase English letters and digits only.')

def validate_email(value):
    import re
    if not re.fullmatch(r"[^\s@]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+",value.strip()):
        raise ValueError('กรอกอีเมล เช่น name@example.com / Enter a valid email, e.g. name@example.com.')

MAX_PRODUCT_QUANTITY=20

def product_cart_quantity(cart,pid):
    return sum(qty for key,qty in cart.items() if key[0]==pid)

def validate_cart_quantities(cart):
    totals={}
    for (pid,color,size),qty in cart.items():
        if isinstance(qty,bool) or not isinstance(qty,int) or qty<=0:raise ValueError('Invalid quantity.')
        totals[pid]=totals.get(pid,0)+qty
    if any(qty>MAX_PRODUCT_QUANTITY for qty in totals.values()):
        raise ValueError('เลือกสินค้าแต่ละรุ่นรวมทุกสีและไซซ์ได้ไม่เกิน 20 ตัวต่อคำสั่งซื้อ / Maximum 20 units per product, across colors and sizes, per order.')

def register_user(fn, ln, email, pw, lang='TH', phone=''):
    validate_phone(phone)
    validate_password(pw)
    validate_email(email)
    if not fn.strip() or not ln.strip():raise ValueError('กรอกชื่อและนามสกุล / Enter your first and last names.')
    try:
        c = conn()
        c.execute('INSERT INTO users(first_name,last_name,email,password_hash,language,phone,registered_phone) VALUES(?,?,?,?,?,?,?)', (fn.strip(), ln.strip(), email.strip(), hash_password(pw), lang, phone, phone))
        c.commit()
        c.close()
        return True
    except sqlite3.IntegrityError:
        return False

# ตรวจข้อมูลบัญชีและเปลี่ยนรหัสผ่านเป็นค่าที่เข้ารหัสแล้ว
def reset_password(email, new_password, old_password=''):
    """Change a password only after verifying the existing password."""
    validate_password(new_password)
    c = conn()
    row = c.execute('SELECT * FROM users WHERE lower(email)=lower(?) AND active=1', (email.strip(),)).fetchone()
    if not row or not check_password(old_password,row['password_hash']):
        c.close()
        return False
    c.execute('UPDATE users SET password_hash=? WHERE id=?', (hash_password(new_password), row['id']))
    c.commit()
    c.close()
    return True

# บันทึกภาษาที่เลือกไว้ในบัญชี
def update_language(uid, lang):
    c = conn()
    c.execute('UPDATE users SET language=? WHERE id=?', (lang, uid))
    c.commit()
    c.close()

# แก้ไขข้อมูลบัญชีและรหัสผ่านเมื่อมีการระบุผ่านตัวจัดการเดิม
def update_profile(uid, fn, ln, email, pw=''):
    validate_email(email)
    if pw:validate_password(pw)
    try:
        c = conn()
        if pw:
            c.execute('UPDATE users SET first_name=?,last_name=?,email=?,password_hash=? WHERE id=?', (fn, ln, email, hash_password(pw), uid))
        else:
            c.execute('UPDATE users SET first_name=?,last_name=?,email=? WHERE id=?', (fn, ln, email, uid))
        c.commit()
        c.close()
        return True
    except sqlite3.IntegrityError:
        return False

# อ่านรายการสินค้าและเลือกว่าจะรวมสินค้าที่ซ่อนหรือไม่
def products(include_archived=False):
    c = conn()
    rows = [dict(x) for x in c.execute('SELECT * FROM products' + ('' if include_archived else ' WHERE active=1') + ' ORDER BY id')]
    c.close()
    return rows

# อ่านข้อมูลสินค้าตามหมายเลขสินค้า
def product(pid):
    c = conn()
    r = _dict(c.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone())
    c.close()
    return r

# อ่านรุ่นย่อยของสินค้าซึ่งแยกตามสีและไซซ์
def variants(pid):
    c = conn()
    from support import product_colors
    rows = [dict(x) for x in c.execute('SELECT * FROM variants WHERE product_id=? ORDER BY color,size', (pid,)) if product_colors.active(c,pid,x['color'])]
    c.close()
    return rows

# อ่านจำนวนคงเหลือของสินค้า สี และไซซ์ที่ระบุ
def variant_stock(pid, color, size):
    c = conn()
    r = c.execute('SELECT stock FROM variants WHERE product_id=? AND color=? AND size=?', (pid, color, size)).fetchone()
    c.close()
    from support import product_colors
    c=conn()
    try:visible=product_colors.active(c,pid,color)
    finally:c.close()
    return r['stock'] if r and visible else 0

# ตรวจข้อมูลและสร้างคำสั่งซื้อพร้อมรายการสินค้า โดยยังไม่ตัดสต็อกก่อนชำระ
# J26 | สร้างคำสั่งซื้อและตรวจสต็อก
def create_order(uid, name, phone, address, cart, postal_code='', points=0, refund_details=None):
    from support import loyalty
    from decimal import Decimal
    from support import returns
    bank=returns.bank_details(refund_details)
    validate_phone(phone)
    if not cart or not all(str(v).strip() for v in (name,phone,address)):
        raise ValueError('Cart and delivery details are required.')
    if postal_code and (len(postal_code.strip())!=5 or not postal_code.strip().isascii() or not postal_code.strip().isdigit()):raise ValueError('รหัสไปรษณีย์ต้องเป็นเลข 5 หลัก / Postal code must be 5 digits.')
    c = conn()
    try:
        c.execute('BEGIN IMMEDIATE')
        if not c.execute('SELECT id FROM users WHERE id=? AND active=1',(uid,)).fetchone():
            raise ValueError('Customer not found.')
        validate_cart_quantities(cart)
        subtotal=Decimal('0'); items=[]
        for (pid,color,size),qty in cart.items():
            if isinstance(qty,bool) or int(qty)!=qty or qty<=0: raise ValueError('Invalid quantity.')
            p=c.execute('SELECT * FROM products WHERE id=? AND active=1',(pid,)).fetchone()
            stock=c.execute('SELECT stock FROM variants WHERE product_id=? AND color=? AND size=?',(pid,color,size)).fetchone()
            from support import product_colors
            if not p or not stock or not product_colors.active(c,pid,color) or stock['stock']<qty: raise ValueError('Product or size is unavailable. Please check your bag.')
            unit_price=price_for_size(dict(p),size,c)
            subtotal+=Decimal(str(unit_price))*qty
            items.append((pid,color,size,qty,unit_price,p['name'],p['code']))
        if points:raise ValueError('ระบบแต้มสะสมถูกยกเลิกแล้ว')
        from support import product_promotions
        totals=product_promotions.cart_quote(cart,uid,c)
        cur=c.execute('INSERT INTO orders(user_id,customer_name,phone,address,total,subtotal,discount_amount,promo_day,promo_percent,reward_points) VALUES(?,?,?,?,?,?,?,?,?,?)',
                      (uid,name.strip(),phone.strip(),address.strip(),totals['total'],totals['subtotal'],totals['discount_amount'],totals['promo_day'],totals['promo_percent'],totals['reward_points']))
        oid=cur.lastrowid
        c.execute('UPDATE orders SET discount_kind=? WHERE id=?',(totals['discount_kind'],oid))
        # กำหนดหมายเลขและลำดับภายในธุรกรรมเดียวกับการสร้างคำสั่งซื้อ
        row=dict(c.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone())
        sequence=c.execute('SELECT COALESCE(MAX(order_sequence),0)+1 FROM orders').fetchone()[0]
        c.execute('UPDATE orders SET order_number=?,order_sequence=? WHERE id=?',(order_number(row),sequence,oid))
        c.execute('UPDATE orders SET postal_code=?,redeemed_points=?,points_discount=?,promo_minimum=?,promo_cap=? WHERE id=?',(postal_code.strip(),totals['redeemed_points'],totals['points_discount'],totals['promo_minimum'],totals['promo_cap'],oid))
        tax=vat_breakdown(totals['total'])
        c.execute('UPDATE orders SET vat_amount=?,before_vat=? WHERE id=?',(tax['vat'],tax['before_vat'],oid))
        c.execute('UPDATE users SET delivery_name=?,phone=?,address=?,postal_code=? WHERE id=?',(name.strip(),phone.strip(),address.strip(),postal_code.strip(),uid))
        if any(bank.values()):
            c.execute('UPDATE users SET refund_bank=?,refund_name=?,refund_account=? WHERE id=?',(bank['bank'],bank['name'],bank['account'],uid))
        c.execute('UPDATE orders SET refund_bank=?,refund_name=?,refund_account=? WHERE id=?',(bank['bank'],bank['name'],bank['account'],oid))
        for item in items: c.execute('INSERT INTO order_items(order_id,product_id,color,size,quantity,price,product_name,product_code) VALUES(?,?,?,?,?,?,?,?)',(oid,)+item)
        c.execute("INSERT INTO events(user_id,kind,target) VALUES(?,'order_created',?)",(uid,str(oid)))
        c.commit(); return oid
    except Exception:
        c.rollback(); raise
    finally: c.close()

# อ่านประวัติคำสั่งซื้อของบัญชี
def orders(uid=None):
    c = conn()
    sql = 'SELECT * FROM orders'
    args = ()
    if uid is not None:
        sql += ' WHERE user_id=?'
        args = (uid,)
    sql += ' ORDER BY id DESC'
    rows = [dict(x) for x in c.execute(sql, args)]
    c.close()
    return rows

# ยกเลิกคำสั่งซื้อที่อยู่ในสถานะยกเลิกได้ พร้อมคืนสต็อกตามเงื่อนไข
def cancel_customer_order(uid,oid):
    from support import loyalty
    c=conn()
    try:
        c.execute('BEGIN IMMEDIATE')
        o=c.execute('SELECT * FROM orders WHERE id=? AND user_id=?',(oid,uid)).fetchone()
        if not o or o['payment_status'] not in ('waiting_payment','under_review','rejected') or o['stock_deducted'] or o['order_status']!='waiting_payment':raise ValueError('This order cannot be cancelled.')
        loyalty.release(c,o)
        c.execute("UPDATE orders SET payment_status='cancelled',order_status='cancelled' WHERE id=?",(oid,))
        c.execute("INSERT INTO events(user_id,kind,target) VALUES(?,'order_cancelled',?)",(uid,str(oid)))
        c.commit()
    except Exception:c.rollback();raise
    finally:c.close()

# อ่านหลักฐานชำระเงินล่าสุดของคำสั่งซื้อ
def latest_payment(oid):
    c = conn()
    r = _dict(c.execute('SELECT * FROM payments WHERE order_id=? ORDER BY id DESC LIMIT 1', (oid,)).fetchone())
    c.close()
    return r

# ตรวจเจ้าของคำสั่งซื้อก่อนเพิ่มหรือเปลี่ยนหลักฐานการชำระเงิน
def add_payment(oid, path, uid=None):
    c = conn()
    try:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT user_id,payment_status,order_status FROM orders WHERE id=?',(oid,)).fetchone()
        if uid is not None and (not row or row['user_id']!=uid):raise PermissionError('ไม่สามารถแก้ไขหลักฐานของบัญชีอื่นได้')
        if not row or row['payment_status'] not in ('waiting_payment','rejected','under_review') or row['order_status']!='waiting_payment':
            raise ValueError('This order cannot accept another receipt.')
        c.execute('INSERT INTO payments(order_id,receipt_path) VALUES(?,?)', (oid, path))
        c.execute("UPDATE orders SET payment_status='under_review' WHERE id=?", (oid,))
        c.commit()
    except Exception:
        c.rollback(); raise
    finally: c.close()

# ปรับสถานะคำสั่งซื้อและข้อมูลเลขพัสดุ
def set_order_status(oid, payment_status, order_status, actor_id=None, tracking='', note=''):
    """Compatibility entry point; all changes use guarded shop transactions."""
    from support import admin_data
    if actor_id is None: raise PermissionError('Administrator identity is required.')
    actions={('paid','preparing'):'approve',('rejected','waiting_payment'):'reject',
             ('paid','shipped'):'ship',('paid','completed'):'complete',
             ('cancelled','cancelled'):'cancel',('refunded','refunded'):'refund'}
    if (payment_status,order_status) not in actions: raise ValueError('Invalid status transition.')
    admin_data.change_order(actor_id,oid,actions[(payment_status,order_status)],tracking,note)

# บันทึกจำนวนคงเหลือของรุ่นย่อย
def set_variant_stock(vid, stock, actor_id=None):
    from support import admin_data
    if actor_id is None: raise PermissionError('Administrator identity is required.')
    admin_data.set_stock(actor_id,vid,stock)


# ตรวจว่าสินค้าอยู่ในรายการโปรดของบัญชีหรือไม่
def is_favorite(user_id, product_id):
    connection = conn()
    row = connection.execute(
        "SELECT id FROM favorites WHERE user_id=? AND product_id=?",
        (user_id, product_id),
    ).fetchone()
    connection.close()
    return row is not None


# เพิ่มหรือนำสินค้าออกจากรายการโปรดของบัญชี
def toggle_favorite(user_id, product_id):
    connection = conn()
    row = connection.execute(
        "SELECT id FROM favorites WHERE user_id=? AND product_id=?",
        (user_id, product_id),
    ).fetchone()

    if row:
        connection.execute("DELETE FROM favorites WHERE id=?", (row["id"],))
        saved = False
    else:
        connection.execute(
            "INSERT INTO favorites(user_id,product_id) VALUES(?,?)",
            (user_id, product_id),
        )
        saved = True

    connection.commit()
    connection.close()
    return saved


# อ่านสินค้าที่บัญชีบันทึกเป็นรายการโปรด
def favorite_products(user_id):
    connection = conn()
    rows = connection.execute(
        """SELECT p.* FROM favorites f
           JOIN products p ON p.id=f.product_id
           WHERE f.user_id=? AND p.active=1 ORDER BY f.created_at DESC""",
        (user_id,),
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


# บันทึกว่าสมาชิกเปิดดูสินค้ารุ่นใดล่าสุด
def record_recent_view(user_id, product_id):
    connection = conn()
    connection.execute(
        "DELETE FROM recently_viewed WHERE user_id=? AND product_id=?",
        (user_id, product_id),
    )
    connection.execute(
        "INSERT INTO recently_viewed(user_id,product_id,viewed_at) VALUES(?,?,CURRENT_TIMESTAMP)",
        (user_id, product_id),
    )
    connection.commit()
    connection.close()


# อ่านสินค้าที่บัญชีเพิ่งดู
def recent_products(user_id, limit=4):
    connection = conn()
    rows = connection.execute(
        """SELECT p.* FROM recently_viewed r
           JOIN products p ON p.id=r.product_id
           WHERE r.user_id=? AND p.active=1 ORDER BY r.viewed_at DESC LIMIT ?""",
        (user_id, limit),
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


# เก็บผลการแนะนำขนาดในตารางประวัติเดิม ซึ่งไม่มีเมนูประวัติในหน้าร้าน
def save_fit_history(user_id, height, waist, hip, thigh, preferred_fit, product_ids):
    ids_text = ",".join(str(product_id) for product_id in product_ids)
    connection = conn()
    cursor = connection.execute(
        """INSERT INTO fit_history(
               user_id,height,waist,hip,thigh,preferred_fit,result_product_ids
           ) VALUES(?,?,?,?,?,?,?)""",
        (user_id, height, waist, hip, thigh, preferred_fit, ids_text),
    )
    history_id = cursor.lastrowid
    connection.commit()
    connection.close()
    return history_id


# อ่านข้อมูลประวัติการแนะนำเดิมจากฐานข้อมูล
def fit_history(user_id, limit=10):
    connection = conn()
    rows = connection.execute(
        "SELECT * FROM fit_history WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


# อ่านสินค้าที่เกี่ยวกับประวัติการแนะนำเดิม
def history_products(result_product_ids):
    ids = [
        int(value)
        for value in result_product_ids.split(",")
        if value.strip().isdigit()
    ]
    items = []
    for product_id in ids:
        item = product(product_id)
        if item:
            items.append(item)
    return items


# Sizes are stored as waist keys so existing orders and stock remain intact.
# XXL and 2XL are the same international size; the old 36-inch key is 2XL.
SIZE_LABELS={24:'XXS',26:'XS',28:'S',30:'M',32:'L',34:'XL',36:'2XL',38:'3XL',40:'4XL',42:'5XL'}

# แปลงค่าขนาดที่เก็บในฐานข้อมูลเป็นไซซ์สากล เช่น S M L XL
def size_label(size):
    return SIZE_LABELS.get(int(size),str(size))

# แปลงชื่อไซซ์สากลกลับเป็นค่าขนาดที่ใช้จัดเก็บ
def size_key(label):
    for key,value in SIZE_LABELS.items():
        if value==label:return key
    raise ValueError('เลือกไซซ์จากรายการ')

# ตรวจว่าเบอร์โทรเป็นตัวเลข 10 หลัก
def validate_phone(value):
    value=str(value).strip()
    if len(value)!=10 or not value.isascii() or not value.isdigit():
        raise ValueError('เบอร์โทรศัพท์ต้องเป็นตัวเลข 10 หลัก ห้ามเกิน 10 หลัก')
    return value

# เพิ่มข้อมูลบัญชี ที่อยู่ รูปโปรไฟล์ ราคาไซซ์ และการติดตามสต็อก
def migrate_customer_details(c):
    for name,definition in [('phone',"TEXT DEFAULT ''"),('address',"TEXT DEFAULT ''"),('postal_code',"TEXT DEFAULT ''"),('delivery_name',"TEXT DEFAULT ''"),('avatar',"TEXT DEFAULT ''"),('avatar_source',"TEXT DEFAULT ''"),('avatar_crop',"TEXT DEFAULT ''"),('active','INTEGER DEFAULT 1')]:
        add_column_if_missing(c,'users',name,definition)
    for name in ('vat_amount','before_vat'):
        add_column_if_missing(c,'orders',name,'REAL DEFAULT 0')
    c.execute("UPDATE orders SET vat_amount=ROUND(total*7/107,2),before_vat=total-ROUND(total*7/107,2) WHERE before_vat=0 AND total>0")
    c.execute("CREATE TABLE IF NOT EXISTS size_prices(size INTEGER PRIMARY KEY,surcharge REAL DEFAULT 0)")
    for size in SIZE_LABELS:
        c.execute('INSERT OR IGNORE INTO size_prices VALUES(?,?)',(size,0 if size<36 else 100+(size-36)//2*50))
    if c.execute('SELECT COUNT(*) FROM products').fetchone()[0] and not c.execute("SELECT 1 FROM shop_metadata WHERE key='international_sizes_v1'").fetchone():
        for product in c.execute('SELECT * FROM products').fetchall():
            for color in c.execute('SELECT DISTINCT color FROM variants WHERE product_id=?',(product['id'],)).fetchall():
                for size in (24,26,38,40,42):
                    # No manufactured stock: new sizes start empty until the admin fills them.
                    c.execute('INSERT OR IGNORE INTO variants(product_id,color,size,stock) VALUES(?,?,?,0)',(product['id'],color['color'],size))
        c.execute("INSERT INTO shop_metadata VALUES('international_sizes_v1','1')")
    # Preserve historical points but stop earning or spending new ones.
    c.execute("INSERT INTO shop_metadata VALUES('points_enabled','0') ON CONFLICT(key) DO UPDATE SET value='0'")

# คำนวณราคาของสินค้า รวมราคาเพิ่มตามไซซ์ที่แอดมินตั้งไว้
def price_for_size(product,size,c=None):
    if c is None:
        connection=conn()
        try:return price_for_size(product,size,connection)
        finally:connection.close()
    row=c.execute('SELECT surcharge FROM size_prices WHERE size=?',(size,)).fetchone()
    return round(float(product['price'])+(float(row['surcharge']) if row else 0),2)

# แยกยอดก่อนภาษีและ VAT 7% จากราคาที่รวมภาษีแล้ว
def vat_breakdown(total):
    # แยก VAT ที่รวมในยอดแล้วด้วยสูตรยอด × 7/107 ไม่บวกภาษีเพิ่มเข้าไปอีก
    from decimal import Decimal,ROUND_HALF_UP
    amount=Decimal(str(total)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    vat=(amount*Decimal(7)/Decimal(107)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    return dict(total=float(amount),vat=float(vat),before_vat=float(amount-vat))

# รวมจำนวนสินค้าของคำสั่งซื้อที่ยังดำเนินการอยู่เพื่อบังคับขีดจำกัดบัญชี
def outstanding_quantity(uid,c=None):
    if c is None:
        connection=conn()
        try:return outstanding_quantity(uid,connection)
        finally:connection.close()
    return c.execute("SELECT COALESCE(SUM(i.quantity),0) FROM order_items i JOIN orders o ON o.id=i.order_id WHERE o.user_id=? AND o.order_status NOT IN ('completed','cancelled','refunded')",(uid,)).fetchone()[0]

# อ่านข้อมูลบัญชีล่าสุดตามหมายเลขผู้ใช้
def user(uid):
    c=conn()
    try:return _dict(c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone())
    finally:c.close()

# ตรวจและบันทึกข้อมูลสมาชิก ที่อยู่ และรูปโปรไฟล์
def save_customer_details(uid,values):
    allowed=('first_name','last_name','email','phone','address','postal_code','delivery_name','avatar','avatar_source','avatar_crop')
    clean={k:str(v).strip() for k,v in values.items() if k in allowed}
    if 'phone' in clean:validate_phone(clean['phone'])
    if 'email' in clean and '@' not in clean['email']:raise ValueError('กรอกอีเมลให้ถูกต้อง')
    if 'postal_code' in clean and clean['postal_code'] and (len(clean['postal_code'])!=5 or not clean['postal_code'].isascii() or not clean['postal_code'].isdigit()):raise ValueError('รหัสไปรษณีย์ต้องเป็นเลข 5 หลัก')
    if not clean:return
    c=conn()
    try:
        c.execute('UPDATE users SET '+','.join(k+'=?' for k in clean)+' WHERE id=?',tuple(clean.values())+(uid,))
        c.commit()
    except Exception:c.rollback();raise
    finally:c.close()

# ปิดบัญชีลูกค้าโดยเก็บประวัติคำสั่งซื้อไว้
def deactivate_customer(actor,uid):
    from support import admin_data
    with admin_data.transaction(actor) as c:
        row=c.execute("SELECT role FROM users WHERE id=?",(uid,)).fetchone()
        if not row or row['role']!='customer':raise ValueError('เลือกบัญชีลูกค้าเท่านั้น')
        c.execute('UPDATE users SET active=0 WHERE id=?',(uid,))
        admin_data.audit(c,actor,'customer_deactivated',uid,'บัญชีลูกค้าถูกปิด ประวัติคำสั่งซื้อคงอยู่')

def reactivate_customer(actor,uid):
    from support import admin_data
    with admin_data.transaction(actor) as c:
        row=c.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()
        if not row or row['role']!='customer':raise ValueError('เลือกบัญชีลูกค้าเท่านั้น / Select a customer account.')
        c.execute('UPDATE users SET active=1 WHERE id=?',(uid,))
        admin_data.audit(c,actor,'customer_unbanned',uid,'ปลดแบนบัญชีลูกค้า ข้อมูลและคำสั่งซื้อเดิมคงอยู่')

def change_admin_password(actor,current,new):
    from support import admin_data
    validate_password(new)
    with admin_data.transaction(actor) as c:
        row=c.execute('SELECT password_hash FROM users WHERE id=?',(actor,)).fetchone()
        if not check_password(current,row['password_hash']):raise ValueError('รหัสผ่านปัจจุบันไม่ถูกต้อง / Current password is incorrect.')
        c.execute('UPDATE users SET password_hash=? WHERE id=?',(hash_password(new),actor))
        admin_data.audit(c,actor,'admin_password_changed',actor,'Administrator changed their own password; no secrets logged')
