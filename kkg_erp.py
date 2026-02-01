# =========================================================
# 🚜 KKG ENTERPRISE OS — PHASE 1 INDUSTRIAL CORE (SINGLE FILE)
# =========================================================

import streamlit as st
import sqlite3
import pandas as pd
import datetime
import hashlib
import uuid
import traceback
from typing import Dict, List, Tuple

# =========================================================
# CONFIG
# =========================================================

st.set_page_config(page_title="KKG Enterprise OS", layout="wide")

DB_FILE = "kkg_enterprise.db"

META = {
    "brand": "Kisan Khidmat Ghar",
    "location": "Chakoora Pulwama",
    "currency": "₹"
}

# =========================================================
# INDUSTRIAL DATABASE ENGINE
# =========================================================

class EnterpriseDB:

    def __init__(self):
        self.conn = self._connect()

    def _connect(self):
        return sqlite3.connect(DB_FILE, check_same_thread=False)

    def run(self, query, params=(), fetch=False):
        try:
            cur = self.conn.cursor()
            cur.execute(query, params)

            if fetch:
                cols = [c[0] for c in cur.description]
                res = [dict(zip(cols, r)) for r in cur.fetchall()]
                cur.close()
                return res
            else:
                self.conn.commit()
                cur.close()
                return True

        except Exception as e:
            print("DB ERROR:", e)
            print(traceback.format_exc())
            return [] if fetch else False

db = EnterpriseDB()

# =========================================================
# SCHEMA INIT
# =========================================================

def init_schema():

    db.run("""
    CREATE TABLE IF NOT EXISTS users(
        username TEXT PRIMARY KEY,
        password TEXT,
        role TEXT
    )
    """)

    db.run("""
    CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price REAL,
        cost REAL,
        stock INTEGER,
        min_stock INTEGER
    )
    """)

    db.run("""
    CREATE TABLE IF NOT EXISTS customers(
        phone TEXT PRIMARY KEY,
        name TEXT,
        credit_limit REAL,
        joined TEXT
    )
    """)

    db.run("""
    CREATE TABLE IF NOT EXISTS transactions(
        id TEXT PRIMARY KEY,
        phone TEXT,
        total REAL,
        paid REAL,
        due REAL,
        type TEXT,
        created TEXT
    )
    """)

    db.run("""
    CREATE TABLE IF NOT EXISTS tx_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tx_id TEXT,
        product TEXT,
        qty INTEGER,
        price REAL,
        cost REAL
    )
    """)

    db.run("""
    CREATE TABLE IF NOT EXISTS expenses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount REAL,
        category TEXT,
        created TEXT
    )
    """)

    db.run("""
    CREATE TABLE IF NOT EXISTS audit(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        action TEXT,
        details TEXT,
        created TEXT
    )
    """)

init_schema()

# =========================================================
# SECURITY + AUDIT
# =========================================================

def hash_pass(p):
    return hashlib.sha256(p.encode()).hexdigest()

def audit(action, details):
    user = st.session_state.get("user","system")
    db.run(
        "INSERT INTO audit VALUES(NULL,?,?,?,?)",
        (user, action, details, str(datetime.datetime.now()))
    )

# =========================================================
# FINANCE ENGINE (REAL PROFIT LOGIC)
# =========================================================

class FinanceEngine:

    @staticmethod
    def today_profit():

        today = str(datetime.date.today())

        sales = db.run(
            "SELECT SUM(total) v FROM transactions WHERE type='SALE' AND created LIKE ?",
            (today+"%",), True
        )

        exp = db.run(
            "SELECT SUM(amount) v FROM expenses WHERE created LIKE ?",
            (today+"%",), True
        )

        sales = sales[0]['v'] if sales and sales[0]['v'] else 0
        exp = exp[0]['v'] if exp and exp[0]['v'] else 0

        return sales-exp

    @staticmethod
    def real_profit():

        items = db.run("SELECT qty, price, cost FROM tx_items", fetch=True)

        profit = 0
        for i in items:
            profit += (i['price'] - i['cost']) * i['qty']

        exp = db.run("SELECT SUM(amount) v FROM expenses", fetch=True)
        exp = exp[0]['v'] if exp and exp[0]['v'] else 0

        return profit - exp

# =========================================================
# AUTH
# =========================================================

def login_ui():

    st.title("🔐 KKG Enterprise Login")

    u = st.text_input("User")
    p = st.text_input("Password", type="password")

    if st.button("Login"):

        res = db.run("SELECT * FROM users WHERE username=?", (u,), True)

        if res and res[0]['password'] == hash_pass(p):
            st.session_state.user = u
            st.session_state.role = res[0]['role']
            audit("LOGIN", u)
            st.rerun()
        else:
            st.error("Invalid login")

# =========================================================
# DASHBOARD
# =========================================================

def dashboard():

    st.title("🚀 Business Command Center")

    profit_today = FinanceEngine.today_profit()
    profit_real = FinanceEngine.real_profit()

    c1,c2 = st.columns(2)

    c1.metric("Today Profit", f"₹{profit_today:,.0f}")
    c2.metric("Real Net Profit", f"₹{profit_real:,.0f}")

# =========================================================
# INVENTORY
# =========================================================

def inventory_ui():

    st.header("📦 Inventory")

    with st.form("add_prod"):
        n = st.text_input("Name")
        p = st.number_input("Price")
        c = st.number_input("Cost")
        s = st.number_input("Stock", step=1)
        if st.form_submit_button("Add"):
            db.run(
                "INSERT INTO products VALUES(NULL,?,?,?,?,?)",
                (n,p,c,s,5)
            )
            audit("ADD_PRODUCT", n)
            st.success("Added")

    prods = db.run("SELECT * FROM products", fetch=True)
    if prods:
        st.dataframe(pd.DataFrame(prods))

# =========================================================
# CUSTOMERS
# =========================================================

def customers_ui():

    st.header("👥 Customers")

    with st.form("add_cust"):
        name = st.text_input("Name")
        ph = st.text_input("Phone")
        lim = st.number_input("Credit Limit", 50000)
        if st.form_submit_button("Add"):
            db.run(
                "INSERT INTO customers VALUES(?,?,?,?)",
                (ph,name,lim,str(datetime.date.today()))
            )
            audit("ADD_CUSTOMER", ph)

    data = db.run("SELECT * FROM customers", fetch=True)
    if data:
        st.dataframe(pd.DataFrame(data))

# =========================================================
# POS ENGINE
# =========================================================

def pos_ui():

    st.header("🛒 POS Terminal")

    prods = db.run("SELECT * FROM products", True)
    custs = db.run("SELECT * FROM customers", True)

    if not prods or not custs:
        st.warning("Need products + customers")
        return

    pmap = {p['name']:p for p in prods}
    cmap = {c['name']:c for c in custs}

    cust = st.selectbox("Customer", list(cmap.keys()))
    prod = st.selectbox("Product", list(pmap.keys()))
    qty = st.number_input("Qty", 1)

    if st.button("Add Item"):

        if "cart" not in st.session_state:
            st.session_state.cart = []

        item = pmap[prod]

        st.session_state.cart.append({
            "name": prod,
            "qty": qty,
            "price": item['price'],
            "cost": item['cost']
        })

    if "cart" in st.session_state and st.session_state.cart:

        df = pd.DataFrame(st.session_state.cart)
        st.dataframe(df)

        total = (df.qty * df.price).sum()

        paid = st.number_input("Paid", 0.0)

        if st.button("Finalize Sale"):

            txid = str(uuid.uuid4())

            db.run(
                "INSERT INTO transactions VALUES(?,?,?,?,?,?,?)",
                (
                    txid,
                    cmap[cust]['phone'],
                    total,
                    paid,
                    total-paid,
                    "SALE",
                    str(datetime.datetime.now())
                )
            )

            for i in st.session_state.cart:
                db.run(
                    "INSERT INTO tx_items VALUES(NULL,?,?,?,?,?)",
                    (txid,i['name'],i['qty'],i['price'],i['cost'])
                )

                db.run(
                    "UPDATE products SET stock=stock-? WHERE name=?",
                    (i['qty'],i['name'])
                )

            audit("SALE", txid)

            st.session_state.cart = []
            st.success("Sale Done")
            st.rerun()

# =========================================================
# EXPENSES
# =========================================================

def expense_ui():

    st.header("💸 Expenses")

    with st.form("exp"):
        cat = st.text_input("Category")
        amt = st.number_input("Amount")
        if st.form_submit_button("Add"):
            db.run(
                "INSERT INTO expenses VALUES(NULL,?,?,?)",
                (amt,cat,str(datetime.datetime.now()))
            )
            audit("ADD_EXP", cat)

    data = db.run("SELECT * FROM expenses", True)
    if data:
        st.dataframe(pd.DataFrame(data))

# =========================================================
# MAIN ROUTER
# =========================================================

def main():

    if "user" not in st.session_state:
        login_ui()
        return

    st.sidebar.title("KKG Enterprise")

    menu = st.sidebar.radio(
        "Menu",
        ["Dashboard","POS","Inventory","Customers","Expenses"]
    )

    if menu=="Dashboard":
        dashboard()

    if menu=="POS":
        pos_ui()

    if menu=="Inventory":
        inventory_ui()

    if menu=="Customers":
        customers_ui()

    if menu=="Expenses":
        expense_ui()

# =========================================================

if __name__ == "__main__":
    main()
