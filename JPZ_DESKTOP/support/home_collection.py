"""Editable product cards for the homepage 02 / NEW DENIM section."""
import json
from pathlib import Path
from PIL import Image
import db
from support import admin_data,gallery


def settings():
    c=db.conn()
    try:
        row=c.execute("SELECT value FROM shop_metadata WHERE key='home_collection_cards'").fetchone()
        if row:return json.loads(row['value'])
        products=db.products();cards=[]
        for fit,title,file in [('baggy','BAGGY DENIM','baggy'),('straight','STRAIGHT DENIM','straight'),('wide','WIDE DENIM','wide'),('cargo','CARGO DENIM','cargo')]:
            product=next((p for p in products if p['fit']==fit),None)
            if product:cards.append(dict(product_id=product['id'],title=title,photo=f'assets/home_prod_{file}.png'))
        return cards
    finally:c.close()


def save(actor,cards):
    clean=[]
    with admin_data.transaction(actor) as c:
        for card in cards:
            pid=card.get('product_id');photo=card.get('photo','');title=str(card.get('title','')).strip()
            if not c.execute('SELECT id FROM products WHERE id=? AND active=1',(pid,)).fetchone():
                raise ValueError('เลือกสินค้าที่เปิดขายให้ครบทุกการ์ด / Select an active product for every card.')
            if len(title)>120:raise ValueError('ชื่อบนการ์ดยาวเกิน 120 ตัว / Card title exceeds 120 characters.')
            if photo:
                path=(db.BASE_DIR/photo).resolve()
                if Path(photo).is_absolute() or not path.is_relative_to(db.BASE_DIR.resolve()) or not path.is_file():raise ValueError('ไม่พบรูปการ์ด / Card image unavailable.')
                with Image.open(path) as image:image.verify()
            clean.append(dict(product_id=pid,title=title,photo=photo))
        c.execute("INSERT INTO shop_metadata VALUES('home_collection_cards',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(json.dumps(clean,ensure_ascii=False),))
        admin_data.audit(c,actor,'home_collection_updated','02_NEW_DENIM',f'{len(clean)} cards')
    return clean


def picture(card):
    photo=card.get('photo','')
    if photo:
        path=(db.BASE_DIR/photo).resolve()
        if path.is_relative_to(db.BASE_DIR.resolve()) and path.is_file():
            with Image.open(path) as image:return image.convert('RGB')
    product=db.product(card.get('product_id'))
    if product:return gallery.source(product['id'],product['color'],'FRONT',fallback=True)
    return None


def visible():
    result=[]
    for card in settings():
        product=db.product(card['product_id'])
        if product and product.get('active',1):result.append((card,product))
    return result
