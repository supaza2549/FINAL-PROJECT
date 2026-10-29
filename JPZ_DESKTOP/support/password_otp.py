"""SMS password recovery. Provider credentials stay outside the application files."""
import base64
import hashlib
import json
import os
import re
import secrets
import time
from urllib import request, parse, error
import db


def migrate(c):
    db.add_column_if_missing(c,'users','phone',"TEXT DEFAULT ''")
    db.add_column_if_missing(c,'users','registered_phone',"TEXT DEFAULT ''")
    c.execute("UPDATE users SET registered_phone=phone WHERE registered_phone='' AND length(phone)=10")
    c.execute('''CREATE TABLE IF NOT EXISTS password_challenges(
        token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, email TEXT NOT NULL,
        phone TEXT NOT NULL, provider_sid TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL, expires_at REAL NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0, consumed INTEGER NOT NULL DEFAULT 0)''')


class TwilioVerify:
    def __init__(self):
        self.account = os.environ.get('TWILIO_ACCOUNT_SID', '')
        self.secret = os.environ.get('TWILIO_AUTH_TOKEN', '')
        self.service = os.environ.get('TWILIO_VERIFY_SERVICE_SID', '')
        if not (re.fullmatch(r'AC[0-9a-fA-F]{32}', self.account)
                and self.secret and re.fullmatch(r'VA[0-9a-fA-F]{32}', self.service)):
            raise ValueError('ร้านยังไม่ได้เปิดบริการ SMS OTP กรุณาติดต่อร้าน / SMS OTP is not configured. Contact the store.')

    def post(self, resource, values):
        auth = base64.b64encode(f'{self.account}:{self.secret}'.encode()).decode()
        req = request.Request(
            f'https://verify.twilio.com/v2/Services/{self.service}/{resource}',
            data=parse.urlencode(values).encode(),
            headers={'Authorization': f'Basic {auth}', 'Content-Type': 'application/x-www-form-urlencoded'},
            method='POST')
        try:
            with request.urlopen(req, timeout=20) as response:
                return json.load(response)
        except error.HTTPError as exc:
            if exc.code == 404:
                raise ValueError('OTP หมดอายุแล้ว กรุณาขอใหม่ / OTP expired. Request a new code.') from None
            raise ValueError('ส่งหรือตรวจ OTP ไม่สำเร็จ กรุณาลองใหม่หรือติดต่อร้าน / SMS verification failed. Try again or contact the store.') from None
        except (error.URLError, TimeoutError, OSError, ValueError):
            raise ValueError('เชื่อมต่อบริการ OTP ไม่สำเร็จ กรุณาลองใหม่ / Cannot connect to SMS service. Try again.') from None

    def send(self, phone):
        result = self.post('Verifications', {'To': '+66' + phone[1:], 'Channel': 'sms'})
        if result.get('status') != 'pending' or not result.get('sid'):
            raise ValueError('ส่ง OTP ไม่สำเร็จ / Unable to send OTP.')
        return result['sid']

    def check(self, sid, code):
        return self.post('VerificationCheck', {'VerificationSid': sid, 'Code': code}).get('status') == 'approved'


def _key(token):
    return hashlib.sha256(token.encode()).hexdigest()


def send(email, phone):
    db.validate_email(email)
    email = email.strip()
    phone = db.validate_phone(phone)
    if not phone.startswith('0'):
        raise ValueError('เบอร์โทรต้องขึ้นต้นด้วย 0 / Phone number must start with 0.')
    provider = TwilioVerify()
    token = secrets.token_urlsafe(32)
    now = time.time()
    c = db.conn()
    try:
        c.execute('BEGIN IMMEDIATE')
        user = c.execute('SELECT id FROM users WHERE lower(email)=lower(?) AND registered_phone=? AND active=1', (email, phone)).fetchone()
        if not user:
            raise ValueError('อีเมลและเบอร์โทรไม่ตรงกับบัญชี / Email and phone do not match the account.')
        recent = c.execute('SELECT MAX(created_at) FROM password_challenges WHERE user_id=?', (user['id'],)).fetchone()[0]
        if recent and now - recent < 60:
            raise ValueError('กรุณารอ 60 วินาทีก่อนขอ OTP ใหม่ / Wait 60 seconds before requesting another OTP.')
        c.execute('UPDATE password_challenges SET consumed=1 WHERE user_id=?', (user['id'],))
        c.execute('INSERT INTO password_challenges(token_hash,user_id,email,phone,created_at,expires_at) VALUES(?,?,?,?,?,?)',
                  (_key(token), user['id'], email, phone, now, now + 600))
        c.commit()
        sid = provider.send(phone)
        c.execute('UPDATE password_challenges SET provider_sid=? WHERE token_hash=?', (sid, _key(token)))
        c.commit()
        return token
    except Exception:
        c.rollback()
        c.execute('UPDATE password_challenges SET consumed=1 WHERE token_hash=?', (_key(token),))
        c.commit()
        raise
    finally:
        c.close()


def reset(token, email, phone, code, new_password):
    db.validate_password(new_password)
    if not re.fullmatch(r'[0-9]{4,10}', code):
        raise ValueError('กรอก OTP เป็นตัวเลข 4–10 หลัก / Enter the 4–10 digit OTP.')
    provider = TwilioVerify()
    c = db.conn()
    try:
        c.execute('BEGIN IMMEDIATE')
        row = c.execute('SELECT * FROM password_challenges WHERE token_hash=?', (_key(token),)).fetchone()
        if (not row or row['consumed'] or row['expires_at'] < time.time() or row['attempts'] >= 5
                or not row['provider_sid'] or row['email'].casefold() != email.strip().casefold() or row['phone'] != phone.strip()):
            raise ValueError('OTP ใช้งานไม่ได้ กรุณาขอใหม่ / OTP is unavailable. Request a new code.')
        c.execute('UPDATE password_challenges SET attempts=attempts+1 WHERE token_hash=?', (_key(token),))
        c.commit()
        if not provider.check(row['provider_sid'], code):
            raise ValueError('OTP ไม่ถูกต้อง / Incorrect OTP.')
        c.execute('BEGIN IMMEDIATE')
        result = c.execute('UPDATE password_challenges SET consumed=1 WHERE token_hash=? AND consumed=0 AND expires_at>=?', (_key(token), time.time()))
        if result.rowcount != 1:
            raise ValueError('OTP ถูกใช้แล้วหรือหมดอายุ / OTP was used or expired.')
        result = c.execute('UPDATE users SET password_hash=? WHERE id=? AND lower(email)=lower(?) AND registered_phone=? AND active=1',
                           (db.hash_password(new_password), row['user_id'], row['email'], row['phone']))
        if result.rowcount != 1:
            raise ValueError('ข้อมูลบัญชีเปลี่ยนไป กรุณาขอ OTP ใหม่ / Account changed. Request a new OTP.')
        c.commit()
        return True
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()
