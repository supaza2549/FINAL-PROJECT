"""สร้างส่วนหัวอีเมลธุรกรรมให้สม่ำเสมอ โดยไม่ปลอมผลยืนยันผู้ส่ง"""
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import formataddr,formatdate,make_msgid
import db

def create(sender,recipient,subject):
    sender=str(sender).strip();recipient=str(recipient).strip()
    db.validate_email(sender);db.validate_email(recipient)
    msg=EmailMessage(policy=SMTP)
    msg['From']=formataddr(('JPZ Pizza Jeans',sender));msg['To']=recipient
    msg['Reply-To']=sender;msg['Date']=formatdate(usegmt=True)
    msg['Message-ID']=make_msgid(domain=sender.rsplit('@',1)[1])
    msg['Auto-Submitted']='auto-generated';msg['Subject']=subject
    return msg
