import tkinter as tk
from tkinter import messagebox

from database import (
    create_database,
    login_user,
    register_user,
    update_user_language
)

from language import translate


# ============================================================
# FIND YOUR FIT — DESIGN SYSTEM V2
# Fashion Editorial / Neo-Brutalist / Luxury Streetwear
# ============================================================

BLACK = "#090909"
WHITE = "#F7F7F2"
PURE_WHITE = "#FFFFFF"
RED = "#FF2A16"
GREY = "#777773"
LIGHT_GREY = "#D9D9D3"
SOFT_GREY = "#ECECE7"


class FindYourFitApp(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("FIND YOUR FIT®")
        self.geometry("1360x800")
        self.minsize(1100, 680)

        self.configure(bg=WHITE)

        self.language = "TH"
        self.current_user = None
        self.current_page = "login"

        self.cart = []

        self.container = tk.Frame(
            self,
            bg=WHITE
        )
        self.container.pack(
            fill="both",
            expand=True
        )

        self.show_login()

    # ========================================================
    # HELPERS
    # ========================================================

    def t(self, key):
        return translate(
            self.language,
            key
        )

    def font(self, size, weight="normal"):
        if self.language == "TH":
            return (
                "Leelawadee UI",
                size,
                weight
            )

        return (
            "Arial",
            size,
            weight
        )

    def clear(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    # ========================================================
    # LANGUAGE
    # ========================================================

    def change_language(self, language):

        self.language = language

        if self.current_user:

            update_user_language(
                self.current_user["id"],
                language
            )

            self.current_user["language"] = language

        if self.current_page == "login":
            self.show_login()

        elif self.current_page == "register":
            self.show_register()

        elif self.current_page == "home":
            self.show_home()

        elif self.current_page == "admin":
            self.show_admin_home()

    def language_switch(self, parent, dark=False):

        bg = BLACK if dark else WHITE
        normal = "#777777" if not dark else "#888888"

        frame = tk.Frame(
            parent,
            bg=bg
        )

        tk.Button(
            frame,
            text="TH",
            command=lambda: self.change_language("TH"),
            bg=bg,
            fg=RED if self.language == "TH" else normal,
            activebackground=bg,
            activeforeground=RED,
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=("Arial", 8, "bold"),
            cursor="hand2"
        ).pack(side="left")

        tk.Label(
            frame,
            text="/",
            bg=bg,
            fg=normal,
            font=("Arial", 8)
        ).pack(
            side="left",
            padx=3
        )

        tk.Button(
            frame,
            text="EN",
            command=lambda: self.change_language("EN"),
            bg=bg,
            fg=RED if self.language == "EN" else normal,
            activebackground=bg,
            activeforeground=RED,
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=("Arial", 8, "bold"),
            cursor="hand2"
        ).pack(side="left")

        return frame

    # ========================================================
    # EDITORIAL ENTRY
    # ========================================================

    def editorial_entry(
        self,
        parent,
        label,
        password=False
    ):

        area = tk.Frame(
            parent,
            bg=WHITE
        )

        tk.Label(
            area,
            text=label,
            bg=WHITE,
            fg=GREY,
            font=self.font(8, "bold")
        ).pack(
            anchor="w"
        )

        entry = tk.Entry(
            area,
            bg=WHITE,
            fg=BLACK,
            insertbackground=BLACK,
            relief="flat",
            bd=0,
            highlightthickness=0,
            show="•" if password else "",
            font=self.font(13)
        )

        entry.pack(
            fill="x",
            pady=(9, 6)
        )

        tk.Frame(
            area,
            bg=BLACK,
            height=1
        ).pack(
            fill="x"
        )

        return area, entry

    # ========================================================
    # LOGIN
    # ========================================================

    def show_login(self):

        self.current_page = "login"
        self.clear()

        page = tk.Frame(
            self.container,
            bg=WHITE
        )
        page.pack(
            fill="both",
            expand=True
        )

        # ====================================================
        # LEFT / BLACK EDITORIAL AREA
        # ====================================================

        left = tk.Frame(
            page,
            bg=BLACK
        )

        left.place(
            relx=0,
            rely=0,
            relwidth=0.55,
            relheight=1
        )

        # BRAND

        tk.Label(
            left,
            text="FIND YOUR FIT®",
            bg=BLACK,
            fg=PURE_WHITE,
            font=("Arial", 17, "bold")
        ).place(
            x=45,
            y=38
        )

        tk.Label(
            left,
            text="DENIM / FORM / IDENTITY",
            bg=BLACK,
            fg="#777777",
            font=("Arial", 7, "bold")
        ).place(
            x=45,
            y=72
        )

        # INDEX

        tk.Label(
            left,
            text="01",
            bg=BLACK,
            fg=RED,
            font=("Arial", 10, "bold")
        ).place(
            relx=0.88,
            y=42
        )

        # BIG TYPOGRAPHY

        hero = (
            "อย่าตามหา\nแค่ SIZE.\n\nตามหา\nFIT ของคุณ."
            if self.language == "TH"
            else
            "DON'T\nFOLLOW\nTHE SIZE.\n\nFOLLOW\nTHE FORM."
        )

        tk.Label(
            left,
            text=hero,
            bg=BLACK,
            fg=PURE_WHITE,
            justify="left",
            font=self.font(
                39 if self.language == "TH" else 45,
                "bold"
            )
        ).place(
            x=45,
            rely=0.20
        )

        # RED GRAPHIC LINE

        tk.Frame(
            left,
            bg=RED,
            width=165,
            height=9
        ).place(
            x=45,
            rely=0.76
        )

        # SMALL TEXT

        tk.Label(
            left,
            text="SIZE IS A NUMBER.\nFIT IS PERSONAL.",
            bg=BLACK,
            fg="#A0A0A0",
            justify="left",
            font=("Arial", 9, "bold")
        ).place(
            x=45,
            rely=0.81
        )

        tk.Label(
            left,
            text="MMXXVI / FIND YOUR FIT",
            bg=BLACK,
            fg="#555555",
            font=("Arial", 7)
        ).place(
            x=45,
            rely=0.94
        )

        # ====================================================
        # ABSTRACT EDITORIAL GRAPHIC
        # ====================================================

        art = tk.Canvas(
            left,
            bg=BLACK,
            highlightthickness=0
        )

        art.place(
            relx=0.56,
            rely=0.16,
            relwidth=0.40,
            relheight=0.70
        )

        art.create_line(
            5, 30,
            300, 510,
            fill="#333333",
            width=1
        )

        art.create_line(
            290, 15,
            20, 530,
            fill="#333333",
            width=1
        )

        art.create_rectangle(
            70,
            115,
            245,
            365,
            outline=PURE_WHITE,
            width=1
        )

        art.create_rectangle(
            90,
            135,
            225,
            345,
            outline=RED,
            width=2
        )

        art.create_text(
            158,
            240,
            text="FIT",
            fill=PURE_WHITE,
            font=("Arial", 39, "bold")
        )

        art.create_text(
            158,
            285,
            text="/ 001",
            fill=RED,
            font=("Arial", 10, "bold")
        )

        # ====================================================
        # RIGHT / LOGIN
        # ====================================================

        right = tk.Frame(
            page,
            bg=WHITE
        )

        right.place(
            relx=0.55,
            rely=0,
            relwidth=0.45,
            relheight=1
        )

        switch = self.language_switch(
            right
        )

        switch.place(
            relx=0.82,
            y=38
        )

        # RIGHT INDEX

        tk.Label(
            right,
            text="ACCOUNT / ACCESS",
            bg=WHITE,
            fg=GREY,
            font=("Arial", 7, "bold")
        ).place(
            x=55,
            y=42
        )

        form = tk.Frame(
            right,
            bg=WHITE
        )

        form.place(
            relx=0.10,
            rely=0.18,
            relwidth=0.76
        )

        title = (
            "ยินดีต้อนรับ\nสู่ FIND YOUR FIT."
            if self.language == "TH"
            else
            "WELCOME TO\nFIND YOUR FIT."
        )

        tk.Label(
            form,
            text=title,
            bg=WHITE,
            fg=BLACK,
            justify="left",
            font=self.font(
                25,
                "bold"
            )
        ).pack(
            anchor="w"
        )

        subtitle = (
            "เข้าสู่ระบบเพื่อค้นหา FIT ที่เหมาะกับคุณ"
            if self.language == "TH"
            else
            "Enter the system. Discover your form."
        )

        tk.Label(
            form,
            text=subtitle,
            bg=WHITE,
            fg=GREY,
            font=self.font(9)
        ).pack(
            anchor="w",
            pady=(12, 38)
        )

        # EMAIL

        email_area, self.login_email = (
            self.editorial_entry(
                form,
                self.t("email")
            )
        )

        email_area.pack(
            fill="x"
        )

        # PASSWORD

        password_area, self.login_password = (
            self.editorial_entry(
                form,
                self.t("password"),
                True
            )
        )

        password_area.pack(
            fill="x",
            pady=(25, 0)
        )

        # SHOW PASSWORD

        self.show_password_var = (
            tk.BooleanVar()
        )

        tk.Checkbutton(
            form,
            text=self.t("show_password"),
            variable=self.show_password_var,
            command=self.toggle_login_password,
            bg=WHITE,
            fg=GREY,
            activebackground=WHITE,
            activeforeground=BLACK,
            selectcolor=WHITE,
            highlightthickness=0,
            bd=0,
            font=self.font(8)
        ).pack(
            anchor="w",
            pady=(12, 28)
        )

        # ENTER BUTTON

        tk.Button(
            form,
            text=(
                "ENTER  ↗"
                if self.language == "EN"
                else
                "เข้าสู่ระบบ  ↗"
            ),
            command=self.process_login,
            bg=BLACK,
            fg=PURE_WHITE,
            activebackground=RED,
            activeforeground=BLACK,
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=self.font(9, "bold"),
            pady=13,
            cursor="hand2"
        ).pack(
            fill="x"
        )

        # REGISTER

        register_row = tk.Frame(
            form,
            bg=WHITE
        )

        register_row.pack(
            fill="x",
            pady=(18, 0)
        )

        tk.Label(
            register_row,
            text=self.t("no_account"),
            bg=WHITE,
            fg=GREY,
            font=self.font(8)
        ).pack(
            side="left"
        )

        tk.Button(
            register_row,
            text=(
                self.t("create_account")
                + "  ↗"
            ),
            command=self.show_register,
            bg=WHITE,
            fg=BLACK,
            activebackground=WHITE,
            activeforeground=RED,
            relief="flat",
            bd=0,
            font=self.font(8, "bold"),
            cursor="hand2"
        ).pack(
            side="left",
            padx=7
        )

        # PERSONAL BRAND MESSAGE

        if self.language == "TH":
            personal_text = (
                "น้องพิซซ่าต้องการให้คุณได้ยีนส์ที่ดีที่สุด\n"
                "เพราะ FIT ที่ใช่ เริ่มจากการรู้จักตัวคุณ"
            )
        else:
            personal_text = (
                "Pizza wants you to find the best jeans for you.\n"
                "The right FIT starts with knowing you."
            )

        tk.Frame(
            form,
            bg=LIGHT_GREY,
            height=1
        ).pack(
            fill="x",
            pady=(42, 18)
        )

        tk.Label(
            form,
            text=personal_text,
            bg=WHITE,
            fg=GREY,
            justify="left",
            font=self.font(8)
        ).pack(
            anchor="w"
        )

        self.login_password.bind(
            "<Return>",
            lambda event: self.process_login()
        )

    # ========================================================
    # PASSWORD
    # ========================================================

    def toggle_login_password(self):

        self.login_password.config(
            show=""
            if self.show_password_var.get()
            else "•"
        )

    # ========================================================
    # PROCESS LOGIN
    # ========================================================

    def process_login(self):

        email = self.login_email.get().strip()
        password = self.login_password.get()

        if not email or not password:

            messagebox.showerror(
                "FIND YOUR FIT",
                self.t("fill_all")
            )
            return

        user = login_user(
            email,
            password
        )

        if not user:

            messagebox.showerror(
                "FIND YOUR FIT",
                self.t("login_failed")
            )
            return

        self.current_user = user

        update_user_language(
            user["id"],
            self.language
        )

        self.current_user[
            "language"
        ] = self.language

        if user["role"] == "admin":
            self.show_admin_home()

        else:
            self.show_home()

    # ========================================================
    # REGISTER
    # ========================================================

    def show_register(self):

        self.current_page = "register"
        self.clear()

        page = tk.Frame(
            self.container,
            bg=WHITE
        )

        page.pack(
            fill="both",
            expand=True
        )

        # LEFT

        left = tk.Frame(
            page,
            bg=RED
        )

        left.place(
            relx=0,
            rely=0,
            relwidth=0.45,
            relheight=1
        )

        tk.Label(
            left,
            text="FIND YOUR FIT®",
            bg=RED,
            fg=BLACK,
            font=("Arial", 17, "bold")
        ).place(
            x=45,
            y=38
        )

        tk.Label(
            left,
            text="02 / JOIN THE FORM",
            bg=RED,
            fg="#4A1009",
            font=("Arial", 8, "bold")
        ).place(
            x=45,
            y=80
        )

        register_hero = (
            "ค้นหา\nตัวตนของคุณ\nผ่าน FIT."
            if self.language == "TH"
            else
            "YOUR BODY.\nYOUR FORM.\nYOUR FIT."
        )

        tk.Label(
            left,
            text=register_hero,
            bg=RED,
            fg=BLACK,
            justify="left",
            font=self.font(
                39,
                "bold"
            )
        ).place(
            x=45,
            rely=0.30
        )

        tk.Label(
            left,
            text="NOT MADE FOR EVERYONE.\nMADE FOR YOU.",
            bg=RED,
            fg=BLACK,
            justify="left",
            font=("Arial", 9, "bold")
        ).place(
            x=45,
            rely=0.83
        )

        # RIGHT

        right = tk.Frame(
            page,
            bg=WHITE
        )

        right.place(
            relx=0.45,
            rely=0,
            relwidth=0.55,
            relheight=1
        )

        switch = self.language_switch(
            right
        )

        switch.place(
            relx=0.84,
            y=35
        )

        form = tk.Frame(
            right,
            bg=WHITE
        )

        form.place(
            relx=0.13,
            rely=0.08,
            relwidth=0.70
        )

        tk.Label(
            form,
            text=self.t("join_title"),
            bg=WHITE,
            fg=BLACK,
            font=self.font(24, "bold")
        ).pack(
            anchor="w"
        )

        tk.Label(
            form,
            text=self.t("join_subtitle"),
            bg=WHITE,
            fg=GREY,
            font=self.font(9)
        ).pack(
            anchor="w",
            pady=(7, 20)
        )

        self.register_entries = {}

        fields = [
            (
                "first_name",
                self.t("first_name"),
                False
            ),
            (
                "last_name",
                self.t("last_name"),
                False
            ),
            (
                "email",
                self.t("email"),
                False
            ),
            (
                "password",
                self.t("password"),
                True
            ),
            (
                "confirm_password",
                self.t("confirm_password"),
                True
            )
        ]

        for key, label, password in fields:

            area, entry = self.editorial_entry(
                form,
                label,
                password
            )

            area.pack(
                fill="x",
                pady=(0, 15)
            )

            self.register_entries[
                key
            ] = entry

        tk.Button(
            form,
            text=(
                self.t("register")
                + "  ↗"
            ),
            command=self.process_register,
            bg=BLACK,
            fg=PURE_WHITE,
            activebackground=RED,
            activeforeground=BLACK,
            relief="flat",
            font=self.font(9, "bold"),
            pady=12,
            cursor="hand2"
        ).pack(
            fill="x",
            pady=(5, 12)
        )

        bottom = tk.Frame(
            form,
            bg=WHITE
        )

        bottom.pack(
            anchor="w"
        )

        tk.Label(
            bottom,
            text=self.t("have_account"),
            bg=WHITE,
            fg=GREY,
            font=self.font(8)
        ).pack(
            side="left"
        )

        tk.Button(
            bottom,
            text=self.t("login") + "  ↗",
            command=self.show_login,
            bg=WHITE,
            fg=BLACK,
            relief="flat",
            font=self.font(8, "bold"),
            cursor="hand2"
        ).pack(
            side="left",
            padx=7
        )

    # ========================================================
    # PROCESS REGISTER
    # ========================================================

    def process_register(self):

        first_name = self.register_entries[
            "first_name"
        ].get().strip()

        last_name = self.register_entries[
            "last_name"
        ].get().strip()

        email = self.register_entries[
            "email"
        ].get().strip()

        password = self.register_entries[
            "password"
        ].get()

        confirm_password = self.register_entries[
            "confirm_password"
        ].get()

        if (
            not first_name
            or not last_name
            or not email
            or not password
            or not confirm_password
        ):

            messagebox.showerror(
                "FIND YOUR FIT",
                self.t("fill_all")
            )
            return

        if password != confirm_password:

            messagebox.showerror(
                "FIND YOUR FIT",
                self.t("password_not_match")
            )
            return

        if len(password) < 6:

            messagebox.showerror(
                "FIND YOUR FIT",
                (
                    "รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร"
                    if self.language == "TH"
                    else
                    "Password must contain at least 6 characters."
                )
            )
            return

        if "@" not in email:

            messagebox.showerror(
                "FIND YOUR FIT",
                (
                    "รูปแบบอีเมลไม่ถูกต้อง"
                    if self.language == "TH"
                    else
                    "Invalid email address."
                )
            )
            return

        user = register_user(
            first_name,
            last_name,
            email,
            password,
            self.language
        )

        if not user:

            messagebox.showerror(
                "FIND YOUR FIT",
                self.t("email_exists")
            )
            return

        self.current_user = user

        messagebox.showinfo(
            "FIND YOUR FIT",
            (
                "สร้างบัญชีเรียบร้อย"
                if self.language == "TH"
                else
                "Account created successfully."
            )
        )

        self.show_home()

    # ========================================================
    # CUSTOMER NAVIGATION
    # ========================================================

    def customer_header(self):

        header = tk.Frame(
            self.container,
            bg=WHITE,
            height=76
        )

        header.pack(
            fill="x"
        )

        header.pack_propagate(False)

        # BRAND

        tk.Button(
            header,
            text="FIND YOUR FIT®",
            command=self.show_home,
            bg=WHITE,
            fg=BLACK,
            activebackground=WHITE,
            activeforeground=RED,
            relief="flat",
            bd=0,
            font=("Arial", 15, "bold"),
            cursor="hand2"
        ).pack(
            side="left",
            padx=(32, 22)
        )

        # COLLECTION INDEX

        tk.Label(
            header,
            text="DENIM / MMXXVI",
            bg=WHITE,
            fg="#999999",
            font=("Arial", 7, "bold")
        ).pack(
            side="left"
        )

        right = tk.Frame(
            header,
            bg=WHITE
        )

        right.pack(
            side="right",
            padx=25
        )

        navigation = [
            (
                self.t("shop"),
                self.show_shop_preview
            ),
            (
                self.t("find_fit"),
                self.show_fit_preview
            ),
            (
                (
                    "BAG"
                    if self.language == "EN"
                    else "ตะกร้า"
                )
                + f" [{len(self.cart)}]",
                self.show_bag_preview
            )
        ]

        for text, command in navigation:

            tk.Button(
                right,
                text=text,
                command=command,
                bg=WHITE,
                fg=BLACK,
                activebackground=WHITE,
                activeforeground=RED,
                relief="flat",
                bd=0,
                font=self.font(8, "bold"),
                cursor="hand2",
                padx=8
            ).pack(
                side="left"
            )

        switch = self.language_switch(
            right
        )

        switch.pack(
            side="left",
            padx=10
        )

        tk.Button(
            right,
            text="×",
            command=self.logout,
            bg=WHITE,
            fg=BLACK,
            activebackground=WHITE,
            activeforeground=RED,
            relief="flat",
            bd=0,
            font=("Arial", 16),
            cursor="hand2"
        ).pack(
            side="left",
            padx=(7, 0)
        )

        tk.Frame(
            self.container,
            bg=BLACK,
            height=1
        ).pack(
            fill="x"
        )

    # ========================================================
    # HOME
    # ========================================================

    def show_home(self):

        self.current_page = "home"

        self.clear()
        self.customer_header()

        body = tk.Frame(
            self.container,
            bg=WHITE
        )

        body.pack(
            fill="both",
            expand=True
        )

        # ====================================================
        # HERO LEFT
        # ====================================================

        left = tk.Frame(
            body,
            bg=WHITE
        )

        left.place(
            relx=0,
            rely=0,
            relwidth=0.58,
            relheight=1
        )

        tk.Label(
            left,
            text="01 / DENIM SYSTEM",
            bg=WHITE,
            fg=BLACK,
            font=("Arial", 8, "bold")
        ).place(
            x=42,
            y=35
        )

        hero = (
            "อย่าหาแค่ SIZE\nค้นหา FIT ของคุณ"
            if self.language == "TH"
            else
            "DON'T FIND\nA SIZE.\nFIND YOUR FIT."
        )

        tk.Label(
            left,
            text=hero,
            bg=WHITE,
            fg=BLACK,
            justify="left",
            font=self.font(
                43 if self.language == "TH" else 51,
                "bold"
            )
        ).place(
            x=42,
            rely=0.16
        )

        # RED MARK

        tk.Frame(
            left,
            bg=RED,
            width=90,
            height=9
        ).place(
            x=45,
            rely=0.53
        )

        description = (
            "ร่างกายของคุณไม่ได้ถูกสร้างขึ้นตามตาราง SIZE\n"
            "เราจึงช่วยค้นหา FIT ที่เข้ากับคุณจริง ๆ"
            if self.language == "TH"
            else
            "YOUR BODY WAS NEVER MADE FOR A SIZE CHART.\n"
            "FIND THE FORM THAT WORKS WITH YOU."
        )

        tk.Label(
            left,
            text=description,
            bg=WHITE,
            fg=GREY,
            justify="left",
            font=self.font(10)
        ).place(
            x=45,
            rely=0.59
        )

        # BUTTONS

        tk.Button(
            left,
            text=(
                "ค้นหา FIT ของฉัน  ↗"
                if self.language == "TH"
                else
                "FIND MY FIT  ↗"
            ),
            command=self.show_fit_preview,
            bg=BLACK,
            fg=PURE_WHITE,
            activebackground=RED,
            activeforeground=BLACK,
            relief="flat",
            font=self.font(9, "bold"),
            padx=25,
            pady=13,
            cursor="hand2"
        ).place(
            x=45,
            rely=0.72
        )

        tk.Button(
            left,
            text=(
                "ดูคอลเลกชัน  →"
                if self.language == "TH"
                else
                "SHOP THE COLLECTION  →"
            ),
            command=self.show_shop_preview,
            bg=WHITE,
            fg=BLACK,
            activebackground=WHITE,
            activeforeground=RED,
            relief="flat",
            bd=0,
            font=self.font(9, "bold"),
            cursor="hand2"
        ).place(
            x=250,
            rely=0.735
        )

        # USER

        user_name = (
            self.current_user["first_name"]
            if self.current_user
            else ""
        )

        tk.Label(
            left,
            text=f"MEMBER / {user_name.upper()}",
            bg=WHITE,
            fg="#999999",
            font=("Arial", 7, "bold")
        ).place(
            x=45,
            rely=0.91
        )

        # ====================================================
        # RIGHT / FUTURE IMAGE SPACE
        # ====================================================

        right = tk.Frame(
            body,
            bg=BLACK
        )

        right.place(
            relx=0.58,
            rely=0,
            relwidth=0.42,
            relheight=1
        )

        tk.Label(
            right,
            text="FORM / 001",
            bg=BLACK,
            fg=PURE_WHITE,
            font=("Arial", 8, "bold")
        ).place(
            x=25,
            y=25
        )

        tk.Label(
            right,
            text="IMAGE\nCOMING\nLATER.",
            bg=BLACK,
            fg="#222222",
            justify="left",
            font=("Arial", 43, "bold")
        ).place(
            x=30,
            rely=0.30
        )

        # Abstract placeholder — จะเปลี่ยนเป็นรูปยีนส์ภายหลัง

        canvas = tk.Canvas(
            right,
            bg=BLACK,
            highlightthickness=0
        )

        canvas.place(
            relx=0.54,
            rely=0.12,
            relwidth=0.40,
            relheight=0.72
        )

        canvas.create_line(
            0, 0,
            230, 500,
            fill="#333333"
        )

        canvas.create_line(
            230, 0,
            0, 500,
            fill="#333333"
        )

        canvas.create_rectangle(
            30,
            90,
            190,
            390,
            outline=PURE_WHITE,
            width=1
        )

        canvas.create_text(
            110,
            240,
            text="DENIM",
            fill=PURE_WHITE,
            font=("Arial", 18, "bold"),
            angle=90
        )

        tk.Label(
            right,
            text="001 / NEW FORM",
            bg=RED,
            fg=BLACK,
            font=("Arial", 8, "bold"),
            padx=12,
            pady=7
        ).place(
            x=25,
            rely=0.88
        )

    # ========================================================
    # SHOP PREVIEW
    # ========================================================

    def show_shop_preview(self):

        self.current_page = "home"

        messagebox.showinfo(
            "02 / COLLECTION",
            (
                "ต่อไปเราจะสร้างหน้า SHOP แบบ Fashion Catalogue\n"
                "และเชื่อมสินค้า 6 รุ่นจาก Database"
                if self.language == "TH"
                else
                "Next: Fashion Catalogue connected to the 6 products."
            )
        )

    # ========================================================
    # FIT PREVIEW
    # ========================================================

    def show_fit_preview(self):

        self.current_page = "home"

        messagebox.showinfo(
            "03 / YOUR FORM",
            (
                "ต่อไปเราจะสร้าง FIND MY FIT\n"
                "ให้เป็น Interactive Fitting Experience"
                if self.language == "TH"
                else
                "Next: FIND MY FIT interactive fitting experience."
            )
        )

    # ========================================================
    # BAG PREVIEW
    # ========================================================

    def show_bag_preview(self):

        messagebox.showinfo(
            "BAG",
            (
                "ระบบ BAG จะเชื่อมกับสินค้าจากหน้า SHOP"
                if self.language == "TH"
                else
                "BAG will connect to the collection."
            )
        )

    # ========================================================
    # ADMIN
    # ========================================================

    def show_admin_home(self):

        self.current_page = "admin"
        self.clear()

        header = tk.Frame(
            self.container,
            bg=BLACK,
            height=75
        )

        header.pack(
            fill="x"
        )

        header.pack_propagate(False)

        tk.Label(
            header,
            text="FIND YOUR FIT® / CONTROL",
            bg=BLACK,
            fg=PURE_WHITE,
            font=("Arial", 15, "bold")
        ).pack(
            side="left",
            padx=30
        )

        right = tk.Frame(
            header,
            bg=BLACK
        )

        right.pack(
            side="right",
            padx=25
        )

        switch = self.language_switch(
            right,
            dark=True
        )

        switch.pack(
            side="left",
            padx=15
        )

        tk.Button(
            right,
            text="×",
            command=self.logout,
            bg=BLACK,
            fg=PURE_WHITE,
            activebackground=BLACK,
            activeforeground=RED,
            relief="flat",
            bd=0,
            font=("Arial", 17),
            cursor="hand2"
        ).pack(
            side="left"
        )

        body = tk.Frame(
            self.container,
            bg=WHITE
        )

        body.pack(
            fill="both",
            expand=True
        )

        tk.Label(
            body,
            text="00 / CONTROL SYSTEM",
            bg=WHITE,
            fg=BLACK,
            font=("Arial", 8, "bold")
        ).place(
            x=45,
            y=40
        )

        title = (
            "จัดการ\nระบบของคุณ."
            if self.language == "TH"
            else
            "CONTROL\nTHE SYSTEM."
        )

        tk.Label(
            body,
            text=title,
            bg=WHITE,
            fg=BLACK,
            justify="left",
            font=self.font(
                43,
                "bold"
            )
        ).place(
            x=45,
            y=100
        )

        tk.Frame(
            body,
            bg=RED,
            width=110,
            height=9
        ).place(
            x=48,
            y=260
        )

        description = (
            "ORDER / PAYMENT / STOCK\n"
            "ระบบจัดการร้านจะถูกเชื่อมในขั้นต่อไป"
            if self.language == "TH"
            else
            "ORDER / PAYMENT / STOCK\n"
            "Commerce controls will be connected next."
        )

        tk.Label(
            body,
            text=description,
            bg=WHITE,
            fg=GREY,
            justify="left",
            font=self.font(10)
        ).place(
            x=45,
            y=300
        )

        # BLACK ART BLOCK

        art = tk.Frame(
            body,
            bg=BLACK
        )

        art.place(
            relx=0.62,
            rely=0.08,
            relwidth=0.31,
            relheight=0.78
        )

        tk.Label(
            art,
            text="ADMIN\n/ 001",
            bg=BLACK,
            fg=PURE_WHITE,
            justify="left",
            font=("Arial", 31, "bold")
        ).place(
            x=30,
            y=35
        )

        tk.Label(
            art,
            text="SYSTEM\nONLINE",
            bg=BLACK,
            fg=RED,
            justify="left",
            font=("Arial", 12, "bold")
        ).place(
            x=30,
            rely=0.78
        )

    # ========================================================
    # LOGOUT
    # ========================================================

    def logout(self):

        self.current_user = None
        self.cart = []

        self.show_login()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    create_database()

    app = FindYourFitApp()

    app.mainloop()