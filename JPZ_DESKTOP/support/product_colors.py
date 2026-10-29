"""Product-specific colors. Hiding retains stock and historical order references."""
import uuid
import db

def migrate(c):
    c.execute('CREATE TABLE IF NOT EXISTS custom_colors(key TEXT PRIMARY KEY,name TEXT NOT NULL UNIQUE)')
    c.execute('CREATE TABLE IF NOT EXISTS product_color_hidden(product_id INTEGER,color TEXT,PRIMARY KEY(product_id,color))')

def active(c,pid,color):
    if not c.execute("SELECT name FROM sqlite_master WHERE name='product_color_hidden'").fetchone():return True
    return not c.execute('SELECT 1 FROM product_color_hidden WHERE product_id=? AND color=?',(pid,color)).fetchone()

def keys(pid,c=None):
    if c is None:
        c=db.conn()
        try:return keys(pid,c)
        finally:c.close()
    return [r['color'] for r in c.execute('SELECT DISTINCT color FROM variants WHERE product_id=? ORDER BY color',(pid,)) if active(c,pid,r['color'])]

def custom_name(key):
    if not str(key).startswith('custom_'):return None
    c=db.conn()
    try:
        row=c.execute('SELECT name FROM custom_colors WHERE key=?',(key,)).fetchone()
        return row['name'] if row else key
    finally:c.close()

def supported(c,key):
    from support.admin_data import COLORS
    return key in COLORS or bool(c.execute('SELECT 1 FROM custom_colors WHERE key=?',(key,)).fetchone())

def add(actor,pid,name=None,key=None):
    from support import admin_data
    with admin_data.transaction(actor) as c:
        migrate(c)
        if not c.execute('SELECT 1 FROM products WHERE id=?',(pid,)).fetchone():raise ValueError('ไม่พบสินค้า / Product not found.')
        if key is None:
            name=(name or '').strip()
            if not name or len(name)>60 or any(ord(ch)<32 for ch in name):raise ValueError('กรอกชื่อสี 1–60 ตัวอักษร / Enter a color name of 1–60 characters.')
            row=next((r for r in c.execute('SELECT * FROM custom_colors') if r['name'].casefold()==name.casefold()),None)
            key=row['key'] if row else 'custom_'+uuid.uuid4().hex
            if not row:c.execute('INSERT INTO custom_colors VALUES(?,?)',(key,name))
        if not supported(c,key):raise ValueError('สีไม่ถูกต้อง / Invalid color.')
        if key in keys(pid,c):raise ValueError('สินค้ามีสีนี้แล้ว / This product already has this color.')
        c.execute('DELETE FROM product_color_hidden WHERE product_id=? AND color=?',(pid,key))
        for size in db.SIZE_LABELS:c.execute('INSERT OR IGNORE INTO variants(product_id,color,size,stock) VALUES(?,?,?,0)',(pid,key,size))
        primary=c.execute('SELECT color FROM products WHERE id=?',(pid,)).fetchone()['color']
        if not active(c,pid,primary):c.execute('UPDATE products SET color=? WHERE id=?',(key,pid))
        admin_data.audit(c,actor,'product_color_added',pid,key)
        return key

def remove(actor,pid,key):
    from support import admin_data
    with admin_data.transaction(actor) as c:
        migrate(c);remaining=[k for k in keys(pid,c) if k!=key]
        if not active(c,pid,key):raise ValueError('สีนี้ถูกลบแล้ว / Color already removed.')
        c.execute('INSERT OR IGNORE INTO product_color_hidden VALUES(?,?)',(pid,key))
        if remaining:c.execute('UPDATE products SET color=? WHERE id=? AND color=?',(remaining[0],pid,key))
        admin_data.audit(c,actor,'product_color_removed',pid,key+' (stock and orders retained)')
        return remaining[0] if remaining else None
