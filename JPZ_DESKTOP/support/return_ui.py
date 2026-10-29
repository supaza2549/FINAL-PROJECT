import tkinter as tk
import json
import db
import receipt
from support import returns

class ReturnMixin:
    def return_form(self,oid):self.navigate('return',self._return_page,oid)

    # J37 | หน้าคืนสินค้า / คืนเงิน
    def _return_page(self,oid):
        order=receipt.order_for(self.user['id'],oid)
        if not order:return self.my_orders(push=False)
        b=self.scroll_content(self.shell())
        form=tk.Frame(b,bg='white');form.pack(fill='x',padx=30,pady=20)
        self.label(form,self.ui('ขอคืนสินค้า','Request a return'),26,True).pack(anchor='w')
        self.label(form,db.order_number(order),12,True).pack(anchor='w',pady=10)
        self.label(form,self.ui('กรอกจำนวนที่ต้องการคืน เหตุผล และบัญชีรับเงินคืน ร้านจะตรวจสอบก่อนดำเนินการ','Enter quantities, reason and refund account. The store reviews your request before processing.'),11,wraplength=900).pack(anchor='w',pady=8)
        existing=returns.for_customer(self.user['id'],oid)
        names={'pending':self.ui('รอตรวจสอบ','Pending review'),'approved':self.ui('ร้านรับคำขอแล้ว','Approved'),'rejected':self.ui('ร้านปฏิเสธคำขอ','Rejected'),'refunded':self.ui('บันทึกคืนเงินแล้ว','Refund recorded')}
        if existing:
            self.label(form,names[existing['status']],14,True).pack(anchor='w',pady=8)
            if existing['admin_note']:self.label(form,existing['admin_note'],11,wraplength=900).pack(anchor='w',pady=8)
        chosen={r['item_id']:r['quantity'] for r in json.loads(existing['items'])} if existing else {}
        quantities={}
        for item in receipt.customer_items(self.user['id'],oid):
            row=tk.Frame(form,bg='#F1F5F8');row.pack(fill='x',pady=6)
            self.label(row,f"{item['name']} / {self.color_label(item['color'])} / {db.size_label(item['size'])}",12,True,bg='#F1F5F8',wraplength=850).pack(anchor='w',padx=14,pady=8)
            self.label(row,self.ui(f"ซื้อ {item['quantity']} ตัว · จำนวนที่ขอคืน (0 = ไม่คืน)",f"Purchased {item['quantity']} · return quantity (0 = keep)"),11,bg='#F1F5F8').pack(anchor='w',padx=14)
            entry=self.entry(row,self.ui('จำนวนคืน','Quantity to return'));entry.insert(0,str(chosen.get(item['id'],0)));quantities[item['id']]=entry
        reason=self.entry(form,self.ui('เหตุผลที่ต้องการคืนสินค้า','Reason for return'))
        if existing:reason.insert(0,existing['reason'])
        bank={}
        defaults={'bank':order.get('refund_bank') or self.user.get('refund_bank',''),'name':order.get('refund_name') or self.user.get('refund_name',''),'account':order.get('refund_account') or self.user.get('refund_account','')}
        if existing:defaults=dict(bank=existing['bank'],name=existing['account_name'],account=existing['account_number'])
        for key,th,en in [('bank','ธนาคาร','Bank'),('name','ชื่อเจ้าของบัญชี','Account holder'),('account','เลขบัญชีรับเงินคืน','Refund account number')]:
            bank[key]=self.entry(form,self.ui(th,en));bank[key].insert(0,defaults[key])
        status=self.label(form,'',11,fg='#BB2020',wraplength=900);status.pack(anchor='w',pady=10)
        def save():
            try:
                returns.submit(self.user['id'],oid,reason.get(),{k:int(v.get()) for k,v in quantities.items()},{k:v.get() for k,v in bank.items()})
                self.user=db.user(self.user['id']);self._return_page(oid)
                self.toast(self.ui('ส่งคำขอคืนสินค้าแล้ว','Return request submitted.'))
            except (ValueError,PermissionError) as exc:status.configure(text=str(exc))
        button=self.button(form,self.ui('ส่งคำขอคืนสินค้า','Submit return request'),save,dark=True);button.pack(anchor='w',pady=10)
        if existing and existing['status'] not in ('pending','rejected'):button.configure(state='disabled')
        self._return_form_ui=dict(quantities=quantities,bank=bank,reason=reason,save=button,status=status)
