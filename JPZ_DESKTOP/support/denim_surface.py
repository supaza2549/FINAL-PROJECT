"""พื้นผ้าเดนิมจากภาพสินค้าที่มีอยู่ อ่านครั้งเดียว และวาดใหม่เฉพาะเมื่อขนาดเปลี่ยน"""
from pathlib import Path
from functools import lru_cache
import tkinter as tk
import math
from support import image_jobs
import db

NAVY='#193244'
IVORY='#F8F6F0'
GOLD='#B8A88E'

@lru_cache(maxsize=2)
def fabric(path,stamp):
    from PIL import Image
    with Image.open(path) as source:
        # ใช้บริเวณผ้าทอล้วนจากภาพมาโครเดิม หลีกเลี่ยงกระดุม ป้าย และกระเป๋า
        w,h=source.size
        patch=source.crop((round(w*.55),round(h*.83),round(w*.69),round(h*.97))).convert('RGB')
        return patch.resize((96,96),Image.Resampling.LANCZOS)

def texture(app,canvas,content=None,window=None):
    """แผ่นผ้านิ่ง ไม่ย่อภาพซ้ำในแอนิเมชัน และไม่เพิ่มพื้นที่เลื่อนจากภาพพื้นหลัง"""
    state={'photo':None,'size':None,'pending':False,'tiles':[]}
    def paint():
        state['pending']=False
        if not image_jobs.is_current(canvas) or not canvas.winfo_exists():return
        width=max(1,canvas.winfo_width());height=max(1,canvas.winfo_height())
        if content is not None:
            canvas.itemconfigure(window,width=width)
            height=max(height,content.winfo_reqheight())
            canvas.configure(scrollregion=(0,0,width,height))
        dimensions=(width,height)
        if state['photo'] is None or state['size']==dimensions:return
        state['size']=dimensions
        for tile in state['tiles']:canvas.delete(tile)
        state['tiles']=[canvas.create_image(x*96,y*96,image=state['photo'],anchor='nw',tags='denim_surface') for y in range(math.ceil(height/96)) for x in range(math.ceil(width/96))]
        canvas.tag_lower('denim_surface')
    def schedule(event=None):
        if not state['pending']:state['pending']=True;canvas.after_idle(paint)
    canvas.bind('<Configure>',schedule,add='+')
    if content is not None:content.bind('<Configure>',schedule)
    def ready(image):
        if image is None:return
        from PIL import ImageTk
        if not hasattr(app,'_denim_fabric_photo'):app._denim_fabric_photo=ImageTk.PhotoImage(image,master=app)
        state['photo']=app._denim_fabric_photo;paint()
    if hasattr(app,'_denim_fabric_photo'):state['photo']=app._denim_fabric_photo;schedule()
    else:
        path=Path(db.BASE_DIR)/'assets/products/RST-03_raw_indigo_styled.png'
        image_jobs.submit(app,canvas,lambda:fabric(str(path),path.stat().st_mtime_ns),ready)
    canvas._denim_surface=state
    return state

# J58 | แถบตัวกรองกรมท่าเรียบ
def sidebar(app,parent):
    """แถบตัวกรองกรมท่าสีเดียว ไม่มีภาพพื้นหลังหรือเอฟเฟกต์แสง"""
    parent._skip_block_shine=True
    holder=tk.Frame(parent,bg=NAVY);holder.pack(fill='both',expand=True)
    from support.theme import ctk
    bar=ctk.CTkScrollbar(holder,orientation='vertical',fg_color=NAVY,button_color='#8C9EAA',button_hover_color=GOLD)
    bar.pack(side='right',fill='y')
    canvas=tk.Canvas(holder,bg=NAVY,highlightthickness=0,yscrollincrement=24)
    canvas.pack(side='left',fill='both',expand=True);bar.configure(command=canvas.yview);canvas.configure(yscrollcommand=bar.set)
    content=tk.Frame(canvas,bg=NAVY);window=canvas.create_window(0,0,window=content,anchor='nw')
    # เปลี่ยนเฉพาะความกว้างและขอบเขตเลื่อน ไม่สร้างภาพหรือย่อพื้นผ้า
    pending=[None]
    def arrange():
        pending[0]=None
        if not image_jobs.is_current(canvas) or not canvas.winfo_exists():return
        width=max(1,canvas.winfo_width())
        canvas.itemconfigure(window,width=width)
        canvas.configure(scrollregion=(0,0,width,max(canvas.winfo_height(),content.winfo_reqheight())))
    def schedule(event=None):
        if pending[0] is None:pending[0]=canvas.after_idle(arrange)
    canvas.bind('<Configure>',schedule);content.bind('<Configure>',schedule)
    def stop(event):
        if event.widget is canvas and pending[0] is not None:
            try:canvas.after_cancel(pending[0])
            except tk.TclError:pass
            pending[0]=None
    canvas.bind('<Destroy>',stop,add='+')
    app._scroll_targets=getattr(app,'_scroll_targets',[])+[canvas];app.bind_all('<MouseWheel>',app.scroll_wheel)
    app.label(content,'JPZ / SELECTION',9,True,bg=NAVY,fg='#D6C6A9').pack(anchor='w',padx=12,pady=(18,8))
    tk.Frame(content,bg=GOLD,height=1).pack(fill='x',padx=12,pady=(0,4))
    content._denim_canvas=canvas
    return content
