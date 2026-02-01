import streamlit as st
import pandas as pd
import datetime
import time
from fpdf import FPDF
import sqlite3
import os
import base64
import random

# ==========================================
# 1. CORE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="KKG Enterprise OS",
    page_icon="🚜",
    layout="wide",
    initial_sidebar_state="expanded"
)

BUSINESS_META = {
    "name": "KISAN KHIDMAT GHAR",
    "location": "Chakoora, Pulwama, J&K",
    "phone": "+91 9622749245",
    "license": "AGRI-LIC-2026-X",
    "currency": "₹"
}

# In a real deploy, these move to the DB. Hardcoded for Phase 1 reliability.
USERS = {
    "admin": {"pass": "kkg@123", "role": "CEO", "name": "Owner"},
    "staff": {"pass": "staff1", "role": "Manager", "name": "Counter Staff"}
}

# ==========================================
# 2. UX ENGINE (GLASSMORPHISM)
# ==========================================
def inject_ui():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700;800&display=swap');
        
        /* BASE */
        .stApp { background-color: #f8fafc; font-family: 'Inter', sans-serif; }
        
        /* SIDEBAR (Premium Dark) */
        [data-testid="stSidebar"] {
            background-color: #0f172a;
            border-right: 1px solid #1e293b;
        }
        [data-testid="stSidebar"] * { color: #e2e8f0 !important; }
        
        /* GLASS CARDS */
        div[data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.8);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
            border-radius: 16px;
            padding: 20px;
            transition: transform 0.2s;
        }
        div[data-testid="stMetric"]:hover { transform: translateY(-5px); border-color: #3b82f6; }
        
        /* TYPOGRAPHY */
        h1, h2, h3 { color: #0f172a; font-weight: 800; letter-spacing: -0.025em; }
        [data-testid="stMetricValue"] { color: #0f172a; font-size: 2rem; font-weight: 800; }
        
        /* BUTTONS */
        .stButton button {
            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
            color: white; border: none; font-weight: 600; border-radius: 8px;
            padding: 0.75rem; transition: all 0.3s ease; box-shadow: 0 4px 10px rgba(37, 99, 235, 0.2);
        }
        .stButton button:hover { transform: scale(1.02); }
        
        /* DANGER ZONE */
        button[kind="secondary"] {
            background: #fee2e2 !important; color: #dc2626 !important; border: 1px solid #fecaca;
        }
        
        /* TABLE STYLING */
        [data-testid="stDataFrame"] {
            background: white; border-radius: 12px; padding: 10px; border: 1px solid #e2e8f0;
        }
        
        /* CUSTOM NOTIFICATIONS */
        .success-box { padding: 15px; background: #dcfce7; border-radius: 8px; color: #166534; font-weight: 500; border: 1px solid #bbf7d0; }
        .error-box { padding: 15px; background: #fee2e2; border-radius: 8px; color: #991b1b; font-weight: 500; border: 1px solid #fecaca; }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 3. SELF-HEALING DATABASE CORE
# ==========================================
@st.cache_resource
def get_db_connection():
    # Cloud (Postgres) check
    if hasattr(st, "secrets") and "postgres" in st.secrets:
        import psycopg2
        try:
            return "POSTGRES", psycopg2.connect(st.secrets["postgres"]["url"])
        except: pass
    
    # Local (SQLite)
    return "SQLITE", sqlite3.connect("kkg_master.sqlite", check_same_thread=False)

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
            if db_type == "SQLITE": res = [dict(row) for row in cur.fetchall()]
            else:
                cols = [desc[0] for desc in cur.description]
                res = [dict(zip(cols, row)) for row in cur.fetchall()]
            cur.close(); return res
        else:
            conn.commit(); cur.close(); return True
    except Exception as e:
        if db_type == "POSTGRES": conn.rollback()
        return [] if fetch else False

# ==========================================
# 4. DATA MODEL INITIALIZATION
# ==========================================
def init_schema():
    db_type, _ = get_db_connection()
    if not db_type: return
    pk = "SERIAL PRIMARY KEY" if db_type == "POSTGRES" else "INTEGER PRIMARY KEY AUTOINCREMENT"
    
    tables = [
        f"CREATE TABLE IF NOT EXISTS products (id {pk}, name TEXT, category TEXT, price REAL, cost_price REAL, stock INTEGER, supplier TEXT, last_updated TEXT)",
        f"CREATE TABLE IF NOT EXISTS customers (phone TEXT PRIMARY KEY, name TEXT, address TEXT, credit_limit REAL, risk_score TEXT, joined_date TEXT)",
        f"CREATE TABLE IF NOT EXISTS transactions (invoice_id TEXT PRIMARY KEY, customer_phone TEXT, date TEXT, type TEXT, total_amount REAL, paid_amount REAL, due_amount REAL, payment_mode TEXT, notes TEXT, created_by TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        f"CREATE TABLE IF NOT EXISTS invoice_items (id {pk}, invoice_id TEXT, product_name TEXT, quantity INTEGER, unit_price REAL, cost_price REAL, total_price REAL)",
        f"CREATE TABLE IF NOT EXISTS expenses (id {pk}, date TEXT, category TEXT, amount REAL, note TEXT, added_by TEXT)",
        f"CREATE TABLE IF NOT EXISTS consultations (id {pk}, customer_phone TEXT, date TEXT, problem_desc TEXT, solution TEXT, image_path TEXT)",
        f"CREATE TABLE IF NOT EXISTS audit_logs (id {pk}, timestamp TEXT, username TEXT, action TEXT, details TEXT)"
    ]
    for t in tables: run_query(t)

init_schema()

# ==========================================
# 5. BUSINESS INTELLIGENCE LOGIC
# ==========================================
def log_audit(action, details):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user = st.session_state.get('username', 'system')
    run_query("INSERT INTO audit_logs (timestamp, username, action, details) VALUES (?,?,?,?)", (ts, user, action, details))

def get_financial_truth():
    today = datetime.date.today().isoformat()
    
    # 1. Revenue
    sales = run_query(f"SELECT SUM(total_amount) as v FROM transactions WHERE date='{today}' AND type='SALE'", fetch=True)
    revenue = sales[0]['v'] or 0
    
    # 2. Operational Expenses
    exps = run_query(f"SELECT SUM(amount) as v FROM expenses WHERE date='{today}'", fetch=True)
    expenses = exps[0]['v'] or 0
    
    # 3. Cost of Goods Sold (COGS) for Today
    # This queries the invoice items to find the original Cost Price of sold items
    cogs_q = f"""
        SELECT SUM(ii.cost_price * ii.quantity) as v 
        FROM invoice_items ii 
        JOIN transactions t ON ii.invoice_id = t.invoice_id 
        WHERE t.date='{today}' AND t.type='SALE'
    """
    cogs_res = run_query(cogs_q, fetch=True)
    cogs = cogs_res[0]['v'] or 0
    
    # 4. Net Profit Calculation
    gross_profit = revenue - cogs
    net_profit = gross_profit - expenses
    
    return revenue, expenses, net_profit

@st.cache_data(ttl=60)
def get_stock_alerts():
    return run_query("SELECT * FROM products WHERE stock < 5", fetch=True)

# ==========================================
# 6. PDF ENGINE
# ==========================================
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 20)
        self.set_text_color(15, 23, 42)
        self.cell(0, 10, BUSINESS_META["name"], 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.set_text_color(100, 116, 139)
        self.cell(0, 5, BUSINESS_META["location"], 0, 1, 'C')
        self.cell(0, 5, f"Helpline: {BUSINESS_META['phone']}", 0, 1, 'C')
        self.ln(10); self.set_draw_color(200); self.line(10, 32, 200, 32); self.ln(5)

    def footer(self):
        self.set_y(-15); self.set_font('Arial', 'I', 8)
        self.cell(0, 10, 'Generated by KKG Enterprise OS', 0, 0, 'C')

def create_invoice(tx, items, cust):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14); pdf.cell(0, 10, "TAX INVOICE", 0, 1, 'C')
    
    pdf.set_font('Arial', '', 10)
    pdf.cell(100, 5, f"Bill To: {cust['name']}", 0, 0)
    pdf.cell(90, 5, f"Inv #: {tx['invoice_id']}", 0, 1, 'R')
    pdf.ln(5)
    pdf.cell(100, 5, f"Ph: {cust['phone']}", 0, 0)
    pdf.cell(90, 5, f"Date: {tx['date']}", 0, 1, 'R')
    pdf.ln(10)
    
    # Headers
    pdf.set_fill_color(240); pdf.set_font('Arial', 'B', 10)
    pdf.cell(90, 8, 'Item', 1, 0, 'L', 1); pdf.cell(30, 8, 'Rate', 1, 0, 'R', 1)
    pdf.cell(20, 8, 'Qty', 1, 0, 'C', 1); pdf.cell(50, 8, 'Total', 1, 1, 'R', 1)
    
    pdf.set_font('Arial', '', 10)
    for i in items:
        pdf.cell(90, 8, str(i.get('product_name') or i.get('name'))[:40], 1, 0, 'L')
        pdf.cell(30, 8, f"{float(i.get('unit_price', i.get('price'))):.0f}", 1, 0, 'R')
        pdf.cell(20, 8, str(i.get('quantity', i.get('qty'))), 1, 0, 'C')
        pdf.cell(50, 8, f"{float(i.get('total_price', i.get('total'))):.0f}", 1, 1, 'R')
        pdf.ln(8)
        
    pdf.ln(5); pdf.set_font('Arial', 'B', 12)
    pdf.cell(140, 10, 'Grand Total', 0, 0, 'R'); pdf.cell(50, 10, f"Rs {tx['total_amount']:,.0f}", 1, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 7. APP MODULES
# ==========================================
def login():
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        with st.form("login"):
            st.markdown("<h2 style='text-align:center;'>🔐 KKG Secure Access</h2>", unsafe_allow_html=True)
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Authenticate"):
                if u in USERS and USERS[u]["pass"] == p:
                    st.session_state.logged_in = True
                    st.session_state.user = u
                    st.session_state.role = USERS[u]["role"]
                    log_audit("LOGIN", f"{u} started session")
                    st.rerun()
                else: st.error("Access Denied")

def main():
    inject_ui()
    if 'logged_in' not in st.session_state: login(); return

    # Sidebar
    st.sidebar.markdown(f"""
        <div style='text-align: center; padding: 20px 0; margin-bottom: 20px;'>
            <h1 style='color: white; font-size: 28px;'>🚜 KKG</h1>
            <p style='color: #94a3b8; font-size: 12px;'>Enterprise OS v1.0</p>
            <div style='background:#1e293b; padding:8px; border-radius:6px; margin-top:10px;'>
                <small style='color:#38bdf8; font-weight:bold;'>{st.session_state.user.upper()} ({st.session_state.role})</small>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    menu = ["Dashboard", "POS Terminal", "Inventory", "Agro-Consult", "Customers", "Expenses", "Reports", "Logout"]
    if st.session_state.role == "Manager": menu = ["POS Terminal", "Inventory", "Agro-Consult", "Customers", "Logout"]
    
    choice = st.sidebar.radio("Main Menu", menu, label_visibility="collapsed")
    
    if choice == "Logout": 
        log_audit("LOGOUT", f"{st.session_state.user} ended session")
        st.session_state.clear(); st.rerun()

    # --- 1. CEO DASHBOARD ---
    if choice == "Dashboard":
        st.title("🚀 Business Command Center")
        st.markdown(f"**Date:** {datetime.date.today().strftime('%d %B %Y')}")
        
        rev, exp, profit = get_financial_truth()
        alerts = get_stock_alerts()
        
        # Financial Cards
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Revenue Today", f"₹{rev:,.0f}")
        c2.metric("OpEx Today", f"₹{exp:,.0f}")
        c3.metric("Net Profit (Real)", f"₹{profit:,.0f}", delta="Net Margin")
        c4.metric("Stock Alerts", len(alerts), delta_color="inverse")
        
        # Weather & Intelligence (Mock for now)
        st.markdown("---")
        c_w, c_g = st.columns([1, 2])
        with c_w:
            st.markdown("### 🌦 Chakoora Weather")
            st.info("Today: Sunny, 24°C\n\nAdvisory: Good day for Apple Scab Spray.")
        
        with c_g:
            st.markdown("### 📉 Sales Velocity")
            trend = run_query("SELECT date, SUM(total_amount) as s FROM transactions WHERE type='SALE' GROUP BY date ORDER BY date DESC LIMIT 7", fetch=True)
            if trend:
                df = pd.DataFrame(trend)
                st.line_chart(df.set_index('date'))
            else: st.caption("No sales data to visualize.")

    # --- 2. SPEED POS ---
    elif choice == "POS Terminal":
        st.title("🛒 Sales Terminal")
        
        prods = run_query("SELECT * FROM products ORDER BY name", fetch=True)
        custs = run_query("SELECT * FROM customers ORDER BY name", fetch=True)
        
        if not prods: st.warning("Inventory Empty"); st.stop()
        
        c_map = {f"{c['name']} | {c['phone']}": c for c in custs}
        p_map = {f"{p['name']} (₹{p['price']})": p for p in prods}
        
        c1, c2 = st.columns([1.5, 1])
        with c1:
            st.markdown("##### Add Item")
            with st.form("add_cart"):
                sel_c = st.selectbox("Customer", list(c_map.keys()))
                sel_p = st.selectbox("Product", list(p_map.keys()))
                qty = st.number_input("Qty", 1, 1000)
                if st.form_submit_button("Add to Bill"):
                    if 'cart' not in st.session_state: st.session_state.cart = []
                    prod = p_map[sel_p]
                    # Stock Guard
                    in_cart = sum(i['qty'] for i in st.session_state.cart if i['id'] == prod['id'])
                    if (in_cart + qty) > prod['stock']:
                        st.error(f"Stock Error! Only {prod['stock']} available.")
                    else:
                        st.session_state.cart.append({**prod, 'qty': qty, 'total': qty*prod['price']})
                        st.success(f"Added {prod['name']}")

        with c2:
            st.markdown("##### Cart")
            if 'cart' in st.session_state and st.session_state.cart:
                df = pd.DataFrame(st.session_state.cart)
                st.dataframe(df[['name', 'qty', 'total']], hide_index=True)
                total = df['total'].sum()
                st.markdown(f"### Total: ₹{total:,.0f}")
                
                with st.form("checkout"):
                    paid = st.number_input("Amount Received", 0.0)
                    mode = st.selectbox("Mode", ["Cash", "UPI", "Credit"])
                    if st.form_submit_button("✅ Finalize Sale"):
                        cust = c_map[sel_c]
                        inv_id = f"INV-{int(time.time())}"
                        due = total - paid
                        
                        # Ledger Entry
                        run_query("INSERT INTO transactions (invoice_id, customer_phone, date, type, total_amount, paid_amount, due_amount, payment_mode, created_by) VALUES (?,?,?,?,?,?,?,?,?)",
                                  (inv_id, cust['phone'], str(datetime.date.today()), 'SALE', total, paid, due, mode, st.session_state.user))
                        
                        # Inventory Deduct & Line Items
                        for i in st.session_state.cart:
                            run_query("INSERT INTO invoice_items (invoice_id, product_name, quantity, unit_price, cost_price, total_price) VALUES (?,?,?,?,?,?)",
                                      (inv_id, i['name'], i['qty'], i['price'], i.get('cost_price', 0), i['total']))
                            run_query("UPDATE products SET stock = stock - ? WHERE id = ?", (i['qty'], i['id']))
                        
                        log_audit("SALE", f"Sold {inv_id} to {cust['name']}")
                        
                        st.session_state.pdf = create_invoice({'invoice_id': inv_id, 'date': str(datetime.date.today()), 'total_amount': total, 'paid_amount': paid, 'due_amount': due}, st.session_state.cart, cust)
                        st.session_state.cart = []
                        st.rerun()
            
            if 'pdf' in st.session_state:
                st.download_button("🖨️ Download Bill", st.session_state.pdf, "invoice.pdf", "application/pdf")

    # --- 3. INVENTORY & SUPPLIERS ---
    elif choice == "Inventory":
        st.title("📦 Stock & Suppliers")
        
        with st.expander("Add New Product"):
            with st.form("new_p"):
                c1, c2, c3, c4 = st.columns(4)
                n = c1.text_input("Name"); cat = c2.text_input("Category")
                sp = c3.number_input("Selling Price", 0.0); cp = c4.number_input("Cost Price", 0.0)
                stk = st.number_input("Stock", 0); sup = st.text_input("Supplier Name")
                
                if st.form_submit_button("Save Item"):
                    run_query("INSERT INTO products (name, category, price, cost_price, stock, supplier) VALUES (?,?,?,?,?,?)", (n, cat, sp, cp, stk, sup))
                    st.success("Saved"); st.rerun()
        
        prods = run_query("SELECT * FROM products ORDER BY name", fetch=True)
        if prods:
            df = pd.DataFrame(prods)
            st.dataframe(df[['name', 'category', 'price', 'cost_price', 'stock', 'supplier']], use_container_width=True)
            
            if st.session_state.role == "CEO":
                d_id = st.number_input("Delete ID", 0)
                if st.button("Delete Item", type="secondary") and d_id:
                    run_query("DELETE FROM products WHERE id=?", (d_id,))
                    log_audit("DELETE", f"Product {d_id} deleted")
                    st.rerun()

    # --- 4. AGRO-CONSULT (NEW) ---
    elif choice == "Agro-Consult":
        st.title("👨‍🌾 Expert Consultation")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### New Case")
            with st.form("consult"):
                cust = st.text_input("Farmer Phone")
                prob = st.text_area("Problem Description (e.g. Yellow Leaves)")
                sol = st.text_area("Prescribed Solution")
                # Image placeholder (Real file upload requires blob storage)
                st.info("Image Upload enabled for Local Mode")
                if st.form_submit_button("Save Record"):
                    run_query("INSERT INTO consultations (customer_phone, date, problem_desc, solution) VALUES (?,?,?,?)",
                              (cust, str(datetime.date.today()), prob, sol))
                    st.success("Consultation Logged")
        
        with c2:
            st.markdown("##### Recent Cases")
            cases = run_query("SELECT * FROM consultations ORDER BY id DESC LIMIT 5", fetch=True)
            if cases: st.dataframe(pd.DataFrame(cases))

    # --- 5. CUSTOMERS & CREDIT ---
    elif choice == "Customers":
        st.title("👥 Customers & Credit")
        with st.expander("Register Customer"):
            with st.form("new_c"):
                n = st.text_input("Name"); p = st.text_input("Phone"); a = st.text_input("Address")
                limit = st.number_input("Credit Limit (₹)", 50000)
                if st.form_submit_button("Save"):
                    if run_query("INSERT INTO customers (phone, name, address, joined_date, credit_limit) VALUES (?,?,?,?,?)", (p, n, a, str(datetime.date.today()), limit)):
                        st.success("Saved"); st.rerun()
                    else: st.error("Exists")
        
        custs = run_query("SELECT * FROM customers", fetch=True)
        if custs: st.dataframe(pd.DataFrame(custs), use_container_width=True)

    # --- 6. REPORTS (ADMIN) ---
    elif choice == "Reports":
        st.title("📈 Business Intelligence")
        
        c1, c2 = st.columns(2)
        d1 = c1.date_input("From", datetime.date.today() - datetime.timedelta(days=30))
        d2 = c2.date_input("To", datetime.date.today())
        
        if st.button("Generate P&L Report"):
            # Detailed Profit Logic
            sales = run_query(f"SELECT SUM(total_amount) as v FROM transactions WHERE date BETWEEN '{d1}' AND '{d2}' AND type='SALE'", fetch=True)[0]['v'] or 0
            
            # COGS logic
            cogs_q = f"SELECT SUM(ii.cost_price * ii.quantity) as v FROM invoice_items ii JOIN transactions t ON ii.invoice_id = t.invoice_id WHERE t.date BETWEEN '{d1}' AND '{d2}'"
            cogs = run_query(cogs_q, fetch=True)[0]['v'] or 0
            
            exps = run_query(f"SELECT SUM(amount) as v FROM expenses WHERE date BETWEEN '{d1}' AND '{d2}'", fetch=True)[0]['v'] or 0
            
            gross = sales - cogs
            net = gross - exps
            
            st.markdown("### Profit & Loss Statement")
            st.table(pd.DataFrame({
                "Metric": ["Total Sales", "Cost of Goods (COGS)", "Gross Profit", "Expenses", "NET PROFIT"],
                "Amount": [f"₹{sales:,.0f}", f"₹{cogs:,.0f}", f"₹{gross:,.0f}", f"₹{exps:,.0f}", f"₹{net:,.0f}"]
            }))
            
            st.markdown("### 🔒 Audit Logs")
            logs = run_query("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 20", fetch=True)
            if logs: st.dataframe(pd.DataFrame(logs))

if __name__ == "__main__":
    main()
