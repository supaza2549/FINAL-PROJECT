"""Atomic inline product, offer and size-stock editing for the admin workspace."""
import db
from support import admin_data,product_promotions

LOW_STOCK_LIMIT=5

def stock_alerts(connection,products):
    """One read for all configured color/size variants; absent sizes count as zero."""
    grouped={}
    from support import product_colors
    for row in connection.execute('SELECT product_id,color,size,stock FROM variants'):
        if not product_colors.active(connection,row['product_id'],row['color']):continue
        if row['size'] in db.SIZE_LABELS:
            grouped.setdefault(row['product_id'],{}).setdefault(row['color'],{})[row['size']]=row['stock']
    result={}
    for product in products:
        colors=grouped.get(product['id'],{})
        if not colors and product_colors.active(connection,product['id'],product['color']):colors={product['color']:{}}
        quantities=[counts.get(size,0) for counts in colors.values() for size in db.SIZE_LABELS]
        result[product['id']]=dict(low_count=sum(n<LOW_STOCK_LIMIT for n in quantities),out_count=sum(n==0 for n in quantities),minimum=min(quantities,default=0))
        result[product['id']]['colors']={}
        for color,counts in colors.items():
            quantities=[counts.get(size,0) for size in db.SIZE_LABELS]
            result[product['id']]['colors'][color]=dict(low_count=sum(n<LOW_STOCK_LIMIT for n in quantities),out_count=sum(n==0 for n in quantities),minimum=min(quantities))
    return result

def save(actor,product,values,offer,color,counts,baseline):
    if set(counts)!=set(db.SIZE_LABELS):raise ValueError('กรอกจำนวนให้ครบทุกไซซ์ / Fill every size.')
    for value in counts.values():
        if not isinstance(value,int) or isinstance(value,bool) or value<0:raise ValueError('สต็อกต้องเป็นจำนวนเต็มตั้งแต่ 0 / Stock must be a non-negative integer.')
    with admin_data.transaction(actor) as c:
        from support import product_colors
        if color not in product_colors.keys(product['id'],c):raise ValueError('สีนี้ไม่มีในสินค้าแล้ว กรุณาโหลดใหม่ / Color removed; reload the product.')
        current=c.execute('SELECT * FROM products WHERE id=?',(product['id'],)).fetchone()
        if not current:raise ValueError('ไม่พบสินค้า / Product not found.')
        if any(current[key]!=product[key] for key in admin_data.PRODUCT_FIELDS if key in product):raise ValueError('สินค้าเปลี่ยนแล้ว กรุณาโหลดใหม่ก่อนบันทึก / Product changed; reload before saving.')
        rows={r['size']:dict(r) for r in c.execute('SELECT id,size,stock FROM variants WHERE product_id=? AND color=?',(product['id'],color))}
        if {key:rows[key]['stock'] for key in rows}!=baseline:raise ValueError('สต็อกเปลี่ยนแล้ว กรุณาโหลดใหม่ก่อนบันทึก / Stock changed; reload before saving.')
        admin_data.save_product(actor,values,product['id'],connection=c)
        product_promotions.save(actor,product['id'],offer['kind'],offer['value'],offer['enabled'],connection=c)
        for size,stock in counts.items():
            if size in rows:
                c.execute('UPDATE variants SET stock=? WHERE id=?',(stock,rows[size]['id']))
            else:c.execute('INSERT INTO variants(product_id,color,size,stock) VALUES(?,?,?,?)',(product['id'],color,size,stock))
        admin_data.audit(c,actor,'inventory_saved',product['id'],color+' / '+', '.join(f'{db.size_label(size)}:{stock}' for size,stock in counts.items()))
        from support import sizing
        sizing.migrate(c)
