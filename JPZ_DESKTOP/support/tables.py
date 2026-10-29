import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

class AdminTable(ttk.Treeview):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.tag_configure('low_stock',foreground='#BB2020')
        self.tag_configure('stripe_even',background='#FFFFFF')
        self.tag_configure('stripe_odd',background='#F1F5F8')
        self._grid_lines=[];self._grid_job=None;self._header_height=None
        self._status_styles={};self._status_labels=[];self._on_cell_double=None
        self._body_font=tkfont.Font(self,font=ttk.Style(self).lookup(self.cget('style'),'font'))
        self.bind('<Configure>',lambda event:self.schedule_grid(),add='+')
        self.bind('<ButtonRelease-1>',lambda event:self.schedule_grid(),add='+')
        self.bind('<B1-Motion>',lambda event:self.schedule_grid(),add='+')
        self.bind('<MouseWheel>',self.scroll_mouse)
        self.bind('<Shift-MouseWheel>',lambda event:self.schedule_grid(),add='+')
        self.bind('<KeyRelease>',lambda event:self.schedule_grid(),add='+')
        self.bind('<Control-c>',self.copy_selected,add='+')

    def scrolled(self,callback,*args):
        callback(*args);self.schedule_grid()

    def scroll_mouse(self,event):
        if not event.delta:return 'break'
        before=self.yview();units=max(1,abs(event.delta)//120)*(-1 if event.delta>0 else 1)
        can_scroll=(units<0 and before[0]>0) or (units>0 and before[1]<1)
        if can_scroll:self.yview_scroll(units,'units')
        self.schedule_grid()
        if self.yview()==before:
            parent=self.master
            while parent is not None:
                if isinstance(parent,tk.Canvas):parent.yview_scroll(units,'units');break
                parent=getattr(parent,'master',None)
        return 'break'

    def schedule_grid(self):
        if self._grid_job is None and self.winfo_exists():self._grid_job=self.after_idle(self.draw_grid)

    def draw_grid(self):
        self._grid_job=None
        if not self.winfo_exists():return
        width=self.winfo_width();height=self.winfo_height()
        if width<4 or height<4:return
        if self._header_height is None:
            self._header_height=max((y+1 for y in range(min(height,120)) if self.identify_region(8,y) in ('heading','separator')),default=48)
        header=self._header_height
        row_height=int(ttk.Style(self).lookup(self.cget('style'),'rowheight') or 46)
        columns=self.cget('columns');total=sum(int(self.column(k,'width')) for k in columns)
        offset=round(self.xview()[0]*total);x=1-offset
        specs=[]
        for key in columns:
            x+=int(self.column(key,'width'))
            if 0<x<width:specs.append((x,0,1,height))
        for y in range(header,height,row_height):specs.append((0,y,width,1))
        while len(self._grid_lines)<len(specs):
            line=tk.Frame(self,bg='#D9DFE5',bd=0,highlightthickness=0)
            # Thin separators forward native table interactions to preserve selection/resize.
            for sequence in ('<Button-1>','<ButtonRelease-1>','<B1-Motion>'):
                def forward(event,seq=sequence):
                    self.event_generate(seq,x=event.x_root-self.winfo_rootx(),y=event.y_root-self.winfo_rooty(),state=event.state)
                    return 'break'
                line.bind(sequence,forward)
            line.bind('<MouseWheel>',lambda event:(self.event_generate('<MouseWheel>',delta=event.delta),'break')[1])
            self._grid_lines.append(line)
        for line,spec in zip(self._grid_lines,specs):line.place(x=spec[0],y=spec[1],width=spec[2],height=spec[3]);line.lift()
        for line in self._grid_lines[len(specs):]:line.place_forget()
        self.draw_status_cells(header,row_height)

    def set_status_colors(self,item,columns):
        self._status_styles[str(item)]=dict(columns);self.schedule_grid()

    def bind(self,sequence=None,func=None,add=None):
        if sequence in ('<Double-1>','<Double-Button-1>') and callable(func):self._on_cell_double=func
        return super().bind(sequence,func,add)

    def draw_status_cells(self,header,row_height):
        children=self.get_children();first=self.identify_row(header+2)
        start=children.index(first) if first in children else int(self.yview()[0]*len(children))
        visible=children[start:start+max(1,(self.winfo_height()-header)//row_height+2)]
        cells=[]
        for item in visible:
            for column,(foreground,background) in self._status_styles.get(item,{}).items():
                bounds=self.bbox(item,column)
                if bounds and bounds[0]+bounds[2]>0 and bounds[0]<self.winfo_width():cells.append((item,column,bounds,foreground,background))
        while len(self._status_labels)<len(cells):
            label=tk.Label(self,bd=0,padx=7,anchor='w',font=self._body_font)
            def click(event):
                self.focus_set();self.selection_set(event.widget._table_item);self.focus(event.widget._table_item)
                self.event_generate('<<TreeviewSelect>>');return 'break'
            def double(event):
                click(event)
                if self._on_cell_double:
                    converted=tk.Event();converted.__dict__.update(event.__dict__);converted.widget=self
                    converted.x=event.x_root-self.winfo_rootx();converted.y=event.y_root-self.winfo_rooty()
                    self._on_cell_double(converted)
                return 'break'
            label.bind('<Button-1>',click);label.bind('<Double-1>',double)
            label.bind('<MouseWheel>',lambda event:(self.event_generate('<MouseWheel>',delta=event.delta),'break')[1])
            label.bind('<Shift-MouseWheel>',lambda event:(self.event_generate('<Shift-MouseWheel>',delta=event.delta),'break')[1])
            self._status_labels.append(label)
        for label,(item,column,bounds,foreground,background) in zip(self._status_labels,cells):
            label._table_item=item;label._table_column=column
            label.configure(text=self.set(item,column),fg=foreground,bg=background)
            x,y,width,height=bounds
            label.place(x=x+3,y=y+3,width=max(1,width-6),height=max(1,height-6));label.lift()
        for label in self._status_labels[len(cells):]:label.place_forget()

    def delete(self,*items):
        for item in items:self._status_styles.pop(str(item),None)
        result=super().delete(*items);self.schedule_grid();return result

    def copy_selected(self,event=None):
        rows=[self.item(i,'values') for i in self.selection()]
        if rows:self.clipboard_clear();self.clipboard_append('\n'.join('\t'.join(str(v) for v in row) for row in rows))
        return 'break'

    def destroy(self):
        if self._grid_job is not None:
            try:self.after_cancel(self._grid_job)
            except tk.TclError:pass
            self._grid_job=None
        return super().destroy()

    def insert(self,parent,index,iid=None,**kwargs):
        tags=tuple(kwargs.pop('tags',()))
        kwargs['tags']=tags+('stripe_odd' if len(self.get_children(parent))%2 else 'stripe_even',)
        for key,value in zip(self.cget('columns'),kwargs.get('values',())):
            minimum=min(520,max(int(self.column(key,'minwidth')),self._body_font.measure(str(value))+20))
            if minimum>int(self.column(key,'minwidth')):
                self.column(key,minwidth=minimum,width=max(minimum,int(self.column(key,'width'))))
        result=super().insert(parent,index,iid=iid,**kwargs);self.schedule_grid();return result

    def restripe(self):
        for index,item in enumerate(self.get_children()):
            tags=tuple(t for t in self.item(item,'tags') if not t.startswith('stripe_'))
            self.item(item,tags=tags+('stripe_odd' if index%2 else 'stripe_even',))
