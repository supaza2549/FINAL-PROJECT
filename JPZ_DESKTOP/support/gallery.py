"""อ่านแกลเลอรีและแสดงภาพในหน้าจอ โดยคงไฟล์ภาพต้นฉบับไว้"""
from pathlib import Path
from support import catalogue
import db
import tkinter as tk
import math
from functools import lru_cache
try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

class NativeImage:
    """แสดงภาพ PNG ด้วย Tk ที่มากับ Python เมื่อไม่มี Pillow"""
    def __init__(self, photo):
        self.photo = photo
        self.width, self.height = photo.width(), photo.height()
        self.size = (self.width, self.height)
    def copy(self):
        return NativeImage(self.photo.copy())
    def resize(self, size, *args):
        ratio = min(size[0]/self.width, size[1]/self.height)
        photo = self.photo.subsample(max(1, math.ceil(1/ratio))) if ratio < 1 else self.photo.zoom(max(1, min(4, int(ratio))))
        return NativeImage(photo)
    def thumbnail(self, size, *args):
        if self.width > size[0] or self.height > size[1]:
            resized = self.resize(size)
            self.__dict__.update(resized.__dict__)

def to_photo(image, master=None):
    return image.photo if isinstance(image, NativeImage) else ImageTk.PhotoImage(image, master=master)

VIEWS=('FRONT','BACK','DETAIL','TEXTURE')

@lru_cache(maxsize=12)
def _source_preview(path,stamp,cell):
    with Image.open(path) as original:
        image=original.convert('RGB')
        if cell>=0:
            w,h=image.size
            if cell not in range(4):return None
            image=image.crop(((cell%2)*w//2,(cell//2)*h//2,((cell%2)+1)*w//2,((cell//2)+1)*h//2))
        image=portrait_frame(image,cell);image.thumbnail((1800,1800))
        return image.copy()

@lru_cache(maxsize=48)
def _preview(path, stamp, cell):
    with Image.open(path) as image:
        image=image.convert('RGB')
        if cell>=0:
            w,h=image.size
            if cell not in range(4):return None
            image=image.crop(((cell%2)*w//2,(cell//2)*h//2,((cell%2)+1)*w//2,((cell//2)+1)*h//2))
        image=portrait_frame(image,cell)
        image.thumbnail((480,490))
        return image.copy()

def preview(pid,color,view):
    if Image is None:return source(pid,color,view)
    item=next((r for r in catalogue.gallery(pid,color) if r['view']==view),None)
    if not item:return None
    path=(Path(db.BASE_DIR)/item['path']).resolve()
    if not path.is_relative_to(Path(db.BASE_DIR).resolve()) or not path.is_file():return None
    result=_preview(str(path),path.stat().st_mtime_ns,item['cell'])
    return result.copy() if result is not None else None

def reference(pid,color,view):
    """เลือกภาพสีตรงกับสินค้า หากไม่มีให้ใช้ภาพอ้างอิงรุ่นเดียวกันพร้อมแจ้งสี"""
    rows=catalogue.gallery(pid,color)
    exact=next((r for r in rows if r['view']==view and (Path(db.BASE_DIR)/r['path']).is_file()),None)
    if exact:return exact
    c=db.conn()
    try:
        rows=[dict(r) for r in c.execute('SELECT * FROM product_gallery WHERE product_id=? AND view=? ORDER BY generated,color',(pid,view))]
    finally:c.close()
    return next((r for r in rows if (Path(db.BASE_DIR)/r['path']).is_file()),None)

def portrait_frame(image,cell):
    # ภาพคนใส่ในชุดภาพมีพื้นหลังสี่เหลี่ยม จึงตัดด้านข้างออก
    # โดยคงความสูงและสัดส่วนของร่างกาย ไม่ยืดภาพ
    if cell in (0,1) and image.width/image.height > .8:
        width=round(image.height*.75);left=(image.width-width)//2
        return image.crop((left,0,left+width,image.height))
    return image

def source(pid,color,view,fallback=False):
    item=reference(pid,color,view) if fallback else next((r for r in catalogue.gallery(pid,color) if r['view']==view),None)
    if not item:return None
    path=(Path(db.BASE_DIR)/item['path']).resolve()
    if not path.is_relative_to(Path(db.BASE_DIR).resolve()) or not path.is_file():return None
    if Image is None:
        if path.suffix.lower() != '.png':return None
        atlas = tk.PhotoImage(file=str(path))
        cell = item['cell']
        if cell == -1:return NativeImage(atlas)
        if cell not in range(4):return None
        w, h = atlas.width()//2, atlas.height()//2
        left, top = (cell%2)*w, (cell//2)*h
        width=min(w,round(h*.75)) if cell in (0,1) else w
        left+=(w-width)//2
        cropped = tk.PhotoImage(width=width, height=h)
        cropped.tk.call(str(cropped), 'copy', str(atlas), '-from', left, top, left+width, top+h)
        return NativeImage(cropped)
    image=_source_preview(str(path),path.stat().st_mtime_ns,item['cell'])
    return image.copy() if image is not None else None

def photo(pid,color,view,width,height,master=None,fallback=False):
    image=source(pid,color,view,fallback=fallback)
    if image is None:return None
    image.thumbnail((max(1,int(width)),max(1,int(height))))
    return to_photo(image,master=master)


# J16 | ครอปรูปช่วงกางเกง
def lower_body(pid,color,view,fallback=False):
    image=source(pid,color,view,fallback=fallback)
    if image is None or Image is None:return image
    row=reference(pid,color,view) if fallback else next((r for r in catalogue.gallery(pid,color) if r['view']==view),None)
    if row and row['generated'] and row['cell'] in (0,1):
        # ตัดภาพให้เห็นช่วงลำตัวถึงรองเท้า โดยไม่ยืดแกนใดแกนหนึ่ง
        image=image.crop((0,round(image.height*.24),image.width,image.height))
    return image

def lower_body_preview(pid,color,view):
    """ใช้ภาพย่อในรายการสินค้า เก็บภาพใหญ่ไว้สำหรับรายละเอียดและซูม"""
    row=reference(pid,color,view)
    if not row:return None
    image=preview(pid,row['color'],view)
    if image is not None and Image is not None and row['generated'] and row['cell'] in (0,1):
        image=image.crop((0,round(image.height*.24),image.width,image.height))
    return image

@lru_cache(maxsize=4)
def _pose_metadata(base):
    import json
    path=Path(base)/'assets/products/gallery_manifest.json'
    return {r['path']:r.get('poses',[]) for r in json.loads(path.read_text('utf-8'))} if path.is_file() else {}

def standing_view(product,prefer_back=False):
    """เลือกภาพท่ายืนที่มีอยู่ โดยไม่ดัดทรงกางเกงหรือสร้างท่าใหม่"""
    choices=[];metadata=_pose_metadata(str(db.BASE_DIR))
    for view in ('FRONT','BACK'):
        row=reference(product['id'],product['color'],view)
        if not row:continue
        poses=metadata.get(row['path'],[])
        pose=poses[row['cell']].lower() if row['cell'] in range(len(poses)) else ''
        if any(word in pose for word in ('seated','sitting','crouch','squat','kneeling')):continue
        choices.append(view)
    return 'BACK' if prefer_back and 'BACK' in choices else choices[0] if choices else 'DETAIL'
