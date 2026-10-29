"""Database-backed categories, gallery assets and protected product removal."""
import json
import sqlite3
import shutil
import uuid
from pathlib import Path
import db

CATEGORY_SEEDS=[('Everyday Denim','เดนิมใส่ทุกวัน'),('Wide & Baggy','ทรงกว้าง / แบ็กกี้'),
                ('Vintage & Flare','วินเทจ / ขาม้า'),('Utility Cargo','คาร์โก้'),('Slim Fit','ทรงเข้ารูป')]

def migrate(c):
    db.add_column_if_missing(c,'products','design',"TEXT DEFAULT ''")
    db.add_column_if_missing(c,'products','design_th',"TEXT DEFAULT ''")
    db.add_column_if_missing(c,'products','category_id','INTEGER')
    c.execute('CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY,name TEXT UNIQUE NOT NULL,name_th TEXT NOT NULL,active INTEGER DEFAULT 1)')
    c.execute('CREATE TABLE IF NOT EXISTS product_gallery(id INTEGER PRIMARY KEY,product_id INTEGER,color TEXT,path TEXT,view TEXT,cell INTEGER,generated INTEGER DEFAULT 1,UNIQUE(product_id,color,view))')
    if not c.execute("SELECT value FROM shop_metadata WHERE key='categories_installed'").fetchone():
        for en,th in CATEGORY_SEEDS:c.execute('INSERT OR IGNORE INTO categories(name,name_th) VALUES(?,?)',(en,th))
        c.execute("INSERT OR IGNORE INTO shop_metadata VALUES('categories_installed','1')")
    install(c)

def install(c):
    install_expanded(c)
    default_map={'baggy':'Wide & Baggy','wide':'Wide & Baggy','wide_straight':'Wide & Baggy',
                 'flare':'Vintage & Flare','bootcut':'Vintage & Flare','cargo':'Utility Cargo','skinny':'Slim Fit'}
    if not c.execute("SELECT value FROM shop_metadata WHERE key='category_assignments_installed'").fetchone():
        products=c.execute('SELECT id,fit FROM products WHERE category_id IS NULL').fetchall()
        for p in products:
            category=c.execute('SELECT id FROM categories WHERE name=?',(default_map.get(p['fit'],'Everyday Denim'),)).fetchone()
            if category:c.execute('UPDATE products SET category_id=? WHERE id=?',(category['id'],p['id']))
        if products:c.execute("INSERT OR IGNORE INTO shop_metadata VALUES('category_assignments_installed','1')")
    manifest=Path(db.BASE_DIR)/'assets'/'products'/'gallery_manifest.json'
    if not manifest.exists():return
    for item in json.loads(manifest.read_text(encoding='utf-8')):
        product=c.execute('SELECT id,color,name FROM products WHERE code=?',(item['code'],)).fetchone()
        if not product:continue
        if item.get('name') and item['name'] != product['name']:continue
        if item['color']==product['color']:
            for size in (28,30,32,34,36):
                c.execute('INSERT OR IGNORE INTO variants(product_id,color,size,stock) VALUES(?,?,?,0)',(product['id'],item['color'],size))
        for cell,view in enumerate(('FRONT','BACK','DETAIL','TEXTURE')):
            c.execute('INSERT OR IGNORE INTO product_gallery(product_id,color,path,view,cell,generated) VALUES(?,?,?,?,?,1)',
                      (product['id'],item['color'],item['path'],view,cell))

def categories(include_hidden=False):
    c=db.conn()
    try:return [dict(r) for r in c.execute('SELECT * FROM categories'+('' if include_hidden else ' WHERE active=1')+' ORDER BY name')]
    finally:c.close()

def gallery(pid,color):
    c=db.conn()
    try:return [dict(r) for r in c.execute('SELECT * FROM product_gallery WHERE product_id=? AND color=? ORDER BY cell',(pid,color))]
    finally:c.close()

def set_image(actor,pid,color,view,source):
    from support import admin_data as admin
    from PIL import Image
    if view not in ('FRONT','BACK','DETAIL','TEXTURE'):raise ValueError('Unknown gallery view.')
    source=Path(source)
    if source.suffix.lower() not in ('.png','.jpg','.jpeg','.webp'):raise ValueError('Choose a PNG, JPEG or WebP image.')
    with Image.open(source) as image:image.verify()
    with admin.transaction(actor) as c:
        if not c.execute('SELECT id FROM variants WHERE product_id=? AND color=?',(pid,color)).fetchone():raise ValueError('Choose an existing product color.')
        relative=Path('assets')/'products'/f'uploaded_{uuid.uuid4().hex}{source.suffix.lower()}'
        destination=Path(db.BASE_DIR)/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,destination)
        c.execute('INSERT INTO product_gallery(product_id,color,path,view,cell,generated) VALUES(?,?,?,?,-1,0) ON CONFLICT(product_id,color,view) DO UPDATE SET path=excluded.path,cell=-1,generated=0',
                  (pid,color,relative.as_posix(),view))
        admin.audit(c,actor,'gallery_uploaded',pid,f'{color} / {view}')

def save_product_with_images(actor,values,images,pid=None,stocks=None,measurements=None):
    """Save the form, initial stock and selected pictures as one transaction."""
    from support import admin_data as admin
    from PIL import Image,ImageOps
    c=db.conn()
    try:admin.require_admin(c,actor)
    finally:c.close()
    staged={}
    try:
        for view,source in images.items():
            if view not in ('FRONT','BACK','DETAIL','TEXTURE'):raise ValueError('Invalid product image view.')
            relative=Path('assets/products')/('uploaded_'+uuid.uuid4().hex+'.png')
            destination=Path(db.BASE_DIR)/relative;destination.parent.mkdir(parents=True,exist_ok=True)
            staged[view]=(relative,destination)
            try:
                with Image.open(source) as original:
                    image=ImageOps.exif_transpose(original).convert('RGB');image.thumbnail((2400,3200));image.save(destination)
            except (OSError,ValueError,Image.DecompressionBombError):raise ValueError('เปิดรูปสินค้าไม่ได้ กรุณาเลือก JPG, PNG หรือ WebP ที่ถูกต้อง / Cannot open the product photo.') from None
        with admin.transaction(actor) as c:
            pid=admin.save_product(actor,values,pid,initial_stocks=stocks,connection=c)
            from support import sizing
            for size,row in (measurements or {}).items():
                sizing.save(actor,pid,size,row,row.get('estimated',True),connection=c)
            for view,(relative,destination) in staged.items():
                c.execute('INSERT INTO product_gallery(product_id,color,path,view,cell,generated) VALUES(?,?,?,?,-1,0) ON CONFLICT(product_id,color,view) DO UPDATE SET path=excluded.path,cell=-1,generated=0',(pid,values['color'],relative.as_posix(),view))
                admin.audit(c,actor,'gallery_uploaded',pid,values['color']+' / '+view)
        return pid
    except Exception:
        for relative,destination in staged.values():destination.unlink(missing_ok=True)
        raise

def save_category(actor,name,name_th,active=1,cid=None):
    from support import admin_data as admin
    name,name_th=name.strip(),name_th.strip()
    if not name or not name_th:raise ValueError('Thai and English category names are required.')
    if active not in (0,1):raise ValueError('Invalid visibility.')
    with admin.transaction(actor) as c:
        if cid:
            if not c.execute('SELECT id FROM categories WHERE id=?',(cid,)).fetchone():raise ValueError('Category not found.')
            c.execute('UPDATE categories SET name=?,name_th=?,active=? WHERE id=?',(name,name_th,active,cid))
        else:
            cid=c.execute('INSERT INTO categories(name,name_th,active) VALUES(?,?,?)',(name,name_th,active)).lastrowid
        admin.audit(c,actor,'category_saved',cid,name)
    return cid

def delete_category(actor,cid):
    from support import admin_data as admin
    with admin.transaction(actor) as c:
        if c.execute('SELECT id FROM products WHERE category_id=?',(cid,)).fetchone():
            raise ValueError('Move products to another category before deleting this category.')
        if not c.execute('DELETE FROM categories WHERE id=?',(cid,)).rowcount:raise ValueError('Category not found.')
        admin.audit(c,actor,'category_deleted',cid,'Unused category removed')

def set_product_visibility(actor,pid,active):
    from support import admin_data as admin
    if active not in (0,1):raise ValueError('Invalid visibility.')
    with admin.transaction(actor) as c:
        product=c.execute('SELECT code FROM products WHERE id=?',(pid,)).fetchone()
        if not product:raise ValueError('Product not found.')
        c.execute('UPDATE products SET active=? WHERE id=?',(active,pid))
        admin.audit(c,actor,'product_shown' if active else 'product_hidden',pid,product['code'])

def delete_product(actor,pid):
    from support import admin_data as admin
    with admin.transaction(actor) as c:
        product=c.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
        if not product:raise ValueError('Product not found.')
        if c.execute('SELECT id FROM order_items WHERE product_id=?',(pid,)).fetchone():
            raise ValueError('สินค้ามีประวัติคำสั่งซื้อ กรุณาใช้ซ่อนสินค้า / This product has order history. Use Hide product.')
        for table in ('variants','favorites','recently_viewed','product_gallery','size_measurements'):
            c.execute(f'DELETE FROM {table} WHERE product_id=?',(pid,))
        c.execute('DELETE FROM products WHERE id=?',(pid,))
        admin.audit(c,actor,'product_deleted',pid,product['code'])
    return 'deleted'

def remove_product(actor,pid):
    return delete_product(actor,pid)

TABLES=('categories','products','variants','size_measurements','users','orders','order_items','payments','daily_promotions','points_ledger','events','audit_log')

def browse(actor,table,term='',page=0,size=100):
    from support import admin_data as admin
    if table not in TABLES:raise ValueError('Unsupported table.')
    c=db.conn()
    try:
        admin.require_admin(c,actor)
        columns=[r['name'] for r in c.execute(f'PRAGMA table_info({table})') if r['name']!='password_hash']
        quoted=['"'+name.replace('"','""')+'"' for name in columns]
        where='';args=[]
        if term:
            where=' WHERE '+' OR '.join(f'CAST({name} AS TEXT) LIKE ? ESCAPE \'\\\'' for name in quoted)
            needle='%'+term.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
            args=[needle]*len(columns)
        total=c.execute(f'SELECT COUNT(*) FROM {table}'+where,args).fetchone()[0]
        page=max(0,min(int(page),max(0,(total-1)//size)))
        rows=[dict(r) for r in c.execute('SELECT '+','.join(quoted)+f' FROM {table}'+where+' ORDER BY rowid DESC LIMIT ? OFFSET ?',args+[size,page*size])]
        return columns,rows,total,page
    finally:c.close()


def install_expanded(c):
    """Install the expanded collection once; never resurrect deleted products."""
    if not c.execute('SELECT 1 FROM products LIMIT 1').fetchone():return
    marker='jpz_collection_100_v2'
    if c.execute('SELECT 1 FROM shop_metadata WHERE key=?',(marker,)).fetchone():return
    manifest=Path(db.BASE_DIR)/'assets/products/expanded_catalogue.json'
    if not manifest.is_file():return
    default_map={'baggy':'Wide & Baggy','wide':'Wide & Baggy','wide_straight':'Wide & Baggy','flare':'Vintage & Flare','bootcut':'Vintage & Flare','cargo':'Utility Cargo','skinny':'Slim Fit'}
    fields=('name','code','price','fit','style','color','waist','hip','thigh','rise','inseam','leg_opening','design','design_th')
    for item in json.loads(manifest.read_text(encoding='utf-8')):
        item.setdefault('design','');item.setdefault('design_th','')
        if item['code'].startswith('JPZ-') and not item['code'].startswith('JPZ-X') and c.execute("SELECT 1 FROM shop_metadata WHERE key='jpz_collection_40_v1'").fetchone():continue
        existing=c.execute('SELECT id FROM products WHERE code=?',(item['code'],)).fetchone()
        if existing:continue
        category=c.execute('SELECT id FROM categories WHERE name=?',(default_map.get(item['fit'],'Everyday Denim'),)).fetchone()
        cur=c.execute('INSERT INTO products('+','.join(fields)+',active,category_id) VALUES('+','.join('?' for _ in range(len(fields)+2))+')',tuple(item[k] for k in fields)+(1,category['id'] if category else None))
        pid=cur.lastrowid
        for size in (28,30,32,34,36):
            c.execute('INSERT INTO variants(product_id,color,size,stock) VALUES(?,?,?,?)',(pid,item['color'],size,item.get('initial_stock',5)))
    c.execute('INSERT INTO shop_metadata VALUES(?,?)',(marker,'1'))
