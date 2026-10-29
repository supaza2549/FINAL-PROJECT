"""วาดใบเสร็จภาษาไทยเป็นภาพและ PDF ขนาด A4 ด้วย Pillow ที่โปรแกรมใช้อยู่"""
from pathlib import Path
import os, tempfile, unicodedata
from PIL import Image, ImageDraw, ImageFont
import db
import receipt


def receipt_data(uid,oid):
    c=db.conn()
    try:
        c.execute('BEGIN')
        order=c.execute("SELECT * FROM orders WHERE id=? AND user_id=? AND payment_status='paid'",(oid,uid)).fetchone()
        if order is None:
            raise PermissionError('ใบเสร็จใช้ได้เฉพาะคำสั่งซื้อของคุณที่ยืนยันชำระแล้ว / Receipt requires your own approved payment.')
        items=[dict(r) for r in c.execute('SELECT * FROM order_items WHERE order_id=? ORDER BY id',(oid,))]
        return dict(order),items
    finally:c.close()


# J31 | สร้างภาพใบเสร็จ
def render_pages(uid,oid):
    order,items=receipt_data(uid,oid)
    from support import order_amounts,product_colors
    from support.language import option_name
    items=order_amounts.lines(items,order['total'])
    fonts=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
    regular=fonts/'tahoma.ttf';bold=fonts/'tahomabd.ttf'
    if not regular.is_file() or not bold.is_file():
        raise OSError('ไม่พบฟอนต์ Tahoma สำหรับใบเสร็จภาษาไทย / Tahoma font unavailable.')
    font=ImageFont.truetype(str(regular),42);small=ImageFont.truetype(str(regular),34)
    strong=ImageFont.truetype(str(bold),42);title=ImageFont.truetype(str(bold),68)
    brand=ImageFont.truetype(str(bold),100)
    width,height=2480,3508;margin=170;right=width-margin;bottom=height-210
    pages=[];page=None;draw=None;y=0;navy='#243E55';muted='#5D6975'
    def new_page():
        nonlocal page,draw,y
        page=Image.new('RGB',(width,height),'white');pages.append(page);draw=ImageDraw.Draw(page)
        draw.text((margin,100),'JPZ.',font=brand,fill=navy)
        draw.text((right,152),'PIZZA JEANS / DENIM MADE PERSONAL.',font=small,fill=muted,anchor='ra')
        draw.line((margin,260,right,260),fill=navy,width=5)
        draw.text((margin,300),'ใบเสร็จรับเงิน / RECEIPT',font=title,fill=navy)
        draw.text((margin,405),'เลขที่ / No. '+db.order_number(order),font=font,fill=navy)
        y=495
    def ensure(space):
        if y+space>bottom:new_page()
    def wrap(text,limit,face=font):
        # ตัดบรรทัดตามช่องว่าง หรือกลุ่มอักษรไทยพร้อมสระและวรรณยุกต์
        result=[]
        for paragraph in str(text).splitlines() or ['']:
            clusters=[]
            for char in paragraph:
                if clusters and (unicodedata.combining(char) or unicodedata.category(char).startswith('M')):clusters[-1]+=char
                else:clusters.append(char)
            line=''
            for cluster in clusters:
                if line and draw.textlength(line+cluster,font=face)>limit:
                    split=line.rfind(' ')
                    if split>len(line)//2:result.append(line[:split]);line=line[split+1:]
                    else:result.append(line);line=''
                line+=cluster
            result.append(line)
        return result
    def paragraph(text,face=font,color=navy):
        nonlocal y
        for line in wrap(text,right-margin,face):
            ensure(68);draw.text((margin,y),line,font=face,fill=color);y+=68
        y+=14
    def table_header():
        nonlocal y
        ensure(90);draw.rectangle((margin,y,right,y+80),fill='#E9EEF3')
        for x,text,anchor in [(margin+20,'สินค้า / Item','la'),(1710,'จำนวน','ra'),(1980,'ต่อชิ้น','ra'),(right-20,'หลังส่วนลด','ra')]:
            draw.text((x,y+15),text,font=strong,fill=navy,anchor=anchor)
        y+=100
    new_page()
    paragraph('ยืนยันชำระเงินแล้ว / PAID',strong,'#26734D')
    paragraph('วันที่สั่งซื้อ / Ordered: '+receipt.local_time(order['created_at']),small,muted)
    paragraph('วันที่รับชำระ / Paid: '+receipt.local_time(order.get('paid_at'))+' (เวลาไทย / Thai time)',small,muted)
    paragraph('ลูกค้า / Customer: '+order['customer_name'])
    paragraph('ที่อยู่จัดส่ง / Delivery: '+order['address'])
    paragraph('รหัสไปรษณีย์ / Postal code: '+(order.get('postal_code') or ''))
    paragraph('โทรศัพท์ / Phone: '+order['phone'])
    y+=20;table_header()
    for item in items:
        lines=wrap(item.get('product_name') or 'สินค้า / Product',1280,strong)
        name_count=len(lines)
        color=product_colors.custom_name(item['color']) or option_name('TH',item['color'])
        details=f"{item.get('product_code') or '-'} / {color} / {db.size_label(item['size'])}"
        lines+=wrap(details,1280,small)
        row_height=len(lines)*65+100
        if row_height<=bottom-595 and y+row_height>bottom:
            new_page();table_header()
        first=True
        for index,line in enumerate(lines):
            if y+90>bottom:new_page();table_header()
            face=small if index>=name_count else strong
            draw.text((margin+20,y),line,font=face,fill=navy)
            if first:
                for x,value in [(1710,str(item['quantity'])),(1980,f"{item['price']:,.2f}"),(right-20,f"{item['net_total']:,.2f}")]:
                    draw.text((x,y),value,font=font,fill=navy,anchor='ra')
                first=False
            y+=65
        draw.line((margin,y+10,right,y+10),fill='#DAE0E6',width=2);y+=35
    tax=db.vat_breakdown(order['total']);ensure(650);y+=20
    summaries=[('ยอดก่อน VAT / Before VAT',tax['before_vat']),('VAT 7% รวมในยอดชำระ / Included VAT',tax['vat'])]
    if len(items)>1 and order['discount_amount']:paragraph('ยอดแต่ละรายการแบ่งส่วนลดตามสัดส่วน / Line discounts are allocated proportionally.',small,muted)
    paragraph('ยอดก่อน VAT เป็นยอดหลังหักส่วนลดแล้ว / Before VAT is after discounts.',small,muted)
    for label,value in summaries:
        draw.text((margin,y),label,font=font,fill=muted)
        draw.text((right,y),f'฿{value:,.2f}',font=font,fill=navy,anchor='ra');y+=75
    draw.line((margin,y,right,y),fill=navy,width=3);y+=30
    draw.text((margin,y),'ชำระแล้ว / PAID TOTAL',font=strong,fill=navy)
    draw.text((right,y),f"฿{order['total']:,.2f}",font=strong,fill=navy,anchor='ra');y+=110
    paragraph('VAT รวมอยู่ในยอดชำระแล้ว / VAT is included in the payment total.',small,muted)
    paragraph('ขอบคุณที่เลือก JPZ / Thank you for shopping with JPZ.',small,muted)
    for index,image in enumerate(pages):
        footer=ImageDraw.Draw(image)
        footer.line((margin,height-170,right,height-170),fill='#DAE0E6',width=2)
        footer.text((margin,height-135),'เอกสารยืนยันรับชำระเงิน ไม่ใช่ใบกำกับภาษี / Payment receipt, not a tax invoice.',font=small,fill=muted)
        footer.text((right,height-85),f'{index+1} / {len(pages)}',font=small,fill=muted,anchor='ra')
    return order,pages

def _write_pdf(order,pages,destination):
    destination=Path(destination)
    handle,temp=tempfile.mkstemp(prefix='.jpz_receipt_',suffix='.pdf',dir=destination.parent);os.close(handle)
    try:
        pages[0].save(temp,'PDF',resolution=300,save_all=True,append_images=pages[1:],title='JPZ receipt '+db.order_number(order),author='JPZ / Pizza Jeans')
        os.replace(temp,destination)
    finally:
        Path(temp).unlink(missing_ok=True)
    return destination

def export(uid,oid,destination):
    order,pages=render_pages(uid,oid)
    try:return _write_pdf(order,pages,destination)
    finally:
        for image in pages:image.close()

def email_files(uid,oid,folder):
    """สร้างภาพทุกหน้าและ PDF จากใบเสร็จชุดเดียวกัน เพื่อให้ยอดตรงกัน"""
    order,pages=render_pages(uid,oid)
    folder=Path(folder);stem='JPZ_receipt_'+db.order_number(order)
    try:
        pdf=_write_pdf(order,pages,folder/(stem+'.pdf'))
        images=[]
        for index,page in enumerate(pages):
            target=folder/f'{stem}_page_{index+1}.png'
            page.save(target,'PNG');images.append(target)
        return pdf,images
    finally:
        for image in pages:image.close()
