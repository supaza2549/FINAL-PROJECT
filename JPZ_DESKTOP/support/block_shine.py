"""แสงเฉียงบนบล็อกสี ใช้ตัวจับเวลาร่วมตัวเดียวและหยุดวาดเมื่อมองไม่เห็น"""
import tkinter as tk
import time
from support.image_jobs import is_current

def colored(widget,color):
    if isinstance(color,(tuple,list)):color=color[0]
    if not color or color=='transparent':return False
    try:
        rgb=widget.winfo_rgb(color)
        return max(rgb)/65535<.82 and sum(rgb)/3/65535<.73
    except tk.TclError:return False

def tint(widget,color,amount):
    if isinstance(color,(tuple,list)):color=color[0]
    values=widget.winfo_rgb(color)
    return '#'+''.join(f'{round(v/257+(255-v/257)*amount):02x}' for v in values)

def clipped(points,bounds):
    """ตัดแสงไว้ภายในบล็อก ไม่ให้ล้นขอบหรือทับรูปสินค้าข้างเคียง"""
    left,top,right,bottom=bounds
    for axis,edge,lower in ((0,left,True),(0,right,False),(1,top,True),(1,bottom,False)):
        result=[]
        if not points:break
        previous=points[-1];inside=lambda p:p[axis]>=edge if lower else p[axis]<=edge
        for current in points:
            a,b=inside(previous),inside(current)
            if a!=b:
                ratio=(edge-previous[axis])/(current[axis]-previous[axis])
                result.append(tuple(previous[i]+ratio*(current[i]-previous[i]) for i in (0,1)))
            if b:result.append(current)
            previous=current
        points=result
    return tuple(value for point in points for value in point)

# J57 | แสงเคลื่อนไหวและการลดงานซ้ำ
class BlockShine:
    def __init__(self,app):
        self.app=app;self.entries={};self.started=time.monotonic();self.scanned=0;self.job=None;self.ticks=0;self.dirty=True;self.scan_count=0
        # ตรวจรายการบล็อกเมื่อจัดหน้าจอเท่านั้น ไม่เดินค้นทั้งหน้าต่างทุก 0.8 วินาที
        app.bind('<Map>',self.invalidate,add='+');app.bind('<Configure>',self.resize,add='+')
        app.bind('<Destroy>',self.stop,add='+');self.job=app.after(100,self.tick)

    def invalidate(self,event=None):
        self.dirty=True

    def resize(self,event):
        # การวาดรูปย่อยไม่ควรทำให้ค้นทั้งหน้าใหม่ การย่อ/ขยายหน้าต่างจึงค่อยตรวจ
        if event.widget is self.app:self.invalidate()

    def stop(self,event=None):
        if event is not None and event.widget is not self.app:return
        if self.job:
            try:self.app.after_cancel(self.job)
            except tk.TclError:pass
        self.job=None

    def scan(self):
        self.scan_count+=1
        found=set()
        def nested_surface(widget,color):
            # กรอบซ้อนกันสีเดียวกันใช้แสงเพียงพื้นผิวเดียว ไม่เกิดแถบแสงซ้ำ
            if isinstance(color,(tuple,list)):color=color[0]
            for child in widget.winfo_children():
                if type(child) is not tk.Frame and type(child).__name__!='CTkFrame':continue
                try:
                    fill=child.cget('fg_color') if hasattr(child,'_canvas') else child.cget('bg')
                    if isinstance(fill,(tuple,list)):fill=fill[0]
                    if fill==color and child.winfo_width()>widget.winfo_width()*.65 and child.winfo_height()>widget.winfo_height()*.55:return True
                except (ValueError,AttributeError,tk.TclError):pass
            return False
        def add(owner,canvas,target,color):
            key=(str(canvas),target);found.add(key)
            if key in self.entries:return
            tags='jpz_block_shine'
            ids=[canvas.create_polygon(0,0,0,0,0,0,fill=tint(canvas,color,a),outline='',state='hidden',tags=tags) for a in (.10,.19)]
            for item in ids:
                if target is not None:canvas.tag_raise(item,target)
                else:
                    try:canvas.tag_raise(item,'inner_parts')
                    except tk.TclError:pass
            self.entries[key]=(owner,canvas,target,ids)
        def walk(widget):
            if not is_current(widget) or getattr(widget,'_block_shine_overlay',False) or getattr(widget,'_skip_block_shine',False):return
            # ปุ่มและกรอบ CustomTkinter มี Canvas อยู่หลังตัวหนังสือและปุ่มย่อย
            if hasattr(widget,'_canvas'):
                try:
                    color=widget.cget('fg_color')
                    if colored(widget,color) and widget.winfo_width()>=55 and widget.winfo_height()>=25 and not nested_surface(widget,color):
                        add(widget,widget._canvas,None,color)
                except (ValueError,AttributeError,tk.TclError):pass
            elif isinstance(widget,tk.Frame) and colored(widget,widget.cget('bg')) and widget.winfo_width()>=55 and widget.winfo_height()>=25 and not nested_surface(widget,widget.cget('bg')):
                if not hasattr(widget,'_shine_canvas'):
                    canvas=tk.Canvas(widget,bg=widget.cget('bg'),highlightthickness=0,bd=0)
                    canvas._block_shine_overlay=True;canvas.place(x=0,y=0,relwidth=1,relheight=1)
                    widget.tk.call('lower',str(canvas));widget._shine_canvas=canvas
                add(widget,widget._shine_canvas,None,widget.cget('bg'))
            elif isinstance(widget,tk.Canvas) and not hasattr(widget.master,'_canvas'):
                for item in widget.find_all():
                    if widget.type(item)!='rectangle':continue
                    color=widget.itemcget(item,'fill');bounds=widget.coords(item)
                    if len(bounds)==4 and bounds[2]-bounds[0]>=55 and bounds[3]-bounds[1]>=25 and colored(widget,color):add(widget,widget,item,color)
            # ไม่ค้นชิ้นส่วนภายในปุ่ม ช่องกรอก และไอคอนที่ไม่ได้เป็นบล็อกใหม่
            if type(widget).__name__ in ('ActionButton','CTkButton','CTkEntry','CTkLabel','CTkComboBox','LuxurySelect','CTkCheckBox','ModernCheck','CTkScrollbar'):return
            for child in widget.winfo_children():walk(child)
        walk(self.app)
        for key in set(self.entries)-found:
            _,canvas,_,ids=self.entries.pop(key)
            try:
                for item in ids:canvas.delete(item)
            except tk.TclError:pass

    def tick(self):
        self.job=None
        if not self.app.winfo_exists():return
        # ฝั่งแอดมินไม่มีแสงและไม่ค้นบล็อก ลดทั้งงานวาดและงานตรวจหน้าจอ
        if str(getattr(self.app,'current_page','')).startswith('admin') or getattr(self.app,'_admin_screen_active',False):
            for _,canvas,_,ids in self.entries.values():
                try:
                    for item in ids:canvas.delete(item)
                except tk.TclError:pass
            self.entries.clear();self.dirty=True
            self.job=self.app.after(400,self.tick);return
        now=time.monotonic()
        if self.dirty and now-self.scanned>.5:
            self.dirty=False;self.scan();self.scanned=now
        visible_count=0
        for owner,canvas,target,ids in list(self.entries.values()):
            if not is_current(owner) or not owner.winfo_exists():
                self.dirty=True;continue
            visible=owner.winfo_ismapped() and self.app.state()!='iconic'
            if target is None:
                pad=5
                bounds=(pad,pad,canvas.winfo_width()-pad,canvas.winfo_height()-pad)
                visible=visible and owner.winfo_rooty()+owner.winfo_height()>self.app.winfo_rooty() and owner.winfo_rooty()<self.app.winfo_rooty()+self.app.winfo_height()
            else:
                bounds=canvas.coords(target)
                # ภาพตกแต่งอาจถูกวาดใหม่ระหว่างเปลี่ยนขนาด ไม่ใช้พิกัดของบล็อกเก่า
                if len(bounds)!=4:
                    for item in ids:canvas.itemconfigure(item,state='hidden')
                    continue
                visible=visible and bounds[3]>canvas.canvasy(0) and bounds[1]<canvas.canvasy(canvas.winfo_height())
            phase=(now-self.started)%5
            if not visible or phase>2.2 or bounds[2]<=bounds[0] or bounds[3]<=bounds[1]:
                for item in ids:canvas.itemconfigure(item,state='hidden')
                continue
            left,top,right,bottom=bounds;width=right-left;height=bottom-top
            slant=min(85,height*.5);x=left-width*.25+(width*1.5+slant)*phase/2.2
            for item,band in zip(ids,(max(15,width*.13),max(6,width*.045))):
                points=clipped([(x-band,top),(x,top),(x+slant,bottom),(x+slant-band,bottom)],bounds)
                if len(points)>=6:canvas.coords(item,*points);canvas.itemconfigure(item,state='normal')
                else:canvas.itemconfigure(item,state='hidden')
            visible_count+=1
        self.ticks+=1
        self.job=self.app.after(50 if visible_count else 160,self.tick)

def install(app):
    if not hasattr(app,'_block_shine'):app._block_shine=BlockShine(app)
