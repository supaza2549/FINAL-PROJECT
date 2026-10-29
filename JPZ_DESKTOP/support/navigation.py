"""จดจำตำแหน่งเลื่อนเมื่อสร้างหน้าจอเดิมขึ้นใหม่"""
import tkinter as tk
from tkinter import ttk
from support.theme import ctk

class NavigationMixin:
    def viewport_key(self):
        args=getattr(self,'current_args',{}).get('args',())
        ids=tuple(arg.get('id') if isinstance(arg,dict) else arg for arg in args if isinstance(arg,(dict,str,int)))
        page=getattr(self,'current_page',None)
        if page=='shop':ids=(getattr(self,'shop_fit','all'),getattr(self,'shop_style','all'),getattr(self,'shop_page',0),getattr(self,'shop_sort','recommended'))
        elif page=='favorites':ids=(getattr(self,'favorites_page',0),)
        return ((self.user or {}).get('id') if getattr(self,'user',None) else None,page,
                getattr(self,'admin_tab',None) if page=='admin' else ids)

    def viewport_widgets(self):
        result=[]
        def visit(parent):
            for widget in parent.winfo_children():
                if getattr(widget,'_retired_page',False):continue
                if isinstance(widget,tk.Toplevel):continue
                # ข้ามชิ้นส่วนภายในปุ่มและช่องกรอก ซึ่งไม่มีตำแหน่งเลื่อนให้จดจำ
                if isinstance(widget,(ctk.CTkButton,ctk.CTkEntry,ctk.CTkLabel,ctk.CTkComboBox,ctk.CTkScrollbar,ctk.CTkCheckBox)):continue
                if isinstance(widget,tk.Canvas):
                    if len(str(widget.cget('scrollregion')).split())==4:result.append(widget)
                elif isinstance(widget,(ttk.Treeview,ttk.Notebook)):result.append(widget)
                visit(widget)
        visit(self);return result

    # J50 | จำตำแหน่งเลื่อน
    def capture_viewport(self):
        key=getattr(self,'_active_viewport_key',None)
        if key is None:return
        states=[]
        for widget in self.viewport_widgets():
            if isinstance(widget,ttk.Notebook):states.append(('tabs',widget.index(widget.select()) if widget.select() else 0))
            elif isinstance(widget,tk.Canvas):states.append(('canvas',max(0,widget.canvasy(0)),widget.xview()[0]))
            else:states.append(('tree',widget.yview()[0],widget.xview()[0]))
        self._viewport_memory=getattr(self,'_viewport_memory',{})
        self._viewport_memory[key]=states

    def schedule_viewport_restore(self):
        key=self.viewport_key();self._active_viewport_key=key
        page=getattr(self,'current_page',None);reset='_reset_'+str(page)+'_scroll'
        if page in ('shop','favorites') and getattr(self,reset,False):
            setattr(self,reset,False)
            getattr(self,'_viewport_memory',{}).pop(key,None)
            return
        states=getattr(self,'_viewport_memory',{}).get(key)
        if not states:return
        def restore():
            if self._active_viewport_key!=key:return
            if getattr(self,'_card_batches',None):self.after(20,restore);return
            for widget,state in zip(self.viewport_widgets(),states):
                if state[0]=='tabs' and isinstance(widget,ttk.Notebook):
                    if state[1]<len(widget.tabs()):widget.select(state[1])
                elif state[0]=='canvas' and isinstance(widget,tk.Canvas):
                    region=list(map(float,str(widget.cget('scrollregion')).split()))
                    height=region[3]-region[1]
                    if height>0:widget.yview_moveto(state[1]/height)
                    widget.xview_moveto(state[2])
                elif state[0]=='tree' and isinstance(widget,ttk.Treeview):widget.yview_moveto(state[1]);widget.xview_moveto(state[2])
        self.after_idle(lambda:self.after(20,restore))
