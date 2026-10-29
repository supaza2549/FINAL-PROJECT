"""Email verification and recovery for the local JPZ application.

SMTP secrets are read only from the administrator's protected configuration.
Challenges never store plaintext passwords or codes. Mail is sent outside a DB lock.
"""
import hashlib,hmac,json,secrets,time,ssl,smtplib,html
from email.message import EmailMessage
from email.utils import formatdate,make_msgid,formataddr
import db
from support import service_settings

INVALID='OTP ไม่ถูกต้อง ถูกใช้แล้ว หรือหมดอายุ กรุณาขอใหม่ / Invalid, used or expired OTP. Request a new code.'

def migrate(c):
    db.add_column_if_missing(c,'users','email_verified','INTEGER DEFAULT 0')
    c.execute('''CREATE TABLE IF NOT EXISTS email_challenges(
        token_hash TEXT PRIMARY KEY,email TEXT NOT NULL,purpose TEXT NOT NULL,
        code_hash TEXT NOT NULL,payload TEXT NOT NULL,created_at REAL NOT NULL,
        expires_at REAL NOT NULL,attempts INTEGER DEFAULT 0,consumed INTEGER DEFAULT 0,
        delivered INTEGER DEFAULT 0)''')
    c.execute('CREATE INDEX IF NOT EXISTS email_challenge_recency ON email_challenges(email,created_at)')

def digest(value):return hashlib.sha256(value.encode()).hexdigest()

def send_message(email,code,purpose):
    import receipt
    cfg=receipt.config()
    password=service_settings.get('JPZ_SMTP_PASSWORD')
    if not all(cfg.get(k) for k in ('host','sender','username')) or not password or cfg.get('security') not in ('STARTTLS','SSL'):
        raise ValueError('ร้านยังไม่ได้ตั้งค่าอีเมลสำหรับส่ง OTP กรุณาติดต่อร้าน / Store email is not configured for OTP.')
    from support import mail_message
    subject='ยืนยันอีเมล' if purpose=='register' else 'ตั้งรหัสผ่านใหม่'
    msg=mail_message.create(cfg['sender'],email,'JPZ | รหัส OTP สำหรับ'+subject)
    msg.set_content(f'รหัส OTP ของคุณ / Your OTP: {code}\n\nใช้ได้ 10 นาที ใช้ได้ครั้งเดียว / Valid for 10 minutes, single use.\nหากคุณไม่ได้ร้องขอ สามารถละเว้นอีเมลนี้ได้ / If you did not request this, ignore this email.\nJPZ · DENIM MADE PERSONAL.')
    # มีทั้งข้อความและ HTML ที่ให้ข้อมูลตรงกัน อ่านได้แม้โปรแกรมอีเมลปิดภาพ
    msg.add_alternative('<html><body style="font-family:Arial,sans-serif;color:#243E55">'
        '<h2>JPZ Pizza Jeans</h2><p>รหัส OTP สำหรับ'+subject+'</p>'
        '<p style="font-size:28px;font-weight:bold;letter-spacing:4px">'+html.escape(str(code))+'</p>'
        '<p>รหัสใช้ได้ 10 นาทีและใช้ได้ครั้งเดียว อย่าให้รหัสนี้แก่ผู้อื่น</p>'
        '<p>หากคุณไม่ได้ร้องขอรหัสนี้ สามารถละเว้นอีเมลนี้ได้</p></body></html>',subtype='html')
    try:
        factory=smtplib.SMTP_SSL if cfg['security']=='SSL' else smtplib.SMTP
        with factory(cfg['host'],int(cfg['port']),timeout=20,**({'context':ssl.create_default_context()} if cfg['security']=='SSL' else {})) as smtp:
            if cfg['security']=='STARTTLS':smtp.starttls(context=ssl.create_default_context())
            smtp.login(cfg['username'],password);smtp.send_message(msg)
    except Exception:
        raise ValueError('ส่ง OTP ทางอีเมลไม่สำเร็จ กรุณาลองใหม่หรือติดต่อร้าน / Email OTP delivery failed. Try again or contact the store.') from None

def send(email,purpose,details=None):
    db.validate_email(email);email=email.strip().casefold()
    if purpose not in ('register','reset'):raise ValueError('Invalid verification purpose.')
    payload={}
    if purpose=='register':
        details=dict(details or {})
        db.validate_password(details.get('password',''));phone=db.validate_phone(details.get('phone',''))
        fn=details.get('first_name','').strip();ln=details.get('last_name','').strip()
        if not fn or not ln:raise ValueError('กรอกชื่อและนามสกุล / Enter first and last names.')
        payload=dict(first_name=fn,last_name=ln,phone=phone,password_hash=db.hash_password(details['password']),language='EN' if details.get('language')=='EN' else 'TH')
    token=secrets.token_urlsafe(32);code=f'{secrets.randbelow(1000000):06d}';now=time.time();c=db.conn()
    try:
        c.execute('BEGIN IMMEDIATE')
        user=c.execute('SELECT * FROM users WHERE lower(email)=?',(email,)).fetchone()
        if purpose=='register' and user:raise ValueError('อีเมลนี้ถูกใช้งานแล้ว / Email already registered.')
        recent=c.execute('SELECT MAX(created_at),COUNT(*) FROM email_challenges WHERE email=? AND created_at>?',(email,now-3600)).fetchone()
        if recent[0] is not None and now-recent[0]<60:raise ValueError('รอ 60 วินาทีก่อนขอ OTP ใหม่ / Wait 60 seconds before requesting another OTP.')
        if recent[1]>=10 or c.execute('SELECT COUNT(*) FROM email_challenges WHERE created_at>?',(now-3600,)).fetchone()[0]>=100:
            raise ValueError('ขอ OTP บ่อยเกินไป กรุณาลองภายหลัง / Too many OTP requests. Try later.')
        if purpose=='reset':
            # Unknown/inactive accounts get a matching opaque challenge but no email.
            payload=dict(user_id=user['id'],password_hash=user['password_hash'],role=user['role']) if user and user['active'] else {}
        c.execute('UPDATE email_challenges SET consumed=1 WHERE email=?',(email,))
        c.execute('INSERT INTO email_challenges(token_hash,email,purpose,code_hash,payload,created_at,expires_at) VALUES(?,?,?,?,?,?,?)',
                  (digest(token),email,purpose,digest(token+'|'+code),json.dumps(payload),now,now+600))
        c.commit()
        if purpose=='register' or payload:send_message(email,code,purpose)
        c.execute('UPDATE email_challenges SET delivered=1 WHERE token_hash=?',(digest(token),));c.commit()
        return token
    except Exception:
        c.rollback();c.execute('UPDATE email_challenges SET consumed=1 WHERE token_hash=?',(digest(token),));c.commit();raise
    finally:c.close()

# J07 | ตรวจ OTP อีเมล
def complete(token,email,purpose,code,new_password=None):
    if purpose not in ('register','reset'):raise ValueError(INVALID)
    if purpose=='reset':db.validate_password(new_password)
    c=db.conn()
    try:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT * FROM email_challenges WHERE token_hash=?',(digest(token),)).fetchone()
        if not row or row['consumed'] or not row['delivered'] or row['expires_at']<time.time() or row['attempts']>=5 or row['email']!=email.strip().casefold() or row['purpose']!=purpose:
            raise ValueError(INVALID)
        c.execute('UPDATE email_challenges SET attempts=attempts+1 WHERE token_hash=?',(row['token_hash'],))
        if not hmac.compare_digest(row['code_hash'],digest(token+'|'+code.strip())):
            c.commit();raise ValueError(INVALID)
        payload=json.loads(row['payload'])
        if purpose=='register':
            if c.execute('SELECT 1 FROM users WHERE lower(email)=?',(row['email'],)).fetchone():raise ValueError('อีเมลนี้ถูกใช้งานแล้ว / Email already registered.')
            c.execute('INSERT INTO users(first_name,last_name,email,password_hash,language,phone,registered_phone,email_verified) VALUES(?,?,?,?,?,?,?,1)',
                      (payload['first_name'],payload['last_name'],row['email'],payload['password_hash'],payload['language'],payload['phone'],payload['phone']))
        else:
            if not payload:raise ValueError(INVALID)
            updated=c.execute('UPDATE users SET password_hash=?,email_verified=1 WHERE id=? AND lower(email)=? AND password_hash=? AND role=? AND active=1',
                              (db.hash_password(new_password),payload['user_id'],row['email'],payload['password_hash'],payload['role']))
            if updated.rowcount!=1:raise ValueError(INVALID)
            c.execute('UPDATE password_challenges SET consumed=1 WHERE user_id=?',(payload['user_id'],))
        c.execute('UPDATE email_challenges SET consumed=1 WHERE email=?',(row['email'],));c.commit();return True
    except Exception:c.rollback();raise
    finally:c.close()
