TEXT = {
    "TH": {
        # AUTH
        "login": "เข้าสู่ระบบ",
        "register": "สมัครสมาชิก",
        "logout": "ออกจากระบบ",
        "email": "อีเมล",
        "password": "รหัสผ่าน",
        "confirm_password": "ยืนยันรหัสผ่าน",
        "first_name": "ชื่อ",
        "last_name": "นามสกุล",
        "show_password": "แสดงรหัสผ่าน",

        "welcome_back": "ยินดีต้อนรับกลับ",
        "login_subtitle": "เข้าสู่ระบบเพื่อค้นหา FIT ที่เหมาะกับคุณ",
        "no_account": "ยังไม่มีบัญชี?",
        "create_account": "สร้างบัญชี",

        "join_title": "สร้างบัญชี",
        "join_subtitle": "เข้าร่วม FIND YOUR FIT",
        "have_account": "มีบัญชีอยู่แล้ว?",

        "login_failed": "อีเมลหรือรหัสผ่านไม่ถูกต้อง",
        "fill_all": "กรุณากรอกข้อมูลให้ครบ",
        "password_not_match": "รหัสผ่านไม่ตรงกัน",
        "email_exists": "อีเมลนี้ถูกใช้งานแล้ว",

        # NAVIGATION
        "home": "หน้าแรก",
        "shop": "สินค้า",
        "find_fit": "ค้นหา FIT",
        "match_jeans": "เทียบยีนส์",
        "size_guide": "วิธีวัด",
        "cart": "ตะกร้า",
        "orders": "คำสั่งซื้อ",
        "profile": "โปรไฟล์",
        "admin": "แอดมิน",

        # HOME
        "hero_label": "01 / FIND YOUR FORM",

        "hero_title":
            "อย่าหาแค่ SIZE\n"
            "ค้นหา FIT ของคุณ",

        "hero_description":
            "ยีนส์ที่ดีไม่ควรถูกเลือกจาก SIZE เพียงอย่างเดียว\n"
            "ค้นหาทรงและสัดส่วนที่เข้ากับร่างกายของคุณ",

        "find_your_fit": "ค้นหา FIT ของฉัน",
        "shop_myself": "เลือกซื้อด้วยตัวเอง",
        "your_body_matters": "YOUR BODY\nMATTERS.",

        # USER
        "hello": "สวัสดี",
        "customer": "ลูกค้า",
        "administrator": "ผู้ดูแลระบบ",

        # STATUS
        "waiting_payment": "รอชำระเงิน",
        "under_review": "กำลังตรวจสอบ",
        "paid": "ชำระเงินแล้ว",
        "rejected": "หลักฐานไม่ผ่าน",
        "preparing": "กำลังเตรียมสินค้า",
        "shipped": "จัดส่งแล้ว",
        "completed": "สำเร็จ",
    },

    "EN": {
        # AUTH
        "login": "LOGIN",
        "register": "REGISTER",
        "logout": "LOGOUT",
        "email": "EMAIL",
        "password": "PASSWORD",
        "confirm_password": "CONFIRM PASSWORD",
        "first_name": "FIRST NAME",
        "last_name": "LAST NAME",
        "show_password": "SHOW PASSWORD",

        "welcome_back": "WELCOME BACK.",
        "login_subtitle": "Sign in and discover the FIT made for you.",
        "no_account": "Don't have an account?",
        "create_account": "CREATE ACCOUNT",

        "join_title": "CREATE ACCOUNT.",
        "join_subtitle": "Join FIND YOUR FIT.",
        "have_account": "Already have an account?",

        "login_failed": "Incorrect email or password.",
        "fill_all": "Please complete all fields.",
        "password_not_match": "Passwords do not match.",
        "email_exists": "This email is already registered.",

        # NAVIGATION
        "home": "HOME",
        "shop": "SHOP",
        "find_fit": "FIND MY FIT",
        "match_jeans": "MATCH MY JEANS",
        "size_guide": "SIZE GUIDE",
        "cart": "CART",
        "orders": "MY ORDERS",
        "profile": "PROFILE",
        "admin": "ADMIN",

        # HOME
        "hero_label": "01 / FIND YOUR FORM",

        "hero_title":
            "DON'T JUST FIND YOUR SIZE.\n"
            "FIND YOUR FIT.",

        "hero_description":
            "Great denim is more than a SIZE.\n"
            "Discover the silhouette that works with your body.",

        "find_your_fit": "FIND MY FIT",
        "shop_myself": "SHOP MYSELF",
        "your_body_matters": "YOUR BODY\nMATTERS.",

        # USER
        "hello": "HELLO",
        "customer": "CUSTOMER",
        "administrator": "ADMINISTRATOR",

        # STATUS
        "waiting_payment": "WAITING PAYMENT",
        "under_review": "UNDER REVIEW",
        "paid": "PAID",
        "rejected": "REJECTED",
        "preparing": "PREPARING",
        "shipped": "SHIPPED",
        "completed": "COMPLETED",
    }
}


def translate(language, key):
    return TEXT.get(language, TEXT["EN"]).get(key, key)