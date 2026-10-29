"""อ่านและย่อภาพในงานเบื้องหลัง แล้วส่งผลมาวาดบนเธรดหน้าจอ"""
from concurrent.futures import ThreadPoolExecutor
import queue
import tkinter as tk
import time
_pool=ThreadPoolExecutor(max_workers=2,thread_name_prefix='jpz-images')

def is_current(widget):
    """ตรวจจากข้อมูล Python เท่านั้น เพื่อใช้ได้ในงานภาพเบื้องหลัง"""
    while widget is not None:
        if getattr(widget,'_retired_page',False):return False
        widget=getattr(widget,'master',None)
    return True
# J49 | โหลดภาพเบื้องหลัง
def submit(app,widget,work,done):
    if not hasattr(app,'_image_results'):app._image_results=queue.Queue();app._image_pending=0
    app._image_pending+=1
    def run():
        try:result=work() if is_current(widget) else None
        except (OSError,ValueError):result=None
        except Exception:result=None
        app._image_results.put((widget,done,result))
    future=_pool.submit(run)
    future.add_done_callback(lambda f:app._image_results.put((widget,done,None)) if f.cancelled() else None)
    widget.bind('<Destroy>',lambda event:future.cancel() if event.widget is widget else None,add='+')
    if getattr(app,'_image_polling',False):return
    app._image_polling=True
    def poll():
        try:
            started=time.perf_counter()
            for index in range(5):
                try:owner,callback,result=app._image_results.get_nowait()
                except queue.Empty:break
                app._image_pending-=1
                if is_current(owner) and owner.winfo_exists():callback(result)
                # คืนเวลาให้เมาส์และหน้าจอเมื่อใช้เวลาวาดภาพครบงบของรอบนี้
                if time.perf_counter()-started>=.006:break
            if app._image_pending:app.after(20,poll)
            else:app._image_polling=False
        except tk.TclError:app._image_polling=False
    app.after(20,poll)
