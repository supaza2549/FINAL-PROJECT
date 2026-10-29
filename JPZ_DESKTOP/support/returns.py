"""Customer return requests and refund account details; no money transfers."""
import json
import db

def migrate(c):
    for table in ('users','orders'):
        for key in ('refund_bank','refund_name','refund_account'):
            db.add_column_if_missing(c,table,key,"TEXT DEFAULT ''")
    c.execute("CREATE TABLE IF NOT EXISTS return_requests(id INTEGER PRIMARY KEY,order_id INTEGER UNIQUE,user_id INTEGER,reason TEXT,items TEXT,bank TEXT,account_name TEXT,account_number TEXT,status TEXT DEFAULT 'pending',admin_note TEXT DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")

def bank_details(values,required=False):
    values=values or {};clean={k:str(values.get(k,'')).strip() for k in ('bank','name','account')}
    if required or any(clean.values()):
        if not all(clean.values()):raise ValueError('กรอกธนาคาร ชื่อบัญชี และเลขบัญชีให้ครบ / Complete all refund account fields.')
        if not clean['account'].isascii() or not clean['account'].isdigit() or not 6<=len(clean['account'])<=20:
            raise ValueError('เลขบัญชีต้องเป็นตัวเลข 6–20 หลัก / Account number must contain 6–20 digits.')
    return clean

def for_customer(uid,oid):
    c=db.conn()
    try:
        if not c.execute('SELECT id FROM orders WHERE id=? AND user_id=?',(oid,uid)).fetchone():raise PermissionError('Order unavailable.')
        row=c.execute('SELECT * FROM return_requests WHERE order_id=? AND user_id=?',(oid,uid)).fetchone()
        return dict(row) if row else None
    finally:c.close()

def submit(uid,oid,reason,quantities,account):
    clean=bank_details(account,True)
    if not str(reason).strip():raise ValueError('กรอกเหตุผลที่ต้องการคืนสินค้า / Enter the reason for your return.')
    c=db.conn()
    try:
        c.execute('BEGIN IMMEDIATE')
        if not c.execute("SELECT id FROM orders WHERE id=? AND user_id=? AND payment_status='paid' AND order_status IN ('preparing','shipped','completed')",(oid,uid)).fetchone():raise PermissionError('คำสั่งซื้อนี้ไม่สามารถส่งคำขอคืนได้ / Return unavailable for this order.')
        old=c.execute('SELECT * FROM return_requests WHERE order_id=?',(oid,)).fetchone()
        if old and old['status'] not in ('pending','rejected'):raise ValueError('ร้านรับคำขอนี้แล้ว กรุณาติดต่อร้านเพื่อแก้ไข / Contact the store to amend an accepted request.')
        items={r['id']:dict(r) for r in c.execute('SELECT * FROM order_items WHERE order_id=?',(oid,))};selected=[]
        for item_id,qty in quantities.items():
            if item_id not in items or isinstance(qty,bool) or not isinstance(qty,int) or not 0<=qty<=items[item_id]['quantity']:raise ValueError('จำนวนคืนต้องไม่เกินจำนวนที่ซื้อ / Return quantity exceeds purchased quantity.')
            if qty:selected.append(dict(item_id=item_id,quantity=qty,name=items[item_id].get('product_name') or '',color=items[item_id]['color'],size=items[item_id]['size']))
        if not selected:raise ValueError('เลือกจำนวนสินค้าที่ต้องการคืน / Select at least one item to return.')
        c.execute("INSERT INTO return_requests(order_id,user_id,reason,items,bank,account_name,account_number) VALUES(?,?,?,?,?,?,?) ON CONFLICT(order_id) DO UPDATE SET reason=excluded.reason,items=excluded.items,bank=excluded.bank,account_name=excluded.account_name,account_number=excluded.account_number,status='pending',admin_note='',updated_at=CURRENT_TIMESTAMP",(oid,uid,str(reason).strip(),json.dumps(selected),clean['bank'],clean['name'],clean['account']))
        c.execute("UPDATE users SET refund_bank=?,refund_name=?,refund_account=? WHERE id=?",(clean['bank'],clean['name'],clean['account'],uid))
        c.execute("INSERT INTO events(user_id,kind,target) VALUES(?,'return_requested',?)",(uid,str(oid)));c.commit()
    except Exception:c.rollback();raise
    finally:c.close()

def review(actor,oid,status,note=''):
    from support import admin_data
    if status not in ('approved','rejected'):raise ValueError('Invalid return status.')
    with admin_data.transaction(actor) as c:
        row=c.execute('SELECT * FROM return_requests WHERE order_id=?',(oid,)).fetchone()
        if not row or row['status']=='refunded':raise ValueError('Request unavailable or already refunded.')
        c.execute('UPDATE return_requests SET status=?,admin_note=?,updated_at=CURRENT_TIMESTAMP WHERE order_id=?',(status,note.strip(),oid))
        admin_data.audit(c,actor,'return_'+status,oid,note.strip())
