"""Local camera preview. No network calls and no files written before avatar save."""
import sys
import threading
import queue
import time
from pathlib import Path
import tkinter as tk
from PIL import Image,ImageTk,ImageOps


def load_camera():
    bundled=Path(__file__).resolve().parents[1]/'vendor/camera_runtime'/f'cp{sys.version_info.major}{sys.version_info.minor}'
    if bundled.is_dir():sys.path.insert(0,str(bundled))
    import cv2
    return cv2


class CameraDialog(tk.Toplevel):
    def __init__(self,app,on_capture):
        super().__init__(app)
        self.app=app;self.on_capture=on_capture;self.stopped=threading.Event()
        self.opened_at=time.monotonic()
        self.frames=queue.Queue(maxsize=1);self.errors=queue.Queue();self.latest=None;self.closed=False
        self.title(app.ui('ถ่ายรูปโปรไฟล์','Take a profile photo'));self.configure(bg='white')
        self.geometry('860x760');self.minsize(650,600);self.transient(app)
        self.protocol('WM_DELETE_WINDOW',self.close);self.bind('<Escape>',lambda e:(self.close(),'break')[1])
        self.bind('<Destroy>',lambda e:self.stopped.set() if e.widget is self else None)
        app.label(self,app.ui('กล้องสำหรับรูปโปรไฟล์','Profile camera'),22,True).pack(anchor='w',padx=24,pady=(20,8))
        app.label(self,app.ui('ภาพใช้ในเครื่องนี้ ถ่ายแล้วจัดตำแหน่งก่อนบันทึก','Photo stays on this device. Adjust the crop before saving.'),11,wraplength=800).pack(anchor='w',padx=24,pady=(0,12))
        footer=tk.Frame(self,bg='white');footer.pack(side='bottom',fill='x',padx=24,pady=16)
        self.capture_button=app.button(footer,app.ui('ถ่ายรูป','Take photo'),self.capture,dark=True);self.capture_button.pack(side='right');self.capture_button.configure(state='disabled')
        app.button(footer,app.ui('ยกเลิก / ปิดกล้อง','Cancel / close camera'),self.close).pack(side='left')
        self.status=app.label(self,app.ui('กำลังเปิดกล้อง…','Opening camera…'),11,wraplength=780,justify='left');self.status.pack(side='bottom',padx=24,pady=8)
        self.preview=tk.Label(self,bg='#17212B');self.preview.pack(fill='both',expand=True,padx=24,pady=8)
        try:self.cv=load_camera()
        except (ImportError,OSError) as exc:
            self.status.configure(text=app.ui('เปิดกล้องไม่ได้: กรุณาติดตั้ง numpy และ opencv-python ให้ตรงกับ Python ที่ใช้','Camera unavailable: install numpy and opencv-python for your Python version.'),fg='#BB2020');return
        self.worker=threading.Thread(target=self.read_camera,daemon=True);self.worker.start()
        self.after(40,self.poll)

    def read_camera(self):
        cap=None
        try:
            # An opened device is insufficient: DirectShow can open without delivering frames.
            # Try actual frames before choosing a backend/device; retain its default resolution.
            initial=None
            for device in range(3):
                for backend in (self.cv.CAP_MSMF,self.cv.CAP_DSHOW):
                    if self.stopped.is_set():return
                    cap=self.cv.VideoCapture(device,backend)
                    if cap.isOpened():
                        for attempt in range(8):
                            if self.stopped.is_set():return
                            ok,frame=cap.read()
                            if ok and frame is not None:
                                initial=frame;break
                            self.stopped.wait(.05)
                    if initial is not None:break
                    cap.release();cap=None
                if initial is not None:break
            if cap is None or initial is None:
                raise RuntimeError(self.app.ui('ไม่พบภาพจากกล้อง ตรวจสิทธิ์กล้องสำหรับแอปเดสก์ท็อป ปิดแอปอื่นที่ใช้กล้อง และเปิดฝาปิดเลนส์','No camera frames. Allow desktop camera access, close other camera apps and open the lens cover.'))
            failures=0
            while not self.stopped.is_set():
                if initial is not None:
                    ok,frame=True,initial;initial=None
                else:ok,frame=cap.read()
                if not ok:
                    failures+=1
                    if failures>=30:raise RuntimeError(self.app.ui('อ่านภาพจากกล้องไม่ได้ กรุณาปิดแล้วเปิดใหม่','Cannot read camera. Close and try again.'))
                    self.stopped.wait(.05);continue
                failures=0
                # Mirror both preview and captured image so the result matches what the user sees.
                image=ImageOps.mirror(Image.fromarray(self.cv.cvtColor(frame,self.cv.COLOR_BGR2RGB)))
                try:self.frames.get_nowait()
                except queue.Empty:pass
                self.frames.put_nowait(image)
                self.stopped.wait(.03)
        except Exception as exc:self.errors.put(str(exc))
        finally:
            if cap is not None:cap.release()

    def poll(self):
        if self.closed:return
        try:
            error=self.errors.get_nowait();self.status.configure(text=error,fg='#BB2020');self.capture_button.configure(state='disabled');return
        except queue.Empty:pass
        try:self.latest=self.frames.get_nowait()
        except queue.Empty:pass
        if self.latest is None and time.monotonic()-self.opened_at>12:
            self.stopped.set()
            self.status.configure(text=self.app.ui('กล้องไม่ส่งภาพ กรุณาตรวจสิทธิ์กล้อง เปิดฝาปิดเลนส์ และปิดโปรแกรมอื่นที่ใช้กล้อง แล้วเปิดหน้านี้ใหม่','Camera did not respond. Check permissions and lens cover, close other camera apps, then reopen this dialog.'),fg='#BB2020')
            return
        if self.latest is not None:
            size=(max(100,self.preview.winfo_width()),max(100,self.preview.winfo_height()))
            image=ImageOps.pad(self.latest,size,color='#17212B',method=Image.Resampling.LANCZOS)
            self.photo=ImageTk.PhotoImage(image,master=self);self.preview.configure(image=self.photo)
            self.capture_button.configure(state='normal');self.status.configure(text=self.app.ui('กล้องกำลังเปิด · กดถ่ายรูปเมื่อพร้อม','Camera is on · take a photo when ready'))
        self.after(40,self.poll)

    def capture(self):
        if self.latest is None:return
        image=self.latest.copy();self.close();self.app.after_idle(lambda:self.on_capture(image))

    def close(self):
        if self.closed:return
        self.closed=True;self.stopped.set();self.destroy()
