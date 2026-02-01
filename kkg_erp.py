import streamlit as st
import pandas as pd
import datetime
import time
from fpdf import FPDF
import sqlite3
import os
import hashlib

# ==========================================
# 1. CONFIGURATION & SECURITY
# ==========================================
st.set_page_config(page_title="KKG ERP", page_icon="🚜", layout="wide")

BUSINESS_INFO = {
    "name": "KISAN KHIDMAT GHAR",
    "address": "Chakoora, Pulwama, J&K",
    "phone": "+91 9622749245",
    "gst": "01AAAAA0000A1Z5" # Placeholder
}

# Simple Hardcoded Credentials (In Phase 3, this moves to DB)
USERS = {
    "admin": "kkg@123",  # Owner (Full Access)
    "staff": "staff1"    # Staff (POS only, no Deletes/Profits)
}

# ==========================================
# 2. DATABASE ENGINE (Self-Healing + Multi-Table)
# ==========================================
@st.cache_resource
def get_db_connection():
    # Cloud Mode
    if hasattr(st, "secrets") and "postgres" in st.secrets:
        import psycopg2
        try:
            return "POSTGRES", psycopg2.connect(st.secrets["postgres"]["url"])
        except: return None, None
    # Local Mode
    return "SQLITE", sqlite3.connect("kkg_database.sqlite", check_same_thread=False)

def run_query(query, params=None, fetch=False):
    db_type, conn = get_db_connection()
    if not conn: return [] if fetch else False

    if db_type == "POSTGRES":
        query = query.replace('?', '%s')
        if conn.closed: st.cache_resource.clear(); db_type, conn = get_db_connection()

    try:
        cur = conn.cursor()
        if db_type == "SQLITE": conn.row_factory = sqlite3.Row
        cur.execute(query, params or ())
        
        if fetch:
            cols = [desc[0] for desc in cur.description]
            res = [dict(zip(cols, row)) for row in cur.fetchall()]
            cur.close(); return res
        else:
            conn.commit(); cur.close(); return True
    except Exception as e:
        if db_type == "POSTGRES": conn.rollback()
        st.error(f"System Error: {e}")
        return [] if fetch else False

# Audit Logger
def log_audit(action, details):
    user = st.session_state.get('username', 'system')
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_query("INSERT INTO audit_logs (timestamp, user, action, details) VALUES (?,?,?,?)", (ts, user, action, details))

# Schema Initialization
def init_system():
    db_type, _ = get_db_connection()
    if not db_type: return
    pk = "SERIAL PRIMARY KEY" if db_type == "POSTGRES" else "INTEGER PRIMARY KEY AUTOINCREMENT"
    
    tables = [
        f"CREATE TABLE IF NOT EXISTS products (id {pk}, name TEXT, category TEXT, price REAL, cost_price REAL, stock INTEGER, supplier TEXT)",
        f"CREATE TABLE IF NOT EXISTS customers (phone TEXT PRIMARY KEY, name TEXT, address TEXT, joined_date TEXT, credit_limit REAL DEFAULT 50000)",
        f"CREATE TABLE IF NOT EXISTS suppliers (id {pk}, name TEXT, phone TEXT, address TEXT)",
        f"CREATE TABLE IF NOT EXISTS transactions (invoice_id TEXT PRIMARY KEY, customer_phone TEXT, date TEXT, type TEXT, total_amount REAL, paid_amount REAL, due_amount REAL, payment_mode TEXT, notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        f"CREATE TABLE IF NOT EXISTS invoice_items (id {pk}, invoice_id TEXT, product_name TEXT, quantity INTEGER, unit_price REAL, total_price REAL)",
        f"CREATE TABLE IF NOT EXISTS expenses (id {pk}, date TEXT, category TEXT, amount REAL, note TEXT, added_by TEXT)",
        f"CREATE TABLE IF NOT EXISTS audit_logs (id {pk}, timestamp TEXT, user TEXT, action TEXT, details TEXT)"
    ]
    for q in tables: run_query(q)

init_system()

# ==========================================
# 3. ADVANCED LOGIC & CACHING
# ==========================================
@st.cache_data(ttl=60)
def get_financial_health():
    today = datetime.date.today().isoformat()
    # Revenue
    sales = run_query(f"SELECT SUM(total_amount) as v FROM transactions WHERE date='{today}' AND type='SALE'", fetch=True)
    sales_val = sales[0]['v'] or 0
    
    # Expenses
    exps = run_query(f"SELECT SUM(amount) as v FROM expenses WHERE date='{today}'", fetch=True)
    exp_val = exps[0]['v'] or 0
    
    # Receivables (Market Debt)
    totals = run_query("SELECT SUM(total_amount) as s, SUM(paid_amount) as p FROM transactions", fetch=True)
    debt = (totals[0]['s'] or 0) - (totals[0]['p'] or 0)
    
    return sales_val, exp_val, debt

def refresh_all():
    st.cache_data.clear()
    st.rerun()

# ==========================================
# 4. PROFESSIONAL PDF
# ==========================================
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 18)
        self.cell(0, 10, BUSINESS_INFO["name"], 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.cell(0, 5, BUSINESS_INFO["address"], 0, 1, 'C')
        self.cell(0, 5, f"Helpline: {BUSINESS_INFO['phone']}", 0, 1, 'C')
        self.ln(10); self.line(10, 30, 200, 30)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, 'Computer Generated Invoice - Valid without Signature', 0, 0, 'C')

def generate_pdf(tx, items, cust):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    title = "SALES INVOICE" if tx['type'] == 'SALE' else "RETURN RECEIPT"
    pdf.cell(0, 10, title, 0, 1, 'C')
    
    pdf.set_font('Arial', '', 10)
    pdf.cell(100, 5, f"Customer: {cust['name']}", 0, 0)
    pdf.cell(90, 5, f"Bill No: {tx['invoice_id']}", 0, 1, 'R')
    pdf.cell(100, 5, f"Phone: {cust['phone']}", 0, 0)
    pdf.cell(90, 5, f"Date: {tx['date']}", 0, 1, 'R')
    pdf.ln(5)
    
    # Table
    pdf.set_fill_color(220, 220, 220); pdf.set_font('Arial', 'B', 10)
    pdf.cell(90, 8, 'Product', 1, 0, 'L', 1); pdf.cell(30, 8, 'Price', 1, 0, 'R', 1)
    pdf.cell(20, 8, 'Qty', 1, 0, 'C', 1); pdf.cell(50, 8, 'Total', 1, 1, 'R', 1)
    
    pdf.set_font('Arial', '', 10)
    for i in items:
        name = i.get('product_name') or i.get('name')
        pdf.cell(90, 8, str(name)[:40], 1, 0, 'L')
        pdf.cell(30, 8, f"{float(i.get('unit_price', i.get('price', 0))):.0f}", 1, 0, 'R')
        pdf.cell(20, 8, str(i.get('quantity', i.get('qty', 0))), 1, 0, 'C')
        pdf.cell(50, 8, f"{float(i.get('total_price', i.get('total', 0))):.0f}", 1, 1, 'R')
    
    pdf.ln(5); pdf.set_font('Arial', 'B', 12)
    pdf.cell(140, 10, 'Net Payable', 0, 0, 'R'); pdf.cell(50, 10, f"Rs {tx['total_amount']:,.0f}", 1, 1, 'R')
    
    # Payment Info
    pdf.set_font('Arial', '', 10)
    pdf.cell(140, 6, 'Paid Amount', 0, 0, 'R'); pdf.cell(50, 6, f"{float(tx.get('paid_amount',0)):,.0f}", 1, 1, 'R')
    
    due = float(tx.get('due_amount', 0))
    if due > 0: pdf.set_text_color(200, 0, 0)
    pdf.cell(140, 6, 'Balance Pending', 0, 0, 'R'); pdf.cell(50, 6, f"{due:,.0f}", 1, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 5. UI & AUTHENTICATION
# ==========================================
st.markdown("""
    <style>
    .stApp { background-color: #f1f5f9; font-family: 'Segoe UI', sans-serif; }
    [data-testid="stSidebar"] { background-color: #0f172a; border-right: 1px solid #334155; }
    [data-testid="stSidebar"] * { color: #f8fafc !important; }
    
    div[data-testid="stMetric"] { background: white; padding: 20px; border-radius: 10px; border-left: 5px solid #2563eb; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .stButton button { background-color: #2563eb; color: white; border-radius: 6px; font-weight: 600; border:none; width: 100%; }
    .stButton button:hover { background-color: #1d4ed8; }
    
    /* Login Page */
    .login-box { max-width: 400px; margin: auto; padding: 40px; background: white; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
    </style>
""", unsafe_allow_html=True)

def login_screen():
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.markdown("<h2 style='text-align: center;'>🔐 KKG ERP Login</h2>", unsafe_allow_html=True)
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Secure Login"):
                if u in USERS and USERS[u] == p:
                    st.session_state.logged_in = True
                    st.session_state.username = u
                    st.session_state.role = "admin" if u == "admin" else "staff"
                    log_audit("LOGIN", "User logged in")
                    st.rerun()
                else:
                    st.error("Invalid Access Credentials")

def main():
    if 'logged_in' not in st.session_state:
        login_screen()
        return

    # SIDEBAR
    st.sidebar.markdown(f"""
        <div style='text-align:center; padding:15px 0;'>
            <h1>🌾 KKG</h1>
            <p>Logged in as: <b>{st.session_state.username.upper()}</b></p>
        </div>
    """, unsafe_allow_html=True)
    
    opts = ["Dashboard", "POS (Billing)", "Customers", "Inventory", "Expenses", "Suppliers", "Reports", "Logout"]
    if st.session_state.role == "staff":
        opts = ["Dashboard", "POS (Billing)", "Customers", "Inventory", "Logout"]
        
    menu = st.sidebar.radio("Menu", opts)

    if menu == "Logout":
        st.session_state.clear()
        st.rerun()

    # --- DASHBOARD ---
    if menu == "Dashboard":
        st.title("🚀 Executive Dashboard")
        sales, exps, debt = get_financial_health()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Today's Revenue", f"₹{sales:,.0f}")
        if st.session_state.role == "admin":
            c2.metric("Today's Expenses", f"₹{exps:,.0f}", delta=f"Net: ₹{sales-exps:,.0f}")
        c3.metric("Market Debt", f"₹{debt:,.0f}", delta_color="inverse")
        
        if st.button("🔄 System Refresh"): refresh_all()

    # --- POS (RETURNS ADDED) ---
    elif menu == "POS (Billing)":
        st.title("🛒 Terminal")
        
        mode = st.radio("Transaction Type", ["SALE", "RETURN"], horizontal=True)
        
        c1, c2 = st.columns([1.5, 1])
        with c1:
            # Cached Data
            custs = run_query("SELECT * FROM customers", fetch=True)
            prods = run_query("SELECT * FROM products", fetch=True)
            
            if not custs or not prods: st.warning("Setup Data First"); st.stop()
            
            c_map = {f"{c['name']} | {c['phone']}": c for c in custs}
            p_map = {f"{p['name']} (₹{p['price']})": p for p in prods}
            
            sel_c = st.selectbox("Customer", list(c_map.keys()))
            sel_p = st.selectbox("Product", list(p_map.keys()))
            
            col_q, col_b = st.columns([1, 1])
            qty = col_q.number_input("Qty", 1)
            
            if 'cart' not in st.session_state: st.session_state.cart = []
            
            if col_b.button("Add"):
                prod = p_map[sel_p]
                if mode == "SALE" and qty > prod['stock']:
                    st.error(f"Stock Low! Only {prod['stock']} left.")
                else:
                    st.session_state.cart.append({**prod, 'qty': qty, 'total': qty * prod['price']})

        with c2:
            st.subheader("Cart")
            if st.session_state.cart:
                df = pd.DataFrame(st.session_state.cart)
                st.dataframe(df[['name', 'qty', 'total']], hide_index=True)
                
                total = df['total'].sum()
                st.markdown(f"### Total: ₹{total:,.0f}")
                
                paid = st.number_input("Paid / Refunded", 0.0)
                pay_mode = st.selectbox("Payment Mode", ["Cash", "UPI", "Credit"])
                
                if st.button("✅ FINALIZE"):
                    cust = c_map[sel_c]
                    inv_id = f"{'RET' if mode=='RETURN' else 'INV'}-{int(time.time())}"
                    
                    # Logic: Returns reduce sale totals (negative)
                    final_total = -total if mode == "RETURN" else total
                    final_paid = -paid if mode == "RETURN" else paid
                    due = final_total - final_paid
                    
                    run_query("INSERT INTO transactions (invoice_id, customer_phone, date, type, total_amount, paid_amount, due_amount, payment_mode) VALUES (?,?,?,?,?,?,?,?)",
                              (inv_id, cust['phone'], str(datetime.date.today()), mode, final_total, final_paid, due, pay_mode))
                    
                    for item in st.session_state.cart:
                        run_query("INSERT INTO invoice_items (invoice_id, product_name, quantity, unit_price, total_price) VALUES (?,?,?,?,?)",
                                  (inv_id, item['name'], item['qty'], item['price'], item['total']))
                        
                        # Stock Logic: Sale removes, Return adds
                        op = "+" if mode == "RETURN" else "-"
                        run_query(f"UPDATE products SET stock = stock {op} ? WHERE id = ?", (item['qty'], item['id']))
                    
                    log_audit("POS_TX", f"Created {inv_id} for {cust['name']}")
                    st.session_state.pdf = generate_pdf({'invoice_id': inv_id, 'date': str(datetime.date.today()), 'total_amount': total, 'paid_amount': paid, 'due_amount': due, 'type': mode}, st.session_state.cart, cust)
                    st.session_state.cart = []
                    refresh_all()
            
            if 'pdf' in st.session_state:
                st.download_button("Download Receipt", st.session_state.pdf, "receipt.pdf", "application/pdf")

    # --- EXPENSES (CEO Only) ---
    elif menu == "Expenses":
        st.title("💸 Expense Manager")
        with st.form("add_exp"):
            c1, c2 = st.columns(2)
            cat = c1.selectbox("Category", ["Rent", "Salary", "Tea/Refreshment", "Transportation", "Electricity", "Other"])
            amt = c2.number_input("Amount", 1.0)
            note = st.text_input("Description")
            if st.form_submit_button("Record Expense"):
                run_query("INSERT INTO expenses (date, category, amount, note, added_by) VALUES (?,?,?,?,?)", 
                          (str(datetime.date.today()), cat, amt, note, st.session_state.username))
                st.success("Recorded")
                refresh_all()
        
        exps = run_query("SELECT * FROM expenses ORDER BY date DESC", fetch=True)
        if exps: st.dataframe(pd.DataFrame(exps))

    # --- SUPPLIERS ---
    elif menu == "Suppliers":
        st.title("🚚 Supplier Database")
        with st.expander("Add Supplier"):
            with st.form("sup"):
                n = st.text_input("Company Name")
                p = st.text_input("Phone")
                a = st.text_input("Address")
                if st.form_submit_button("Save"):
                    run_query("INSERT INTO suppliers (name, phone, address) VALUES (?,?,?)", (n,p,a))
                    st.success("Added")
                    st.rerun()
        
        sups = run_query("SELECT * FROM suppliers", fetch=True)
        if sups: st.dataframe(pd.DataFrame(sups))

    # --- INVENTORY ---
    elif menu == "Inventory":
        st.title("📦 Stock Room")
        with st.expander("Add Product"):
            with st.form("add"):
                n = st.text_input("Name"); cat = st.text_input("Category")
                c1, c2, c3 = st.columns(3)
                p = c1.number_input("Selling Price", 0.0); cp = c2.number_input("Cost Price", 0.0); s = c3.number_input("Stock", 0)
                if st.form_submit_button("Save"):
                    run_query("INSERT INTO products (name, category, price, cost_price, stock) VALUES (?,?,?,?,?)", (n,cat,p,cp,s))
                    st.success("Saved"); refresh_all()
        
        prods = run_query("SELECT * FROM products", fetch=True)
        if prods:
            df = pd.DataFrame(prods)
            st.dataframe(df)
            if st.session_state.role == "admin":
                d_id = st.number_input("Delete ID", 0)
                if st.button("Delete Item") and d_id > 0:
                    run_query("DELETE FROM products WHERE id=?", (d_id,))
                    log_audit("DELETE_ITEM", f"Deleted Product ID {d_id}")
                    refresh_all()

    # --- CUSTOMERS ---
    elif menu == "Customers":
        st.title("👥 Customers")
        with st.expander("Register"):
            with st.form("cust"):
                n = st.text_input("Name"); p = st.text_input("Phone"); a = st.text_input("Address")
                if st.form_submit_button("Save"):
                    if run_query("INSERT INTO customers (phone, name, address, joined_date) VALUES (?,?,?,?)", (p,n,a,str(datetime.date.today()))):
                        st.success("Saved"); refresh_all()
                    else: st.error("Exists")
        
        custs = run_query("SELECT * FROM customers", fetch=True)
        if custs:
            st.dataframe(pd.DataFrame(custs))
            if st.session_state.role == "admin":
                d_ph = st.text_input("Delete Phone")
                if st.button("Delete Customer") and d_ph:
                    run_query("DELETE FROM customers WHERE phone=?", (d_ph,))
                    refresh_all()

    # --- REPORTS (CEO Only) ---
    elif menu == "Reports":
        st.title("📈 Business Intelligence")
        
        # Date Filter
        c1, c2 = st.columns(2)
        d1 = c1.date_input("Start Date", datetime.date.today().replace(day=1))
        d2 = c2.date_input("End Date", datetime.date.today())
        
        # Advanced Logic
        txs = run_query(f"SELECT * FROM transactions WHERE date BETWEEN '{d1}' AND '{d2}'", fetch=True)
        if txs:
            df = pd.DataFrame(txs)
            revenue = df[df['type']=='SALE']['total_amount'].sum()
            returns = abs(df[df['type']=='RETURN']['total_amount'].sum())
            net_sales = revenue - returns
            
            exps = run_query(f"SELECT SUM(amount) as v FROM expenses WHERE date BETWEEN '{d1}' AND '{d2}'", fetch=True)[0]['v'] or 0
            
            # Simple Profit Estimate (Assuming 10% margin if cost not tracked properly yet)
            est_profit = (net_sales * 0.15) - exps
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Gross Sales", f"₹{revenue:,.0f}")
            col2.metric("Returns", f"₹{returns:,.0f}")
            col3.metric("Expenses", f"₹{exps:,.0f}")
            col4.metric("Est. Net Profit", f"₹{est_profit:,.0f}", delta="Approx Margin")
            
            st.markdown("### 📝 Audit Logs")
            logs = run_query("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 20", fetch=True)
            st.dataframe(pd.DataFrame(logs), use_container_width=True)

if __name__ == "__main__":
    main()
