"""ภาพตะกร้าตรงรุ่นและสี เน้นช่วงกางเกง และรักษาสัดส่วนภาพ"""
from PIL import Image,ImageOps
import db
from support import gallery,catalogue

# J54 | ภาพครึ่งตัวในตะกร้า
def thumbnail(pid,color):
    product=db.product(pid)
    if not product:return None
    product=dict(product,color=color)
    rows=catalogue.gallery(pid,color);views={row['view'] for row in rows}
    standing=gallery.standing_view(product)
    choices=[standing,'DETAIL']
    metadata=gallery._pose_metadata(str(db.BASE_DIR))
    # ไม่แทนรูปด้วยสีอื่น และไม่ใช้รูปท่านั่งเมื่อมีมุมยืน/ภาพตัวกางเกงให้เลือก
    for candidate in ('FRONT','BACK'):
        row=next((r for r in rows if r['view']==candidate),None)
        if not row:continue
        poses=metadata.get(row['path'],[])
        pose=poses[row['cell']].lower() if row['cell'] in range(len(poses)) else ''
        if any(word in pose for word in ('seated','sitting','crouch','squat','kneeling')):continue
        choices.append(candidate)
    for view in dict.fromkeys(choices):
        if view not in views:continue
        image=gallery.preview(pid,color,view)
        if image is None:continue
        row=next(r for r in rows if r['view']==view)
        cropped=bool(row['generated'] and row['cell'] in (0,1))
        if cropped:image=image.crop((0,round(image.height*.24),image.width,image.height))
        return ImageOps.pad(image,(110,130),color='#F4F4F4',method=Image.Resampling.LANCZOS),view,cropped
    return None
