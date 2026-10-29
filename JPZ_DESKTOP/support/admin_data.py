"""Local shop operations, event history and administrator reporting."""
import csv
import json
import math
import sqlite3
from contextlib import contextmanager,nullcontext
from pathlib import Path
import db

def migrate(c):
    db.add_column_if_missing(c, 'products', 'active', 'INTEGER DEFAULT 1')
    db.add_column_if_missing(c, 'orders', 'tracking', "TEXT DEFAULT ''")
    db.add_column_if_missing(c, 'orders', 'admin_note', "TEXT DEFAULT ''")
    c.execute('CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, user_id INTEGER, kind TEXT, target TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
    c.execute('CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY, actor_id INTEGER, action TEXT, target TEXT, detail TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
    c.execute('CREATE TABLE IF NOT EXISTS shop_metadata(key TEXT PRIMARY KEY, value TEXT)')
    c.execute("INSERT OR IGNORE INTO shop_metadata VALUES('analytics_started', CURRENT_TIMESTAMP)")
    c.execute('CREATE INDEX IF NOT EXISTS events_time ON events(created_at, kind)')
    from support import catalogue
    catalogue.migrate(c)
    import receipt as receipts
    receipts.migrate(c)
    from support import returns
    returns.migrate(c)
    from support import password_otp
    password_otp.migrate(c)
    from support import email_otp
    email_otp.migrate(c)
    from support import slip_verification
    slip_verification.migrate(c)

def log_event(user_id, kind, target=''):
    c=db.conn()
    try:
        c.execute('INSERT INTO events(user_id,kind,target) VALUES(?,?,?)', (user_id, kind, str(target)))
        c.commit()
    finally: c.close()

def require_admin(c, actor):
    row=c.execute("SELECT role,active FROM users WHERE id=?", (actor,)).fetchone()
    if not row or row['role']!='admin' or not row['active']:
        raise PermissionError('Administrator access required.')

@contextmanager
def transaction(actor):
    c=db.conn()
    try:
        c.execute('BEGIN IMMEDIATE')
        require_admin(c, actor)
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()

def audit(c,actor,action,target,detail):
    c.execute('INSERT INTO audit_log(actor_id,action,target,detail) VALUES(?,?,?,?)',
              (actor, action, str(target), str(detail)))


def change_user_role(actor, uid, role):
    """Keep account identity/history and serialize the last-admin check."""
    if role not in ('customer','admin'):
        raise ValueError('เลือกสิทธิ์ลูกค้าหรือแอดมิน / Choose customer or administrator.')
    with transaction(actor) as c:
        user=c.execute('SELECT role,active FROM users WHERE id=?',(uid,)).fetchone()
        if not user or not user['active']:
            raise ValueError('บัญชีนี้ไม่พร้อมใช้งาน / Account is inactive or unavailable.')
        if user['role']==role:return False
        if user['role']=='admin' and role=='customer':
            remaining=c.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1 AND id!=?",(uid,)).fetchone()[0]
            if not remaining:
                raise ValueError('ต้องเหลือแอดมินที่ใช้งานได้อย่างน้อย 1 บัญชี / Keep at least one active administrator.')
        c.execute('UPDATE users SET role=? WHERE id=?',(role,uid))
        c.execute('UPDATE password_challenges SET consumed=1 WHERE user_id=?',(uid,))
        audit(c,actor,'user_role_changed',uid,f"{user['role']} → {role}")
        return True

def query(actor,sql,args=()):
    c=db.conn()
    try:
        require_admin(c,actor)
        return [dict(r) for r in c.execute(sql,args)]
    finally: c.close()

def dashboard(actor, days=None, start=None, end=None, include_activity=True):
    args=() if days is None else (f'-{int(days)} days',)
    condition='1=1' if days is None else "created_at>=datetime('now',?)"
    if start is not None or end is not None:
        from datetime import date
        if start is None or end is None or date.fromisoformat(start)>date.fromisoformat(end):raise ValueError('Invalid date range.')
        condition="date(created_at,'+7 hours') BETWEEN ? AND ?";args=(start,end)
    result=query(actor,f"""SELECT COUNT(*) orders,
      COALESCE(SUM(CASE WHEN payment_status='paid' THEN total ELSE 0 END),0) revenue,
      COALESCE(SUM(CASE WHEN payment_status='under_review' AND order_status!='cancelled' THEN 1 ELSE 0 END),0) review,
      COALESCE(SUM(CASE WHEN payment_status='paid' AND order_status='preparing' THEN 1 ELSE 0 END),0) preparing,
      COALESCE(SUM(CASE WHEN payment_status='refunded' THEN total ELSE 0 END),0) refunds
      FROM orders WHERE {condition}""",args)[0]
    result['customers']=query(actor,"SELECT COUNT(*) n FROM users WHERE role='customer' AND active=1")[0]['n']
    result['stock']=query(actor,'SELECT COALESCE(SUM(v.stock),0) n FROM variants v JOIN products p ON p.id=v.product_id WHERE p.active=1')[0]['n']
    result['low_stock']=query(actor,'SELECT COUNT(*) n FROM variants v JOIN products p ON p.id=v.product_id WHERE v.stock<5 AND p.active=1')[0]['n']
    result['events']=query(actor,f"SELECT kind,COUNT(*) n FROM events WHERE {condition} GROUP BY kind",args) if include_activity else []
    result['analytics_since']=query(actor,"SELECT value FROM shop_metadata WHERE key='analytics_started'")[0]['value']
    result['records_since']=query(actor,"SELECT MIN(created_at) value FROM (SELECT created_at FROM users UNION ALL SELECT created_at FROM orders)")[0]['value']
    result['daily']=query(actor,f"SELECT date(created_at,'+7 hours') day, COUNT(*) orders, SUM(CASE WHEN payment_status='paid' THEN total ELSE 0 END) revenue FROM orders WHERE {condition} GROUP BY day ORDER BY day DESC",args)
    result['top']=query(actor,f"""SELECT p.name, SUM(i.quantity) units, SUM(i.quantity*i.price*o.total/NULLIF(o.subtotal,0)) revenue
        FROM order_items i JOIN products p ON p.id=i.product_id JOIN orders o ON o.id=i.order_id
        WHERE o.payment_status='paid' AND {condition.replace('created_at','o.created_at')}
        GROUP BY p.id ORDER BY revenue DESC LIMIT 5""",args)
    return result

def order_items(actor,oid):
    return query(actor,"SELECT i.*,COALESCE(NULLIF(i.product_name,''),p.name) name,COALESCE(NULLIF(i.product_code,''),p.code) code FROM order_items i LEFT JOIN products p ON p.id=i.product_id WHERE i.order_id=?",(oid,))

def change_order(actor,oid,action,tracking=None,note='',verified_payment=None,reference=None,not_shipped_confirmed=False):
    from support import loyalty
    with transaction(actor) as c:
        o=c.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
        if not o: raise ValueError('Order not found.')
        tracking=o['tracking'] if tracking is None else tracking.strip()
        payment,status=o['payment_status'],o['order_status']
        if action=='approve':
            if payment!='under_review' or status=='cancelled': raise ValueError('Only payments under review can be approved.')
            if c.execute('SELECT 1 FROM order_corrections WHERE order_id=?',(oid,)).fetchone() and reference is None and verified_payment is None:
                raise ValueError('รายการแก้ไขต้องตรวจหลักฐานและยืนยันเลขอ้างอิงอีกครั้ง / Corrected orders require a fresh payment reference confirmation.')
            if not c.execute('SELECT id FROM payments WHERE order_id=?',(oid,)).fetchone(): raise ValueError('No payment receipt to review.')
            if verified_payment is not None:
                latest=c.execute('SELECT id FROM payments WHERE order_id=? ORDER BY id DESC LIMIT 1',(oid,)).fetchone()
                valid=c.execute('SELECT amount,payment_id FROM verified_slips WHERE order_id=? AND payment_id=?',(oid,verified_payment)).fetchone()
                if not valid or valid['payment_id']!=verified_payment or latest['id']!=verified_payment or valid['amount']!=o['total']:raise ValueError('สลิปที่ตรวจไม่ตรงกับคำสั่งซื้อปัจจุบัน / Verified slip no longer matches the order.')
            if not o['stock_deducted']:
                for item in c.execute('SELECT product_id,color,size,SUM(quantity) quantity FROM order_items WHERE order_id=? GROUP BY product_id,color,size',(oid,)).fetchall():
                    cur=c.execute('UPDATE variants SET stock=stock-? WHERE product_id=? AND color=? AND size=? AND stock>=?',
                                  (item['quantity'],item['product_id'],item['color'],item['size'],item['quantity']))
                    if cur.rowcount!=1: raise ValueError('Insufficient stock. Update stock before approving payment.')
                c.execute('UPDATE orders SET stock_deducted=1 WHERE id=?',(oid,))
            payment,status='paid','preparing'
            loyalty.award(c,o)
        elif action=='reject':
            if payment!='under_review' or status=='cancelled': raise ValueError('ปฏิเสธได้เฉพาะรายการรอตรวจสอบ / Only payments under review can be rejected.')
            payment,status='rejected','waiting_payment'
        elif action=='review':
            if payment not in ('waiting_payment','rejected','cancelled','paid'):
                raise ValueError('สถานะนี้เปลี่ยนกลับเป็นรอตรวจสอบไม่ได้ / This payment cannot return to review.')
            if not note.strip():raise ValueError('กรอกเหตุผลแก้ไขสถานะก่อน / Enter a reason for the status correction.')
            if not c.execute('SELECT 1 FROM payments WHERE order_id=?',(oid,)).fetchone():
                raise ValueError('ยังไม่มีหลักฐานชำระเงินให้ตรวจสอบ / No payment proof to review.')
            if c.execute("SELECT 1 FROM receipt_outbox WHERE order_id=? AND status='sending'",(oid,)).fetchone():
                raise ValueError('กำลังส่งใบเสร็จ กรุณารอให้ส่งเสร็จแล้วลองใหม่ / Receipt email is being sent; retry after it finishes.')
            if payment=='paid' and (status not in ('preparing','shipped','completed') or not_shipped_confirmed is not True):
                raise ValueError('ยืนยันก่อนว่ายังไม่ได้จัดส่งจริง หากส่งแล้วใช้ขั้นตอนคืนสินค้า/คืนเงิน / Confirm the order has not actually shipped; shipped goods require the return/refund process.')
            snapshot={'order':dict(o),'reason':note.strip()}
            for table in ('receipt_approvals','receipt_outbox','points_ledger'):
                snapshot[table]=[dict(r) for r in c.execute('SELECT * FROM '+table+' WHERE order_id=?',(oid,))]
            c.execute('INSERT INTO order_corrections(order_id,actor_id,snapshot) VALUES(?,?,?)',(oid,actor,json.dumps(snapshot,ensure_ascii=False)))
            if o['stock_deducted']:
                for item in c.execute('SELECT product_id,color,size,SUM(quantity) quantity FROM order_items WHERE order_id=? GROUP BY product_id,color,size',(oid,)).fetchall():
                    cur=c.execute('UPDATE variants SET stock=stock+? WHERE product_id=? AND color=? AND size=?',(item['quantity'],item['product_id'],item['color'],item['size']))
                    if cur.rowcount!=1:raise ValueError('ไม่พบสต็อกเดิม กรุณาตรวจรายการสินค้า / Original stock variant is missing.')
            c.execute('UPDATE orders SET stock_deducted=0,paid_at=NULL WHERE id=?',(oid,))
            c.execute("DELETE FROM points_ledger WHERE order_id=? AND kind='earned'",(oid,))
            c.execute("UPDATE receipt_outbox SET status='void',error='',claimed_at=NULL WHERE order_id=?",(oid,))
            payment,status='under_review','waiting_payment';tracking=''
        elif action=='prepare':
            if payment!='paid' or status not in ('preparing','shipped','completed'):raise ValueError('Only paid orders can change delivery status.')
            status='preparing'
        elif action=='ship':
            if payment!='paid' or status not in ('preparing','shipped','completed'): raise ValueError('Only paid orders can ship.')
            if not tracking.strip(): raise ValueError('Enter a tracking number before shipping.')
            status='shipped'
        elif action=='complete':
            if payment!='paid' or status not in ('preparing','shipped','completed'): raise ValueError('Only paid orders can be completed.')
            status='completed'
        elif action=='cancel':
            if payment=='paid' or status in ('cancelled','refunded'): raise ValueError('Paid orders require a refund record; this order cannot be cancelled.')
            if o['stock_deducted']:
                for item in c.execute('SELECT * FROM order_items WHERE order_id=?',(oid,)).fetchall():
                    c.execute('UPDATE variants SET stock=stock+? WHERE product_id=? AND color=? AND size=?',(item['quantity'],item['product_id'],item['color'],item['size']))
                c.execute('UPDATE orders SET stock_deducted=0 WHERE id=?',(oid,))
            payment,status='cancelled','cancelled' 
            loyalty.release(c,o)
        elif action=='refund':
            if payment!='paid' or status not in ('preparing','shipped','completed'): raise ValueError('Only paid orders can receive a refund record.')
            if not note.strip(): raise ValueError('Enter the refund reason and external transfer reference.')
            sent_before=c.execute("SELECT 1 FROM audit_log WHERE target=? AND action IN ('order_ship','order_complete') LIMIT 1",(str(oid),)).fetchone()
            if status=='preparing' and o['stock_deducted'] and not sent_before and not o['tracking']:
                for item in c.execute('SELECT * FROM order_items WHERE order_id=?',(oid,)).fetchall():
                    c.execute('UPDATE variants SET stock=stock+? WHERE product_id=? AND color=? AND size=?',
                              (item['quantity'],item['product_id'],item['color'],item['size']))
                c.execute('UPDATE orders SET stock_deducted=0 WHERE id=?',(oid,))
            payment,status='refunded','refunded'
            loyalty.reverse(c,o)
            c.execute("UPDATE return_requests SET status='refunded',updated_at=CURRENT_TIMESTAMP WHERE order_id=?",(oid,))
        elif action!='note': raise ValueError('Unknown order action.')
        c.execute('UPDATE orders SET payment_status=?,order_status=?,tracking=?,admin_note=? WHERE id=?',
                  (payment,status,tracking,note.strip(),oid))
        if action == 'approve':
            import receipt as receipts
            c.execute('UPDATE orders SET paid_at=CURRENT_TIMESTAMP WHERE id=?',(oid,))
            if reference is not None or verified_payment is not None:
                approved_ref=reference if verified_payment is None else c.execute('SELECT trans_ref FROM verified_slips WHERE order_id=? AND payment_id=?',(oid,verified_payment)).fetchone()['trans_ref']
                receipts.record_approval(c,actor,oid,approved_ref,verified_payment)
            receipts.enqueue(c, oid)
        audit(c,actor,'order_'+action,oid,f"{o['payment_status']}/{o['order_status']} → {payment}/{status}"+((' / '+note.strip()) if action=='review' else ''))

PRODUCT_FIELDS=('name','code','price','fit','style','color','waist','hip','thigh','rise','inseam','leg_opening','active','category_id')
COLORS=('dark_indigo','washed_blue','black','raw_indigo','light_blue','vintage_blue','grey')
FITS=('baggy','wide','loose','relaxed','straight','skinny','flare','bootcut','cargo','wide_straight')
STYLES=('clean','ripped','vintage','washed','raw')
PALETTES={'baggy':['washed_blue','dark_indigo','light_blue'],'wide':['black','dark_indigo','raw_indigo'],
          'loose':['grey','dark_indigo','washed_blue'],'relaxed':['washed_blue','vintage_blue','dark_indigo'],
          'straight':['raw_indigo','vintage_blue','black'],'skinny':['black','dark_indigo'],
          'flare':['raw_indigo','vintage_blue','black'],'bootcut':['raw_indigo','vintage_blue','black'],
          'cargo':['black','grey'],'wide_straight':['black','dark_indigo','raw_indigo']}

def save_product(actor,data,pid=None,initial_stock=0,initial_size=32,initial_stocks=None,connection=None):
    if isinstance(initial_stock,bool) or int(initial_stock)!=initial_stock or initial_stock<0:raise ValueError('Initial stock must be a non-negative integer.')
    if initial_size not in db.SIZE_LABELS:raise ValueError('Select a valid size.')
    if initial_stocks is not None:
        if any(size not in db.SIZE_LABELS or isinstance(size,bool) or isinstance(qty,bool) or not isinstance(qty,int) or qty<0 for size,qty in initial_stocks.items()):raise ValueError('Enter non-negative whole stock quantities for each size.')
    values=dict(data)
    values.setdefault('category_id',None)
    values['category_id']=int(values['category_id']) if values['category_id'] not in (None,'') else None
    if not values['name'].strip() or not values['code'].strip(): raise ValueError('Name and SKU are required.')
    for key in ('price','waist','hip','thigh','rise','inseam','leg_opening'):
        values[key]=float(values[key])
        if not math.isfinite(values[key]) or values[key]<=0: raise ValueError('Price and measurements must be positive numbers.')
    if values['fit'] not in FITS or values['style'] not in STYLES or (values['color'] not in COLORS and not str(values['color']).startswith('custom_')): raise ValueError('Select a valid fit, style and color.')
    values['name'],values['code']=values['name'].strip(),values['code'].strip()
    values['active']=int(values['active'])
    if values['active'] not in (0,1): raise ValueError('Invalid active flag.')
    with (nullcontext(connection) if connection is not None else transaction(actor)) as c:
        require_admin(c,actor)
        from support import product_colors
        product_colors.migrate(c)
        if not product_colors.supported(c,values['color']):raise ValueError('Invalid color.')
        if values['category_id'] is not None and not c.execute('SELECT id FROM categories WHERE id=?',(values['category_id'],)).fetchone():
            raise ValueError('Category not found.')
        if pid:
            old=c.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
            if not old: raise ValueError('Product not found.')
            c.execute('UPDATE products SET '+','.join(f'{key}=?' for key in PRODUCT_FIELDS)+' WHERE id=?',tuple(values[k] for k in PRODUCT_FIELDS)+(pid,))
            from support import sizing
            for row in c.execute('SELECT * FROM size_measurements WHERE product_id=? AND estimated=1',(pid,)).fetchall():
                if all(abs(row[k]-v)<.01 for k,v in zip(sizing.FIELDS,sizing.grade(old,row['size']))):
                    c.execute('UPDATE size_measurements SET '+','.join(k+'=?' for k in sizing.FIELDS)+' WHERE product_id=? AND size=?',sizing.grade(values,row['size'])+(pid,row['size']))
        else:
            cur=c.execute('INSERT INTO products('+','.join(PRODUCT_FIELDS)+') VALUES('+','.join('?' for _ in PRODUCT_FIELDS)+')',tuple(values[k] for k in PRODUCT_FIELDS))
            pid=cur.lastrowid
            for color in [values['color']]:
                for size in db.SIZE_LABELS: c.execute('INSERT INTO variants(product_id,color,size,stock) VALUES(?,?,?,0)',(pid,color,size))
            stocks=initial_stocks if initial_stocks is not None else {initial_size:initial_stock}
            for size,quantity in stocks.items():c.execute('UPDATE variants SET stock=? WHERE product_id=? AND color=? AND size=?',(quantity,pid,values['color'],size))
        audit(c,actor,'product_saved',pid,values['code'])
        from support import sizing
        sizing.migrate(c)
    return pid

def set_stock(actor,vid,stock):
    if isinstance(stock,bool) or int(stock)!=stock or stock<0: raise ValueError('Stock must be a non-negative integer.')
    with transaction(actor) as c:
        old=c.execute('SELECT stock FROM variants WHERE id=?',(vid,)).fetchone()
        if not old: raise ValueError('Variant not found.')
        c.execute('UPDATE variants SET stock=? WHERE id=?',(int(stock),vid))
        audit(c,actor,'stock_updated',vid,f"{old['stock']} → {stock}")

def add_variant(actor,pid,color,size,stock):
    if size not in db.SIZE_LABELS or isinstance(size,bool): raise ValueError('Select a valid size.')
    if isinstance(stock,bool) or int(stock)!=stock or stock<0: raise ValueError('Stock must be a non-negative integer.')
    with transaction(actor) as c:
        p=c.execute('SELECT fit,color FROM products WHERE id=?',(pid,)).fetchone()
        if not p or color not in COLORS: raise ValueError('Choose a supported product color.')
        if c.execute('SELECT id FROM variants WHERE product_id=? AND color=? AND size=?',(pid,color,size)).fetchone():
            raise ValueError('This color and size already exist. Adjust its stock in the inventory table.')
        cur=c.execute('INSERT INTO variants(product_id,color,size,stock) VALUES(?,?,?,?)',(pid,color,size,int(stock)))
        audit(c,actor,'variant_added',cur.lastrowid,f'{pid} / {color} / {size} / {stock}')
        from support import sizing
        sizing.migrate(c)

def export_csv(actor,kind,path):
    queries={
        'orders': 'SELECT id,created_at,customer_name,phone,address,postal_code,subtotal,discount_amount,promo_day,promo_percent,redeemed_points,points_discount,total,payment_status,order_status,tracking FROM orders ORDER BY id DESC',
        'stock': 'SELECT p.code,p.name,v.color,v.size,v.stock,p.active FROM variants v JOIN products p ON p.id=v.product_id ORDER BY p.id,v.color,v.size',
        'customers': "SELECT id,first_name,last_name,email,created_at FROM users WHERE role='customer' ORDER BY id DESC",
        'audit': 'SELECT id,actor_id,action,target,detail,created_at FROM audit_log ORDER BY id DESC',
    }
    rows=query(actor,queries[kind])
    # Write headers even when the table has no rows.
    c=db.conn()
    try:
        require_admin(c,actor)
        headers=[col[0] for col in c.execute(queries[kind]).description]
    finally: c.close()
    with Path(path).open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.writer(f); writer.writerow(headers)
        for row in rows:
            writer.writerow([("'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@','\t','\r')) else v) for v in row.values()])
    with transaction(actor) as c: audit(c,actor,'export',kind,f'{len(rows)} rows')

def backup(actor,path):
    if Path(path).resolve()==Path(db.DB).resolve(): raise ValueError('Choose a different backup file.')
    c=db.conn()
    try:
        require_admin(c,actor)
        destination=sqlite3.connect(str(path))
        try: c.backup(destination)
        finally: destination.close()
    finally: c.close()
    with transaction(actor) as c: audit(c,actor,'backup','database','SQLite snapshot created')


def adjust_stock(actor, vid, quantity, mode):
    if isinstance(quantity,bool) or int(quantity)!=quantity or quantity<0:raise ValueError('Quantity must be a non-negative integer.')
    if mode not in ('add','remove','set'):raise ValueError('Invalid stock action.')
    with transaction(actor) as c:
        row=c.execute('SELECT stock FROM variants WHERE id=?',(vid,)).fetchone()
        if not row:raise ValueError('Variant not found.')
        stock=int(quantity) if mode=='set' else row['stock']+int(quantity)*(1 if mode=='add' else -1)
        if stock<0:raise ValueError('Cannot remove more than the available stock.')
        c.execute('UPDATE variants SET stock=? WHERE id=?',(stock,vid))
        audit(c,actor,'stock_'+mode,vid,f"{row['stock']} → {stock}")
    return stock
