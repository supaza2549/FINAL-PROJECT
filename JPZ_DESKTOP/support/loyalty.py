"""Persistent daily promotions and paid-order points, implemented in Python."""
from datetime import datetime, timezone, timedelta
import json
import secrets
from decimal import Decimal, ROUND_HALF_UP
import math
import db

DEFAULTS={'enabled':True,'percentages':[5,7,10],'minimum':500.0,'cap':200.0,'baht_per_point':100.0}

def thai_day():
    return datetime.now(timezone(timedelta(hours=7))).date().isoformat()

def migrate(c):
    for name,definition in [('postal_code',"TEXT DEFAULT ''"),('redeemed_points','INTEGER DEFAULT 0'),('points_discount','REAL DEFAULT 0'),('promo_minimum','REAL DEFAULT 0'),('promo_cap','REAL DEFAULT 0')]:
        db.add_column_if_missing(c,'orders',name,definition)
    for name,definition in [('subtotal','REAL DEFAULT 0'),('discount_amount','REAL DEFAULT 0'),
                            ('promo_day',"TEXT DEFAULT ''"),('promo_percent','INTEGER DEFAULT 0'),('reward_points','INTEGER DEFAULT 0')]:
        db.add_column_if_missing(c,'orders',name,definition)
    c.execute('UPDATE orders SET subtotal=total WHERE subtotal=0 AND total>0')
    c.execute('CREATE TABLE IF NOT EXISTS reward_settings(id INTEGER PRIMARY KEY CHECK(id=1),config TEXT NOT NULL)')
    c.execute('INSERT OR IGNORE INTO reward_settings VALUES(1,?)',(json.dumps(DEFAULTS),))
    c.execute('CREATE TABLE IF NOT EXISTS daily_promotions(day TEXT PRIMARY KEY,percent INTEGER,minimum REAL,cap REAL,enabled INTEGER)')
    c.execute("UPDATE orders SET promo_minimum=COALESCE((SELECT minimum FROM daily_promotions WHERE day=orders.promo_day),promo_minimum),promo_cap=COALESCE((SELECT cap FROM daily_promotions WHERE day=orders.promo_day),promo_cap) WHERE promo_cap=0 AND promo_day<>''")
    c.execute('CREATE TABLE IF NOT EXISTS points_ledger(id INTEGER PRIMARY KEY,user_id INTEGER,order_id INTEGER,kind TEXT,points INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(order_id,kind))')

def settings(c=None):
    if c is not None:
        config=json.loads(c.execute('SELECT config FROM reward_settings WHERE id=1').fetchone()['config'])
        config.setdefault('blocks',[dict(percent=v,minimum=config['minimum'],cap=config['cap']) for v in config['percentages']])
        return config
    connection=db.conn()
    try: return settings(connection)
    finally: connection.close()

def daily(c=None,day=None):
    if c is None:
        connection=db.conn()
        try:
            connection.execute('BEGIN IMMEDIATE')
            result=daily(connection,day)
            connection.commit()
            return result
        except Exception:
            connection.rollback(); raise
        finally: connection.close()
    day=day or thai_day()
    config=settings(c)
    row=c.execute('SELECT * FROM daily_promotions WHERE day=?',(day,)).fetchone()
    # Keep a valid selection for the day; saved edits must never advertise old terms.
    matches=row is not None and any(
        all(row[key]==block[key] for key in ('percent','minimum','cap'))
        for block in config['blocks'])
    if not row or (day==thai_day() and not matches):
        block=secrets.choice(config['blocks'])
        c.execute('INSERT OR REPLACE INTO daily_promotions(day,percent,minimum,cap,enabled) VALUES(?,?,?,?,?)',
                  (day,block['percent'],block['minimum'],block['cap'],int(config['enabled'])))
        row=c.execute('SELECT * FROM daily_promotions WHERE day=?',(day,)).fetchone()
    elif day==thai_day() and bool(row['enabled'])!=config['enabled']:
        c.execute('UPDATE daily_promotions SET enabled=? WHERE day=?',(int(config['enabled']),day))
        row=c.execute('SELECT * FROM daily_promotions WHERE day=?',(day,)).fetchone()
    result=dict(row)
    result['enabled']=bool(result['enabled'] and config['enabled'])
    return result

def calculate_discount(subtotal,percent,minimum,cap,enabled=True):
    values=(subtotal,percent,minimum,cap)
    if not all(math.isfinite(float(v)) and float(v)>=0 for v in values) or float(percent)>100:
        raise ValueError('Enter valid non-negative totals and a percentage up to 100.')
    amount=Decimal(str(subtotal)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    reduction=Decimal('0')
    if enabled and amount>=Decimal(str(minimum)):
        reduction=min(amount*Decimal(str(percent))/100,Decimal(str(cap)),amount).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    return {'subtotal':float(amount),'discount_amount':float(reduction),'total':float(amount-reduction)}

def quote(subtotal,c=None):
    promo=daily(c)
    totals=calculate_discount(subtotal,promo['percent'],promo['minimum'],promo['cap'],promo['enabled'])
    reduction=totals['discount_amount']
    return dict(totals,**{
            'promo_day':promo['day'] if reduction else '', 'promo_percent':promo['percent'] if reduction else 0,
            'reward_points':0})

def balance(user_id):
    c=db.conn()
    try: return c.execute('SELECT COALESCE(SUM(points),0) n FROM points_ledger WHERE user_id=?',(user_id,)).fetchone()['n']
    finally: c.close()

def history(user_id):
    c=db.conn()
    try: return [dict(r) for r in c.execute('SELECT * FROM points_ledger WHERE user_id=? ORDER BY id DESC LIMIT 8',(user_id,))]
    finally: c.close()

def award(c,order):
    if order['reward_points']>0:
        c.execute("INSERT OR IGNORE INTO points_ledger(user_id,order_id,kind,points) VALUES(?,?,'earned',?)",(order['user_id'],order['id'],order['reward_points']))

def reverse(c,order):
    row=c.execute("SELECT points FROM points_ledger WHERE order_id=? AND kind='earned'",(order['id'],)).fetchone()
    if row:
        c.execute("INSERT OR IGNORE INTO points_ledger(user_id,order_id,kind,points) VALUES(?,?,'refund',?)",(order['user_id'],order['id'],-row['points']))
    release(c,order)

def redeem_quote(subtotal,uid,points=0,c=None):
    if c is None:
        connection=db.conn()
        try:
            connection.execute('BEGIN IMMEDIATE')
            result=redeem_quote(subtotal,uid,points,connection)
            connection.commit()
            return result
        except Exception:connection.rollback();raise
        finally:connection.close()
    if points:raise ValueError('ระบบแต้มสะสมถูกยกเลิกแล้ว')
    totals=quote(subtotal,c)
    promo=daily(c)
    totals.update(redeemed_points=0,points_discount=0,max_points=0,reward_points=0,promo_minimum=promo['minimum'],promo_cap=promo['cap'])
    return totals

def reserve(c,uid,oid,points):
    if points:c.execute("INSERT INTO points_ledger(user_id,order_id,kind,points) VALUES(?,?,'redeemed',?)",(uid,oid,-points))

def release(c,order):
    row=c.execute("SELECT points FROM points_ledger WHERE order_id=? AND kind='redeemed'",(order['id'],)).fetchone()
    if row:c.execute("INSERT OR IGNORE INTO points_ledger(user_id,order_id,kind,points) VALUES(?,?,'returned',?)",(order['user_id'],order['id'],-row['points']))

def explanation():
    rate=settings()['baht_per_point']
    return (f'สะสมแต้ม: ทุกยอดชำระสุทธิครบ {rate:g} บาท รับ 1 แต้ม หลังร้านยืนยันการชำระเงิน เศษยอดที่ไม่ครบจะไม่นำมาคิดแต้ม\n'
            'ใช้แต้มเป็นส่วนลด: 1 แต้ม เท่ากับ 1 บาท ใช้ลดได้สูงสุด 20% ของยอดสินค้าหลังหักส่วนลดโปรโมชั่น\n'
            'เมื่อยืนยันคำสั่งซื้อ ระบบจะหักแต้มที่เลือกใช้ทันที หากยกเลิกคำสั่งซื้อหรือได้รับเงินคืน ระบบจะคืนแต้มที่ใช้ให้\n'
            'หากได้รับเงินคืน แต้มสะสมที่ได้รับจากคำสั่งซื้อนั้นจะถูกหักออกจากบัญชี',
            f'Earn 1 point per ฿{rate:g} of net payment, rounded down, after approval. 1 point = ฿1 discount, up to 20% after promotion. Points are reserved when ordered, returned on cancellation/refund; refunded orders lose earned points.')

def save_settings(actor,config):
    from support import admin_data as admin
    config=dict(config)
    if not isinstance(config['enabled'],bool): raise ValueError('Invalid enabled setting.')
    blocks=config.get('blocks')
    if blocks is not None:
        if not isinstance(blocks,list) or not blocks:raise ValueError('ต้องมีอย่างน้อย 1 บล็อก / Keep at least one block.')
        normalized=[]
        for block in blocks:
            rate=block['percent']
            if isinstance(rate,bool) or int(rate)!=rate or not 1<=rate<=50:
                raise ValueError('เปอร์เซ็นต์ต้องเป็นจำนวนเต็ม 1–50 / Percentage must be a whole number from 1 to 50.')
            minimum=float(block['minimum']);cap=float(block['cap'])
            if not math.isfinite(minimum) or minimum<0 or not math.isfinite(cap) or cap<=0:
                raise ValueError('ขั้นต่ำต้องไม่ติดลบและเพดานต้องมากกว่า 0 / Minimum must be non-negative and cap positive.')
            normalized.append(dict(percent=int(rate),minimum=minimum,cap=cap))
        config['blocks']=normalized
        config.update(percentages=[v['percent'] for v in normalized],minimum=normalized[0]['minimum'],cap=normalized[0]['cap'])
    if not config['percentages'] or any(isinstance(v,bool) or int(v)!=v or not 1<=v<=50 for v in config['percentages']):
        raise ValueError('Discount percentages must be whole numbers between 1 and 50.')
    config['percentages']=sorted(set(int(v) for v in config['percentages']))
    for key in ('minimum','cap','baht_per_point'):
        config[key]=float(config[key])
        if not math.isfinite(config[key]) or config[key]<0 or (key!='minimum' and config[key]<=0):
            raise ValueError('Minimum must be non-negative; cap and points rate must be positive.')
    with admin.transaction(actor) as c:
        c.execute('UPDATE reward_settings SET config=? WHERE id=1',(json.dumps(config),))
        daily(c)  # Refresh today's conditions atomically with the saved blocks.
        admin.audit(c,actor,'reward_settings','shop',json.dumps(config))
