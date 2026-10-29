import sqlite3
import hashlib
import secrets
from datetime import datetime


DATABASE = "find_your_fit.db"


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# =========================================================
# PASSWORD SECURITY
# =========================================================

def hash_password(password):
    salt = secrets.token_hex(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120000
    ).hex()

    return f"{salt}${password_hash}"


def check_password(password, stored_password):
    try:
        salt, saved_hash = stored_password.split("$", 1)

        test_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            120000
        ).hex()

        return secrets.compare_digest(
            test_hash,
            saved_hash
        )

    except (ValueError, AttributeError):
        return False


# =========================================================
# CREATE DATABASE
# =========================================================

def create_database():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'customer',
            language TEXT NOT NULL DEFAULT 'TH',
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT UNIQUE NOT NULL,
            price INTEGER NOT NULL,
            fit TEXT NOT NULL,
            color TEXT NOT NULL,
            waist REAL NOT NULL,
            hip REAL NOT NULL,
            thigh REAL NOT NULL,
            rise REAL NOT NULL,
            inseam REAL NOT NULL,
            leg_opening REAL NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            total INTEGER NOT NULL,
            payment_status TEXT NOT NULL DEFAULT 'waiting_payment',
            order_status TEXT NOT NULL DEFAULT 'waiting_payment',
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            price INTEGER NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            receipt_path TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )
    """)

    create_demo_users(conn)
    create_demo_products(conn)

    conn.commit()
    conn.close()


# =========================================================
# DEMO USERS
# =========================================================

def create_demo_users(conn):
    demo_users = [
        (
            "Demo",
            "Customer",
            "demo@findyourfit.local",
            "demo1234",
            "customer",
            "TH"
        ),
        (
            "System",
            "Admin",
            "admin@findyourfit.local",
            "admin1234",
            "admin",
            "TH"
        )
    ]

    for first_name, last_name, email, password, role, language in demo_users:

        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if existing is None:
            conn.execute("""
                INSERT INTO users (
                    first_name,
                    last_name,
                    email,
                    password_hash,
                    role,
                    language,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                first_name,
                last_name,
                email,
                hash_password(password),
                role,
                language,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))


# =========================================================
# DEMO PRODUCTS
# =========================================================

def create_demo_products(conn):
    products = [
        (
            "VOID BAGGY 01",
            "VBG-01",
            1290,
            "baggy",
            "dark_indigo",
            32,
            42,
            26,
            12.5,
            32,
            19,
            8
        ),
        (
            "RAW STRAIGHT 02",
            "RST-02",
            1390,
            "straight",
            "deep_indigo",
            32,
            40,
            24,
            11.5,
            32,
            16,
            6
        ),
        (
            "FADED RELAX 03",
            "FRX-03",
            1190,
            "relaxed",
            "washed_blue",
            33,
            43,
            26,
            12,
            31.5,
            18,
            10
        ),
        (
            "BLACK FORM 04",
            "BFM-04",
            1490,
            "straight",
            "black",
            31,
            39,
            23.5,
            11,
            32,
            15.5,
            7
        ),
        (
            "ARCHIVE WIDE 05",
            "AWD-05",
            1590,
            "wide",
            "light_blue",
            32,
            44,
            27,
            13,
            32.5,
            21,
            5
        ),
        (
            "GREY MOTION 06",
            "GMT-06",
            1290,
            "loose",
            "grey",
            32,
            42,
            25.5,
            12,
            32,
            18.5,
            9
        )
    ]

    for product in products:
        existing = conn.execute(
            "SELECT id FROM products WHERE code = ?",
            (product[1],)
        ).fetchone()

        if existing is None:
            conn.execute("""
                INSERT INTO products (
                    name,
                    code,
                    price,
                    fit,
                    color,
                    waist,
                    hip,
                    thigh,
                    rise,
                    inseam,
                    leg_opening,
                    stock
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, product)


# =========================================================
# LOGIN
# =========================================================

def login_user(email, password):
    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE LOWER(email) = LOWER(?)",
        (email.strip(),)
    ).fetchone()

    conn.close()

    if user and check_password(
        password,
        user["password_hash"]
    ):
        return dict(user)

    return None


# =========================================================
# REGISTER
# =========================================================

def register_user(
    first_name,
    last_name,
    email,
    password,
    language="TH"
):
    conn = get_db()

    try:
        cursor = conn.execute("""
            INSERT INTO users (
                first_name,
                last_name,
                email,
                password_hash,
                role,
                language,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            first_name.strip(),
            last_name.strip(),
            email.strip().lower(),
            hash_password(password),
            "customer",
            language,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        conn.commit()

        user_id = cursor.lastrowid

        user = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        return dict(user)

    except sqlite3.IntegrityError:
        return None

    finally:
        conn.close()


# =========================================================
# UPDATE LANGUAGE
# =========================================================

def update_user_language(user_id, language):
    conn = get_db()

    conn.execute(
        "UPDATE users SET language = ? WHERE id = ?",
        (language, user_id)
    )

    conn.commit()
    conn.close()