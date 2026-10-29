"""ส่วนประกอบหน้าจอ JPZ โดยใช้ระบบทำงานจากโมดูลเดิม"""
from pathlib import Path
import sys
import re
import unicodedata
from tkinter import TclError
from tkinter import font as tkfont
from functools import lru_cache

vendor=Path(__file__).resolve().parents[1]/'vendor'
if vendor.is_dir():sys.path.insert(0,str(vendor))
import customtkinter as ctk
from customtkinter.windows.widgets.core_rendering import DrawEngine

if DrawEngine.preferred_drawing_method=='circle_shapes':
    DrawEngine.preferred_drawing_method='polygon_shapes'

ctk.set_appearance_mode('light')
ctk.set_default_color_theme('dark-blue')

INK='#17212B'
DENIM='#243E55'
PAPER='#FFFFFF'
BACKDROP='#F1F3F5'
MUTED='#5D6975'
BORDER='#DAE0E6'

def surface(widget):
    try:
        color=widget.cget('fg_color')
        if isinstance(color,(tuple,list)):color=color[0]
        if color and color!='transparent':return color
    except (ValueError,AttributeError,KeyError,TclError):pass
    try:return widget.cget('bg')
    except (ValueError,AttributeError,KeyError,TclError):return PAPER

# Register bundled fonts for this process only, without installing into Windows.
_private_fonts=[]
if sys.platform=='win32':
    import ctypes
    for filename in ('Prompt-Regular.ttf','Prompt-Medium.ttf','Prompt-SemiBold.ttf'):
        path=Path(__file__).resolve().parents[1]/'assets'/'fonts'/filename
        if path.is_file() and ctypes.windll.gdi32.AddFontResourceExW(str(path),0x10,0):
            _private_fonts.append(str(path))

@lru_cache(maxsize=1)
def installed_families():return set(tkfont.families())

def font_family(bold=False,size=11):
    installed=installed_families()
    preferred=('Prompt SemiBold','Prompt Medium','Prompt') if bold and size>=18 else ('Prompt Medium','Prompt') if bold else ('Prompt',)
    return next((family for family in (*preferred,'Leelawadee UI','Leelawadee','Tahoma') if family in installed),'TkDefaultFont')

def font_weight(bold=False,size=11):
    return 'normal' if font_family(bold,size).startswith('Prompt') else 'bold' if bold else 'normal'

def ui_font(size=11,bold=False):
    # Classic Tk sizes are points; CustomTkinter font sizes are pixels.
    return ctk.CTkFont(family=font_family(bold,size),size=round(max(11,size)*4/3),weight=font_weight(bold,size))

class ActionButton(ctk.CTkButton):
    """Allow the few retained Tk-style color updates without changing callbacks."""
    def configure(self,require_redraw=False,**kw):
        for old,new in [('fg','text_color'),('bg','fg_color')]:
            if old in kw:kw[new]=kw.pop(old)
        kw.pop('activeforeground',None)
        return super().configure(require_redraw=require_redraw,**kw)

# J51 | สี / ฟอนต์ / ปุ่ม
def action(parent,text,command,dark=False,compact=False):
    text=clean_ui_text(text)
    font=ui_font(11,True)
    width=max(36,font.measure(text)+(22 if compact else 36))
    return ActionButton(parent,text=text,command=command,font=font,
        width=width,height=max(36 if compact else 46,font.metrics('linespace')+14),corner_radius=8,
        fg_color=DENIM if dark else PAPER,text_color=PAPER if dark else INK,
        hover_color='#355873' if dark else '#E9EEF3',border_width=0 if dark else 1,
        border_color=BORDER,bg_color=surface(parent),cursor='hand2')

def field(parent,font=None,show=None):
    font=font or ui_font(12)
    return ctk.CTkEntry(parent,height=max(48,font.metrics('linespace')+20),corner_radius=10,border_width=1,
        border_color='#D9D4C9',fg_color='#FAF9F5',text_color=INK,
        font=font,show=show or '',bg_color=surface(parent))

def card(parent,color=PAPER,radius=14):
    return ctk.CTkFrame(parent,fg_color=color,bg_color=surface(parent),
        corner_radius=radius,border_width=1,border_color=BORDER)

def ctk_font(font=None):
    if isinstance(font,tuple) and len(font)>=2:
        return ctk.CTkFont(family=font[0],size=round(abs(font[1])*4/3),weight='bold' if 'bold' in font[2:] else 'normal')
    return font or ui_font(12)

class LuxurySelect(ctk.CTkComboBox):
    """เมนูเลือกมุมมนของ JPZ ที่รองรับเหตุการณ์ของฟอร์มเดิม"""
    def __init__(self,parent,**options):
        variable=options.pop('textvariable',None)
        width=options.pop('width',20)
        command=options.pop('command',None)
        self._selection_command=command
        super().__init__(parent,variable=variable,width=max(90,width*8+36),height=46,
            font=ctk_font(options.pop('font',None)),dropdown_font=ui_font(12),
            state=options.pop('state','readonly'),values=options.pop('values',[]),
            corner_radius=10,border_width=1,border_color='#D9D4C9',fg_color='#FAF9F5',
            button_color='#F0EDE5',button_hover_color='#E5DED1',text_color=INK,
            dropdown_fg_color='#FFFEFA',dropdown_hover_color='#EEE8DA',dropdown_text_color=INK,
            bg_color=surface(parent),command=self._selected,**options)

    def _selected(self,value):
        self._entry.event_generate('<<ComboboxSelected>>')
        if self._selection_command:self._selection_command(value)

    def destroy(self):
        # ยกเลิกงานติดตามขนาดของเมนูย่อยก่อนลบ ป้องกันงานค้างเมื่อเปลี่ยนหน้าซ้ำ
        from customtkinter.windows.widgets.scaling import CTkScalingBaseClass
        CTkScalingBaseClass.destroy(self._dropdown_menu)
        super().destroy()

    def event_generate(self,sequence,**options):
        if sequence=='<<ComboboxSelected>>':return self._entry.event_generate(sequence,**options)
        return super().event_generate(sequence,**options)

    def configure(self,require_redraw=False,**options):
        if 'textvariable' in options:options['variable']=options.pop('textvariable')
        if 'width' in options:options['width']=max(90,options['width']*8+36)
        return super().configure(require_redraw=require_redraw,**options)

def select_field(parent,**options):return LuxurySelect(parent,**options)

class ModernCheck(ctk.CTkCheckBox):
    def __init__(self,*args,**options):
        super().__init__(*args,**options)
        self._canvas.configure(takefocus=1)
        self._canvas.bind('<space>',lambda event:(self.toggle(),'break')[1],add='+')
        self._canvas.bind('<Return>',lambda event:(self.toggle(),'break')[1],add='+')
    def invoke(self):return self.toggle()

def check_field(parent,**options):
    options.pop('bg',None);options.pop('activebackground',None);options.pop('takefocus',None)
    options.setdefault('text','')
    return ModernCheck(parent,width=28 if not options['text'] else 160,height=30,
        checkbox_width=25,checkbox_height=25,corner_radius=6,border_width=1.5,
        fg_color=DENIM,border_color='#B6AB96',hover_color='#E9E1D3',checkmark_color=PAPER,
        text_color=INK,bg_color=surface(parent),font=ctk_font(options.pop('font',None)),**options)


def clean_ui_text(value):
    """ปรับระยะข้อความโดยคงขอบเขตคำภาษาไทยและการขึ้นบรรทัดใหม่"""
    if not isinstance(value,str):return value
    value=unicodedata.normalize('NFC',value).replace('\u00a0',' ').replace('\u200b','')
    value=re.sub(r'([\u0e01-\u0e2e])[ \t]+([\u0e31\u0e34-\u0e3a\u0e47-\u0e4e])',r'\1\2',value)
    return re.sub(r'[ \t]{2,}',' ',value)
