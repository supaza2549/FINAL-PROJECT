# หน้าต่างจัดตำแหน่งรูปโปรไฟล์ ผู้ใช้ลากรูปและซูมก่อนบันทึก
# เก็บรูปต้นฉบับแยกจากภาพที่ตัดแล้ว เพื่อกลับมาจัดตำแหน่งใหม่ได้
import tkinter as tk
import math
from tkinter import messagebox
from PIL import Image,ImageDraw,ImageTk
from support.theme import ctk,action,ui_font


# คำนวณขอบเขตการเลื่อน โดยภาพต้องคลุมกรอบตัดทั้งสี่ด้าน
# offset เป็นระยะเลื่อนในหน่วยพิกเซลของหน้าต่างตัวอย่าง

def clamp_offset(image,view,zoom,offset):
    w,h=(view,view) if isinstance(view,(int,float)) else view
    scale=max(w/image.width,h/image.height)*zoom
    limits=((image.width*scale-w)/2,(image.height*scale-h)/2)
    return tuple(max(-limit,min(limit,value)) for value,limit in zip(offset,limits))


# ตัดภาพสี่เหลี่ยมตามตำแหน่งที่เลือก วงกลมแสดงผลใช้ภาพนี้ภายหลัง
# คำนวณจากต้นฉบับก่อนย่อ เพื่อรักษาความคมชัดของรูปที่บันทึก

def crop_avatar(image,view,zoom,offset,size=512):
    return crop_photo(image,(view,view),zoom,offset,(size,size))


def crop_photo(image,view,zoom,offset,size):
    zoom=max(1,min(5,float(zoom)));dx,dy=clamp_offset(image,view,zoom,offset)
    w,h=view;scale=max(w/image.width,h/image.height)*zoom;cw,ch=w/scale,h/scale
    left=(image.width-cw)/2-dx/scale;top=(image.height-ch)/2-dy/scale
    left=max(0,min(image.width-cw,left));top=max(0,min(image.height-ch,top))
    return image.crop((left,top,left+cw,top+ch)).resize(size,Image.Resampling.LANCZOS)


class AvatarEditor(tk.Toplevel):
    # สร้างหน้าต่างตัวอย่างวงกลม พร้อมตัวเลื่อนซูม ปุ่มคืนค่า และปุ่มบันทึก
    def __init__(self,parent,image,on_save,settings=None,portrait=False):
        super().__init__(parent);self.parent=parent;self.original=image.copy();self.on_save=on_save
        self.view=320;self.zoom=1.;self.offset=(0.,0.);self.drag_origin=None
        self.portrait=portrait;self.crop_view=(288,336) if portrait else (320,320)
        self.output_size=(600,700) if portrait else (512,512)
        # เปิดรูปครั้งถัดไปด้วยตำแหน่งที่บัญชีบันทึกไว้
        if isinstance(settings,dict):
            try:
                zoom=float(settings.get('zoom',1));offset=tuple(float(v) for v in settings.get('offset',(0,0)))
                if len(offset)==2 and all(math.isfinite(v) for v in (zoom,*offset)):
                    self.zoom=max(1,min(5,zoom));self.offset=clamp_offset(self.original,self.crop_view,self.zoom,offset)
            except (ValueError,TypeError):pass
        self.initial_zoom=self.zoom;self.initial_offset=self.offset
        self.title(parent.ui('จัดตำแหน่งรูปโปรไฟล์','Adjust profile photo'));self.configure(bg='white')
        if portrait:self.title(parent.ui('จัดตำแหน่งรูปเจ้าของร้าน','Adjust store owner photo'))
        self.geometry('520x630');self.resizable(False,False);self.transient(parent)
        self.update_idletasks();x=parent.winfo_rootx()+(parent.winfo_width()-520)//2;y=parent.winfo_rooty()+(parent.winfo_height()-630)//2
        self.geometry(f'520x630+{max(0,x)}+{max(0,y)}')
        parent.label(self,parent.ui('จัดรูปเจ้าของร้านให้พอดีกรอบ','Fit the store owner photo to the frame') if portrait else parent.ui('จัดรูปให้พอดีกับวงกลม','Fit your photo in the circle'),19,True).pack(pady=(20,8))
        parent.label(self,parent.ui('ลากรูปเพื่อเลื่อนตำแหน่ง หมุนล้อเมาส์ขึ้นเพื่อซูมเข้า ลงเพื่อซูมออก','Drag to reposition. Scroll up to zoom in, down to zoom out.'),11,wraplength=460,justify='center').pack(pady=(0,14))
        self.canvas=tk.Canvas(self,width=self.crop_view[0],height=self.crop_view[1],bg='#243E55',highlightthickness=0,cursor='fleur')
        self.canvas.pack();self.canvas.bind('<ButtonPress-1>',self.start_drag);self.canvas.bind('<B1-Motion>',self.drag)
        # รับล้อเมาส์ทั่วหน้าต่างจัดรูป โดยไม่ผูกกับหน้าหลักของโปรแกรม
        self.bind('<MouseWheel>',self.wheel)
        tools=tk.Frame(self,bg='white');tools.pack(fill='x',padx=42,pady=(18,8))
        # ปุ่มลบและบวกช่วยให้ปรับขนาดได้โดยไม่ต้องลากตัวเลื่อน
        self.zoom_out=action(tools,'−',lambda:self.set_zoom(self.zoom-.1),compact=True)
        self.zoom_out.pack(side='left',padx=(0,8))
        self.slider=ctk.CTkSlider(tools,from_=1,to=5,number_of_steps=80,command=self.set_zoom,fg_color='#DAE0E6',progress_color='#243E55',button_color='#243E55');self.slider.pack(side='left',fill='x',expand=True);self.slider.set(self.zoom)
        self.zoom_in=action(tools,'+',lambda:self.set_zoom(self.zoom+.1),compact=True)
        self.zoom_in.pack(side='left',padx=(8,0))
        self.zoom_label=parent.label(self,'',11)
        self.zoom_label.pack()
        buttons=tk.Frame(self,bg='white');buttons.pack(fill='x',padx=28,pady=16)
        action(buttons,parent.ui('คืนตำแหน่งเดิม','Reset'),self.reset,compact=True).pack(side='left')
        action(buttons,parent.ui('บันทึกรูป','Save photo'),self.save,dark=True,compact=True).pack(side='right')
        action(buttons,parent.ui('ยกเลิก','Cancel'),self.close,compact=True).pack(side='right',padx=8)
        self.protocol('WM_DELETE_WINDOW',self.close);self.bind('<Escape>',lambda event:self.close())
        self.render();self.grab_set()

    # อัปเดตตัวอย่างด้วยตำแหน่งปัจจุบัน และทำพื้นที่นอกวงกลมให้มืดลง
    def render(self):
        # แสดงเปอร์เซ็นต์และหยุดปุ่มเมื่อถึงขอบเขต ป้องกันภาพไม่เต็มวงกลม
        self.zoom_label.configure(text=self.parent.ui(f'ซูม {self.zoom:.0%} · 100% = พอดีกรอบ',f'Zoom {self.zoom:.0%} · 100% = fit to frame'))
        self.zoom_out.configure(state='disabled' if self.zoom<=1 else 'normal')
        self.zoom_in.configure(state='disabled' if self.zoom>=5 else 'normal')
        self.offset=clamp_offset(self.original,self.crop_view,self.zoom,self.offset)
        square=crop_photo(self.original,self.crop_view,self.zoom,self.offset,self.crop_view).convert('RGBA')
        overlay=Image.new('RGBA',self.crop_view,(0,0,0,0) if self.portrait else (20,32,43,200));draw=ImageDraw.Draw(overlay)
        if self.portrait:draw.rectangle((1,1,self.crop_view[0]-2,self.crop_view[1]-2),outline='white',width=2)
        else:draw.ellipse((2,2,self.view-3,self.view-3),fill=(0,0,0,0),outline=(255,255,255,255),width=2)
        photo=ImageTk.PhotoImage(Image.alpha_composite(square,overlay),master=self)
        self.canvas.delete('all');self.canvas.create_image(0,0,image=photo,anchor='nw');self.canvas._image=photo

    # บันทึกจุดเริ่มลาก ไม่เขียนข้อมูลลงฐานข้อมูลในขั้นตอนนี้
    def start_drag(self,event):self.drag_origin=(event.x,event.y,*self.offset)

    # คำนวณระยะลากและปรับตัวอย่างทันที
    def drag(self,event):
        if self.drag_origin:
            x,y,dx,dy=self.drag_origin;self.offset=(dx+event.x-x,dy+event.y-y);self.render()

    # ปรับตัวคูณซูมและป้องกันการเลื่อนภาพออกนอกขอบ
    def set_zoom(self,value):self.zoom=max(1,min(5,float(value)));self.slider.set(self.zoom);self.render()

    # รองรับการใช้สกรอลล์เมาส์เพื่อซูมภาพในหน้าต่างนี้
    def wheel(self,event):
        if event.delta:
            self.set_zoom(self.zoom*(1.12 if event.delta>0 else 1/1.12))
        return 'break'

    # คืนตำแหน่งและขนาดที่ใช้เมื่อเริ่มเปิดหน้าต่างนี้
    def reset(self):self.offset=self.initial_offset;self.set_zoom(self.initial_zoom)

    # เรียกตัวบันทึกรูปของบัญชีเมื่อผู้ใช้กดยืนยันเท่านั้น
    def save(self):
        try:self.on_save(crop_photo(self.original,self.crop_view,self.zoom,self.offset,self.output_size),self.original,{'zoom':self.zoom,'offset':list(self.offset)})
        except Exception as exc:messagebox.showerror('JPZ',str(exc),parent=self);return
        self.close()

    # ปิดหน้าต่างและคืนการควบคุมให้หน้าหลัก การยกเลิกไม่บันทึกภาพ
    def close(self):
        if self.winfo_exists():self.grab_release();self.destroy()
