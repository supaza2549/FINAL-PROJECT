"""Public store address is stored separately from account delivery details."""
import json
import db
from support import admin_data


def address():
    c = db.conn()
    try:
        row = c.execute("SELECT value FROM shop_metadata WHERE key='store_address'").fetchone()
    finally:
        c.close()
    try:
        values = json.loads(row['value']) if row else {}
        if not isinstance(values, dict):values = {}
    except (ValueError, TypeError):values = {}
    return {key: str(values.get(key, default)).strip() for key, default in
            (('name', 'JPZ / PIZZA JEANS'), ('address', ''), ('postal_code', ''))}


def save_account(actor, account, store):
    values = {key: str(account.get(key, '')).strip() for key in ('first_name', 'last_name', 'email', 'phone')}
    if not values['first_name'] or not values['last_name']:raise ValueError('Enter your first and last name.')
    db.validate_phone(values['phone'])
    db.validate_email(values['email'])
    public = {key: str(store.get(key, '')).strip() for key in ('name', 'address', 'postal_code')}
    postal = public['postal_code']
    if postal and (len(postal) != 5 or not postal.isascii() or not postal.isdigit()):raise ValueError('Postal code must contain 5 digits.')
    with admin_data.transaction(actor) as c:
        c.execute('UPDATE users SET first_name=?,last_name=?,email=?,phone=? WHERE id=?',
                  (*values.values(), actor))
        c.execute("INSERT INTO shop_metadata(key,value) VALUES('store_address',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  (json.dumps(public, ensure_ascii=False),))
        admin_data.audit(c, actor, 'store_address_saved', 'store_address', 'Store address and administrator account updated')
