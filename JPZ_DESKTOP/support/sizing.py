"""Per-model, per-size garment measurements. Seed values are estimates, never measurements from photos."""
import math
from contextlib import nullcontext
import db
FIELDS=('waist','hip','thigh','rise','inseam','leg_opening')
# JPZ garment templates at W32. Body-size chart reference: Levi's men's
# bottoms (waist/seat/thigh); ease, rise, hem and length are JPZ fit choices,
# not ISO-prescribed garment measurements or measurements of actual stock.
FIT_BASES={
 'skinny':(32,39.5,23,10.5,31.5,12),
 'straight':(32,41,24.5,11.5,32,16),
 'baggy':(32,44,28,13,32,21),
 'wide':(32,43.5,27,12.5,32,23),
 'loose':(32,43,26.5,12.5,32,20.5),
 'relaxed':(32,42,25.5,12,32,18),
 'flare':(32,41.5,25,11,33,24),
 'bootcut':(32,41,24.5,11.5,33,20),
 'cargo':(32,44,28,13,32,20),
 'wide_straight':(32,43.5,27,12.5,32,21.5),
}

def reference_base(fit):return dict(zip(FIELDS,FIT_BASES.get(fit,FIT_BASES['straight'])))

def grade(base,size):
    d=size-32
    return tuple(round(float(base[k])+d*factor,2) for k,factor in zip(FIELDS,(1,1,.5,.125,0,.25)))
def migrate(c):
    c.execute('CREATE TABLE IF NOT EXISTS size_measurements(product_id INTEGER,size INTEGER,waist REAL,hip REAL,thigh REAL,rise REAL,inseam REAL,leg_opening REAL,estimated INTEGER DEFAULT 1,PRIMARY KEY(product_id,size))')
    if not c.execute("SELECT 1 FROM shop_metadata WHERE key='jpz_fit_size_templates_v1'").fetchone():
        for p in c.execute('SELECT * FROM products').fetchall():
            base=reference_base(p['fit'])
            # Preserve recorded measurements and manually edited size tables.
            edited=c.execute("SELECT 1 FROM audit_log WHERE action='size_measurements' AND target=?",(str(p['id']),)).fetchone()
            if edited:continue
            for row in c.execute('SELECT * FROM size_measurements WHERE product_id=? AND estimated=1',(p['id'],)).fetchall():
                c.execute('UPDATE size_measurements SET '+','.join(k+'=?' for k in FIELDS)+' WHERE product_id=? AND size=?',grade(base,row['size'])+(p['id'],row['size']))
            measured=c.execute('SELECT 1 FROM size_measurements WHERE product_id=? AND size=32 AND estimated=0',(p['id'],)).fetchone()
            if not measured:c.execute('UPDATE products SET '+','.join(k+'=?' for k in FIELDS)+' WHERE id=?',tuple(base[k] for k in FIELDS)+(p['id'],))
        c.execute("INSERT INTO shop_metadata VALUES('jpz_fit_size_templates_v1','1')")
    for p in c.execute('SELECT * FROM products').fetchall():
        for v in c.execute('SELECT DISTINCT size FROM variants WHERE product_id=?',(p['id'],)).fetchall():
            size=v['size']
            values=grade(p,size)
            c.execute('INSERT OR IGNORE INTO size_measurements VALUES(?,?,?,?,?,?,?,?,1)',(p['id'],size)+values)
def rows(pid):
    c=db.conn()
    try:return [dict(r) for r in c.execute('SELECT * FROM size_measurements WHERE product_id=? ORDER BY size',(pid,))]
    finally:c.close()
def for_size(p,size):
    row=next((r for r in rows(p['id']) if r['size']==size),None)
    return row or dict(p,size=size,estimated=1)
def candidates(products):
    result=[]
    c=db.conn()
    try:
        published={}
        for row in c.execute('SELECT product_id,color FROM product_gallery GROUP BY product_id,color HAVING COUNT(DISTINCT view)=4'):
            published.setdefault(row['product_id'],set()).add(row['color'])
    finally:c.close()
    for p in products:
        variants=[v for v in db.variants(p['id']) if v['stock']>0 and v['color'] in published.get(p['id'],set())]
        available={v['size'] for v in variants}
        for r in rows(p['id']):
            if r['size'] in available:
                color=next((v['color'] for v in variants if v['size']==r['size'] and v['color']==p['color']),next(v['color'] for v in variants if v['size']==r['size']))
                result.append(dict(p,**{k:r[k] for k in FIELDS},color=color,recommended_size=r['size'],estimated=r['estimated']))
    return result
def save(actor,pid,size,values,estimated,connection=None):
    from support import admin_data
    nums=[float(values[k]) for k in FIELDS]
    if not all(math.isfinite(v) and 0<v<=100 for v in nums):raise ValueError('Measurements must be positive inches, at most 100.')
    with (nullcontext(connection) if connection is not None else admin_data.transaction(actor)) as c:
        admin_data.require_admin(c,actor)
        if not c.execute('SELECT 1 FROM variants WHERE product_id=? AND size=?',(pid,size)).fetchone():raise ValueError('Product size not found.')
        c.execute('INSERT INTO size_measurements VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(product_id,size) DO UPDATE SET '+','.join(k+'=excluded.'+k for k in FIELDS)+',estimated=excluded.estimated',(pid,size,*nums,int(bool(estimated))))
        admin_data.audit(c,actor,'size_measurements',pid,f'size {size}; estimated={bool(estimated)}')
