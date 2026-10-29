"""Windows-user protected service settings; not part of the distributed archive."""
import ctypes
from ctypes import wintypes
import json,os,tempfile,threading
from pathlib import Path
import db
_KEYS=('JPZ_EASYSLIP_API_KEY','JPZ_EASYSLIP_BANK_NUMBER','JPZ_RECEIPT_EMAIL','JPZ_SMTP_SENDER','JPZ_SMTP_USERNAME','JPZ_SMTP_HOST','JPZ_SMTP_PORT','JPZ_SMTP_SECURITY','JPZ_SMTP_PASSWORD')
_lock=threading.RLock();_cache={}

def _path():return Path(db.BASE_DIR)/'.private'/'services.dpapi'

class Blob(ctypes.Structure):
    _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_ubyte))]

def _crypt(content,decrypt=False):
    if os.name!='nt':raise OSError('การบันทึกรหัสบริการรองรับ Windows เท่านั้น / Protected settings require Windows.')
    buf=ctypes.create_string_buffer(content);source=Blob(len(content),ctypes.cast(buf,ctypes.POINTER(ctypes.c_ubyte)));result=Blob()
    api=ctypes.WinDLL('crypt32',use_last_error=True)
    if decrypt:
        ok=api.CryptUnprotectData(ctypes.byref(source),None,None,None,None,1,ctypes.byref(result))
    else:
        ok=api.CryptProtectData(ctypes.byref(source),'JPZ service settings',None,None,None,1,ctypes.byref(result))
    if not ok:raise OSError('อ่าน/บันทึกการตั้งค่าที่ป้องกันไว้ไม่ได้ กรุณาใช้บัญชี Windows เดิม / Cannot access protected settings; use the original Windows account.')
    try:return ctypes.string_at(result.pbData,result.cbData)
    finally:
        kernel=ctypes.WinDLL('kernel32');kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree(ctypes.cast(result.pbData,ctypes.c_void_p))

def stored():
    path=_path()
    with _lock:
        stamp=(path.stat().st_mtime_ns,path.stat().st_size) if path.exists() else None
        cached=_cache.get(str(path))
        if cached and cached[0]==stamp:return dict(cached[1])
        values=json.loads(_crypt(path.read_bytes(),True).decode('utf-8')) if stamp else {}
        clean={k:str(v) for k,v in values.items() if k in _KEYS}
        _cache[str(path)]=(stamp,clean);return dict(clean)

def get(key,default=''):
    from support import mail_config
    connection={'JPZ_SMTP_HOST':mail_config.SMTP_HOST,'JPZ_SMTP_PORT':str(mail_config.SMTP_PORT),'JPZ_SMTP_SECURITY':mail_config.SMTP_SECURITY}
    if key in connection:return str(connection[key])
    if key in os.environ:return os.environ[key]
    try:return stored().get(key,default)
    except (OSError,ValueError):return default

def save(actor,values):
    from support import admin_data
    c=db.conn()
    try:admin_data.require_admin(c,actor)
    finally:c.close()
    clean=stored()
    for key,value in values.items():
        if key not in _KEYS:raise ValueError('Unknown service setting.')
        value=str(value).strip()
        if '\n' in value or '\r' in value:raise ValueError('ไม่อนุญาตข้อความหลายบรรทัด / Multi-line values are not allowed.')
        if key in ('JPZ_EASYSLIP_API_KEY','JPZ_SMTP_PASSWORD') and not value:continue
        clean[key]=value
    if clean.get('JPZ_SMTP_SENDER'):
        db.validate_email(clean['JPZ_SMTP_SENDER'])
        if (clean.get('JPZ_SMTP_SENDER')!=stored().get('JPZ_SMTP_SENDER') or clean.get('JPZ_SMTP_USERNAME')!=stored().get('JPZ_SMTP_USERNAME')) and not str(values.get('JPZ_SMTP_PASSWORD','')).strip():
            raise ValueError('เมื่อเปลี่ยนอีเมลผู้ส่ง กรุณาใส่รหัสผ่านแอปของบัญชีใหม่ด้วย / Enter the new account app password when changing sender.')
    if clean.get('JPZ_SMTP_SECURITY') not in ('STARTTLS','SSL'):raise ValueError('เลือก STARTTLS หรือ SSL / Choose STARTTLS or SSL.')
    try:port=int(clean.get('JPZ_SMTP_PORT','587'))
    except ValueError:raise ValueError('พอร์ตอีเมลไม่ถูกต้อง / Invalid mail port.') from None
    if not 1<=port<=65535:raise ValueError('พอร์ตอีเมลไม่ถูกต้อง / Invalid mail port.')
    if clean.get('JPZ_RECEIPT_EMAIL')=='1' and not all(clean.get(k) for k in ('JPZ_SMTP_HOST','JPZ_SMTP_SENDER','JPZ_SMTP_USERNAME','JPZ_SMTP_PASSWORD')):
        raise ValueError('กรอกข้อมูลอีเมลผู้ส่งให้ครบก่อนเปิดส่ง / Complete the sender settings before enabling email.')
    bank=''.join(ch for ch in clean.get('JPZ_EASYSLIP_BANK_NUMBER','') if ch.isascii() and ch.isdigit());clean['JPZ_EASYSLIP_BANK_NUMBER']=bank
    if clean.get('JPZ_EASYSLIP_API_KEY') and not bank:raise ValueError('กรอกเลขบัญชีที่ลงทะเบียนกับ EasySlip / Enter the EasySlip registered bank account.')
    encrypted=_crypt(json.dumps(clean,ensure_ascii=False).encode('utf-8'));path=_path();path.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(dir=path.parent,suffix='.tmp')
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(encrypted)
        os.replace(temp,path)
    finally:
        if Path(temp).exists():Path(temp).unlink()
    with _lock:_cache.pop(str(path),None)
    with admin_data.transaction(actor) as c:admin_data.audit(c,actor,'service_settings_saved','services','Protected EasySlip/email settings updated (secrets excluded)')
    return clean
