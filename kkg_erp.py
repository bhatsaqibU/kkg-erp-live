import streamlit as st
import pandas as pd
import datetime
import time
from fpdf import FPDF
import sqlite3
import os
import hashlib

# ==========================================
# 1. ENTERPRISE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="KKG ERP",
    page_icon="🚜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Business Constants
BUSINESS_META = {
    "name": "KISAN KHIDMAT GHAR",
    "address": "Chakoora, Pulwama, J&K",
    "phone": "+91 9622749245",
    "gst": "01AAAAA0000A1Z5", # Placeholder
    "currency": "₹"
}

# Credentials (In a real V2 phase, these move to DB)
USERS = {
    "admin": {"pass": "kkg@123", "role": "admin", "name": "Owner"},
    "staff": {"pass": "staff1", "role": "staff", "name": "Counter Staff"}
}

DB_FILE = "kkg_database.sqlite"

# ==========================================
# 2. IMMERSIVE UI ENGINE (CSS)
# ==========================================
def inject_industrial_css():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
        
        /* BASE THEME */
        .stApp { background-color: #f1f5f9; font-family: 'Inter', sans-serif; }
        
        /* SIDEBAR (Midnight Navy) */
        [data-testid="stSidebar"] {
            background-color: #0f172a;
            border-right: 1px solid #1e293b;
        }
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
            color: #f1f5f9 !important;
        }
        
        /* METRIC CARDS (Glassmorphism) */
        div[data-testid="stMetric"] {
            background: white !important;
            border: 1px solid #e2e8f0;
            padding: 20px !important;
            border-radius: 12px !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            transition: transform 0.2s;
        }
        div[data-testid="stMetric"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
            border-color: #3b82f6;
        }
        [data-testid="stMetricLabel"] { color: #64748b; font-weight: 600; font-size: 0.9rem; }
        [data-testid="stMetricValue"] { color: #0f172a; font-weight: 800; font-size: 1.8rem; }
        
        /* PRIMARY BUTTONS */
        .stButton button {
            background: linear-gradient(135deg, #2563eb, #1d4ed8);
            color: white !important;
            font-weight: 600;
            border-radius: 8px;
            border: none;
            padding: 0.6rem 1rem;
            width: 100%;
            box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2);
        }
        .stButton button:hover { background: #1e40af; }
        
        /* DANGER/DELETE BUTTONS */
        button[kind="secondary"] {
            background: white !important;
            color: #dc2626 !important;
            border: 1px solid #fecaca !important;
        }
        
        /* TABLES */
        [data-testid="stDataFrame"] {
            background: white;
            border-radius: 12px;
            border: 1px solid #e2e8f0;
            padding: 10px;
        }
        
        /* INPUTS */
        input, select {
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 8px;
            color: #0f172a;
        }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 3. DATABASE MANAGER CLASS
# ==========================================
class DatabaseManager:
    def __init__(self):
        self.db_file = DB_FILE
        self.init_schema()

    def get_connection(self):
        # Hybrid Check: Cloud vs Local
        if hasattr(st, "secrets") and "postgres" in st.secrets:
            try:
                import psycopg2
                return "POSTGRES", psycopg2.connect(st.secrets["postgres"]["url"])
            except: pass # Fallback
        
        return "SQLITE", sqlite3.connect(self.db_file, check_same_thread=False)

    def run(self, query, params=None, fetch=False):
        db_type, conn = self.get_connection()
        if not conn: return [] if fetch else False

        # Postgres Parameter Fix
        if db_type == "POSTGRES":
            query = query.replace('?', '%s')

        try:
            cur = conn.cursor()
            if db_type == "SQLITE": conn.row_factory = sqlite3.Row
            
            cur.execute(query, params or ())
            
            if fetch:
                if db_type == "SQLITE":
                    res = [dict(row) for row in cur.fetchall()]
                else:
                    cols = [desc[0] for desc in cur.description]
                    res = [dict(zip(cols, row)) for row in cur.fetchall()]
                conn.close()
                return res
            else:
                conn.commit()
                conn.close()
                return True
        except Exception as e:
            if db_type == "POSTGRES": conn.rollback()
            # st.error(f"DB Error: {e}") # Uncomment for debugging
            return [] if fetch else False

    def init_schema(self):
        """Ensures all 7 industrial tables exist."""
        db_type, _ = self.get_connection()
        if not db_type: return
        
        pk = "SERIAL PRIMARY KEY" if db_type == "POSTGRES" else "INTEGER PRIMARY KEY AUTOINCREMENT"
        
        tables = [
            f"CREATE TABLE IF NOT EXISTS products (id {pk}, name TEXT, category TEXT, price REAL, cost_price REAL DEFAULT 0, stock INTEGER, supplier_id INTEGER)",
            f"CREATE TABLE IF NOT EXISTS customers (phone TEXT PRIMARY KEY, name TEXT, address TEXT, joined_date TEXT, credit_limit REAL DEFAULT 50000)",
            f"CREATE TABLE IF NOT EXISTS suppliers (id {pk}, name TEXT, phone TEXT, address TEXT)",
            f"CREATE TABLE IF NOT EXISTS transactions (invoice_id TEXT PRIMARY KEY, customer_phone TEXT, date TEXT, type TEXT, total_amount REAL, paid_amount REAL, due_amount REAL, payment_mode TEXT, created_by TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
            f"CREATE TABLE IF NOT EXISTS invoice_items (id {pk}, invoice_id TEXT, product_name TEXT, quantity INTEGER, unit_price REAL, cost_price REAL, total_price REAL)",
            f"CREATE TABLE IF NOT EXISTS expenses (id {pk}, date TEXT, category TEXT, amount REAL, note TEXT, added_by TEXT)",
            f"CREATE TABLE IF NOT EXISTS system_logs (id {pk}, timestamp TEXT, username TEXT, action TEXT, details TEXT)"
        ]
        for t in tables: self.run(t)

# Initialize DB Engine
db = DatabaseManager()

# ==========================================
# 4. BUSINESS LOGIC & AUDIT
# ==========================================
def log_audit(action, details):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user = st.session_state.get('username', 'system')
    db.run("INSERT INTO system_logs (timestamp, username, action, details) VALUES (?,?,?,?)", 
           (ts, user, action, details))

# --- LIVE FINANCIALS (NO CACHE) ---
def get_live_metrics():
    today = datetime.date.today().isoformat()
    
    # 1. Sales
    sales = db.run("SELECT SUM(total_amount) as v FROM transactions WHERE date=? AND type='SALE'", (today,), fetch=True)
    sales_val = sales[0]['v'] if sales and sales[0]['v'] else 0
    
    # 2. Expenses
    exps = db.run("SELECT SUM(amount) as v FROM expenses WHERE date=?", (today,), fetch=True)
    exp_val = exps[0]['v'] if exps and exps[0]['v'] else 0
    
    # 3. Market Debt
    tot_sales = db.run("SELECT SUM(total_amount) as v FROM transactions WHERE type='SALE'", fetch=True)
    tot_paid = db.run("SELECT SUM(paid_amount) as v FROM transactions", fetch=True)
    debt = (tot_sales[0]['v'] or 0) - (tot_paid[0]['v'] or 0)
    
    return sales_val, exp_val, debt

# --- STATIC DATA (CACHED FOR SPEED) ---
@st.cache_data(ttl=300)
def get_master_lists():
    prods = db.run("SELECT * FROM products ORDER BY name", fetch=True)
    custs = db.run("SELECT * FROM customers ORDER BY name", fetch=True)
    sups = db.run("SELECT * FROM suppliers ORDER BY name", fetch=True)
    return prods, custs, sups

def refresh_app():
    st.cache_data.clear()
    st.rerun()

# ==========================================
# 5. PROFESSIONAL PDF CLASS
# ==========================================
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 22)
        self.set_text_color(15, 23, 42)
        self.cell(0, 10, BUSINESS_META["name"], 0, 1, 'C')
        
        self.set_font('Arial', '', 10)
        self.set_text_color(100, 116, 139)
        self.cell(0, 5, BUSINESS_META["address"], 0, 1, 'C')
        self.cell(0, 5, f"Contact: {BUSINESS_META['phone']}", 0, 1, 'C')
        self.ln(10)
        self.set_draw_color(200); self.line(10, 32, 200, 32); self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, 'Software by KKG ERP System', 0, 0, 'C')

def create_invoice(tx, items, cust):
    pdf = PDF()
    pdf.add_page()
    
    # Meta
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(130, 10, "INVOICE", 0, 0)
    pdf.set_font('Arial', '', 10)
    pdf.cell(60, 10, f"Date: {tx['date']}", 0, 1, 'R')
    
    # Customer Box
    pdf.set_fill_color(248, 250, 252)
    pdf.rect(10, 45, 190, 20, 'F')
    pdf.set_y(48); pdf.set_x(12)
    pdf.cell(100, 5, f"To: {cust['name']}", 0, 1)
    pdf.set_x(12)
    pdf.cell(100, 5, f"Ph: {cust['phone']}", 0, 1)
    pdf.set_y(48); pdf.set_x(140)
    pdf.cell(50, 5, f"Inv #: {tx['invoice_id']}", 0, 1)
    pdf.ln(20)
    
    # Header
    pdf.set_fill_color(15, 23, 42); pdf.set_text_color(255, 255, 255)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(10, 8, "#", 1, 0, 'C', 1)
    pdf.cell(90, 8, "Item", 1, 0, 'L', 1)
    pdf.cell(25, 8, "Price", 1, 0, 'R', 1)
    pdf.cell(20, 8, "Qty", 1, 0, 'C', 1)
    pdf.cell(45, 8, "Total", 1, 1, 'R', 1)
    pdf.ln(8)
    
    # Items
    pdf.set_text_color(0, 0, 0); pdf.set_font('Arial', '', 10)
    for idx, i in enumerate(items):
        name = i.get('product_name') or i.get('name')
        pdf.cell(10, 8, str(idx+1), 1, 0, 'C')
        pdf.cell(90, 8, str(name)[:45], 1, 0, 'L')
        pdf.cell(25, 8, f"{float(i.get('unit_price', i.get('price'))):.0f}", 1, 0, 'R')
        pdf.cell(20, 8, str(i.get('quantity', i.get('qty'))), 1, 0, 'C')
        pdf.cell(45, 8, f"{float(i.get('total_price', i.get('total'))):.0f}", 1, 1, 'R')
        pdf.ln(8)
        
    # Total
    pdf.ln(5); pdf.set_font('Arial', 'B', 12)
    pdf.cell(145, 10, "Total Payable", 0, 0, 'R')
    pdf.cell(45, 10, f"Rs {tx['total_amount']:,.0f}", 0, 1, 'R')
    
    # Due Logic
    paid = float(tx.get('paid_amount', 0))
    due = float(tx.get('due_amount', 0))
    
    pdf.set_font('Arial', '', 10)
    pdf.cell(145, 6, "Paid Amount", 0, 0, 'R')
    pdf.cell(45, 6, f"{paid:,.0f}", 0, 1, 'R')
    
    if due > 0:
        pdf.set_text_color(220, 38, 38) # Red
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(145, 10, "Balance Due", 0, 0, 'R')
        pdf.cell(45, 10, f"Rs {due:,.0f}", 0, 1, 'R')
        
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 6. APP MODULES (UI & LOGIC)
# ==========================================
def login():
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        with st.form("login_f"):
            st.markdown("<h2 style='text-align:center;'>🔐 Secure Login</h2>", unsafe_allow_html=True)
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Enter KKG ERP"):
                if u in USERS and USERS[u]["pass"] == p:
                    st.session_state.logged_in = True
                    st.session_state.user = u
                    st.session_state.role = USERS[u]["role"]
                    log_audit("LOGIN", f"{u} accessed system")
                    st.rerun()
                else:
                    st.error("Access Denied")

def main():
    inject_industrial_css()
    
    if 'logged_in' not in st.session_state:
        login()
        return

    # --- SIDEBAR ---
    st.sidebar.markdown(f"""
        <div style='text-align: center; padding: 20px 0;'>
            <h1>🚜 KKG</h1>
            <p style='color:#94a3b8; font-size:12px;'>v30.0 Titanium</p>
            <div style='background:#1e293b; padding:5px; border-radius:5px; margin-top:10px;'>
                <small>User: {st.session_state.user.upper()}</small>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    menu = ["Dashboard", "POS Terminal", "Inventory", "Customers", "Suppliers", "Expenses", "Ledger", "Reports"]
    if st.session_state.role == "staff":
        menu = ["POS Terminal", "Customers", "Inventory"]
        
    choice = st.sidebar.radio("Main Menu", menu, label_visibility="collapsed")
    
    if st.sidebar.button("Log Out"):
        st.session_state.clear()
        st.rerun()

    # --- 1. DASHBOARD (LIVE) ---
    if choice == "Dashboard":
        st.title("Executive Dashboard")
        
        # Real-time Metrics
        sales, exps, debt = get_live_metrics()
        
        # Calculate Estimated Net Profit (Gross Margin Logic could go here)
        # For now: Revenue - Expenses
        profit = sales - exps
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Revenue Today", f"₹{sales:,.0f}")
        c2.metric("Expenses Today", f"₹{exps:,.0f}")
        c3.metric("Net Cash Flow", f"₹{profit:,.0f}", delta="Estimated")
        c4.metric("Market Debt", f"₹{debt:,.0f}", delta_color="inverse")
        
        st.markdown("---")
        
        # Charts Area
        g1, g2 = st.columns(2)
        with g1:
            st.subheader("Recent Sales Trend")
            trend = db.run("SELECT date, SUM(total_amount) as sales FROM transactions WHERE type='SALE' GROUP BY date ORDER BY date DESC LIMIT 14", fetch=True)
            if trend:
                df = pd.DataFrame(trend)
                df['date'] = pd.to_datetime(df['date'])
                st.line_chart(df.set_index('date'))
            else: st.info("No sales data yet")
            
        with g2:
            st.subheader("Top Products")
            top = db.run("SELECT product_name, SUM(quantity) as qty FROM invoice_items GROUP BY product_name ORDER BY qty DESC LIMIT 5", fetch=True)
            if top: st.bar_chart(pd.DataFrame(top).set_index('product_name'))
            else: st.info("No product data yet")

    # --- 2. POS TERMINAL (FAST) ---
    elif choice == "POS Terminal":
        st.title("🛒 Sales Terminal")
        
        prods, custs, _ = get_master_lists()
        
        if not prods: st.warning("Inventory Empty"); st.stop()
        
        c_map = {f"{c['name']} | {c['phone']}": c for c in custs}
        p_map = {f"{p['name']} (₹{p['price']:.0f})": p for p in prods}
        
        c1, c2 = st.columns([1.5, 1])
        with c1:
            st.markdown("##### Add Item")
            with st.container():
                with st.form("pos_add"):
                    sel_c = st.selectbox("Customer", list(c_map.keys()))
                    sel_p = st.selectbox("Product", list(p_map.keys()))
                    qty = st.number_input("Quantity", 1, 1000)
                    
                    if st.form_submit_button("Add to Bill"):
                        if 'cart' not in st.session_state: st.session_state.cart = []
                        prod = p_map[sel_p]
                        
                        # Stock Validation
                        in_cart = sum(i['qty'] for i in st.session_state.cart if i['id'] == prod['id'])
                        if (in_cart + qty) > prod['stock']:
                            st.error(f"Low Stock! Only {prod['stock']} units available.")
                        else:
                            st.session_state.cart.append({**prod, 'qty': qty, 'total': qty*prod['price']})
                            st.success("Added")

        with c2:
            st.markdown("##### Summary")
            if 'cart' in st.session_state and st.session_state.cart:
                df = pd.DataFrame(st.session_state.cart)
                st.dataframe(df[['name', 'qty', 'total']], hide_index=True, use_container_width=True)
                
                total = df['total'].sum()
                st.markdown(f"### Total: ₹{total:,.0f}")
                
                with st.form("checkout"):
                    paid = st.number_input("Amount Received", 0.0)
                    mode = st.selectbox("Payment Mode", ["Cash", "UPI", "Credit"])
                    
                    if st.form_submit_button("✅ Finalize Sale"):
                        cust = c_map[sel_c]
                        inv_id = f"INV-{int(time.time())}"
                        due = total - paid
                        
                        # Atomic Transaction
                        db.run("INSERT INTO transactions (invoice_id, customer_phone, date, type, total_amount, paid_amount, due_amount, payment_mode, created_by) VALUES (?,?,?,?,?,?,?,?,?)",
                               (inv_id, cust['phone'], str(datetime.date.today()), 'SALE', total, paid, due, mode, st.session_state.user))
                        
                        for i in st.session_state.cart:
                            db.run("INSERT INTO invoice_items (invoice_id, product_name, quantity, unit_price, cost_price, total_price) VALUES (?,?,?,?,?,?)",
                                   (inv_id, i['name'], i['qty'], i['price'], i.get('cost_price', 0), i['total']))
                            db.run("UPDATE products SET stock = stock - ? WHERE id = ?", (i['qty'], i['id']))
                        
                        log_audit("SALE", f"Sold {inv_id} to {cust['name']}")
                        
                        # Generate PDF
                        st.session_state.pdf = create_invoice({'invoice_id': inv_id, 'date': str(datetime.date.today()), 'total_amount': total, 'paid_amount': paid, 'due_amount': due}, st.session_state.cart, cust)
                        
                        st.session_state.cart = []
                        refresh_app()
            
            if 'pdf' in st.session_state:
                st.success("Transaction Saved!")
                st.download_button("Download Invoice", st.session_state.pdf, "invoice.pdf", "application/pdf")

    # --- 3. INVENTORY (PROFIT ENGINE) ---
    elif choice == "Inventory":
        st.title("📦 Stock & Pricing")
        
        with st.expander("Add New Product"):
            with st.form("add_p"):
                c1, c2, c3, c4 = st.columns(4)
                n = c1.text_input("Name"); cat = c2.text_input("Category")
                sp = c3.number_input("Selling Price", 0.0); cp = c4.number_input("Cost Price (for Profit)", 0.0)
                stk = st.number_input("Stock", 0)
                
                # Supplier Link
                _, _, sups = get_master_lists()
                sup_map = {s['name']: s['id'] for s in sups} if sups else {}
                sup_sel = st.selectbox("Supplier", ["None"] + list(sup_map.keys()))
                sup_id = sup_map.get(sup_sel, None)
                
                if st.form_submit_button("Save Item"):
                    db.run("INSERT INTO products (name, category, price, cost_price, stock, supplier_id) VALUES (?,?,?,?,?,?)", 
                           (n, cat, sp, cp, stk, sup_id))
                    refresh_app()
        
        prods, _, _ = get_master_lists()
        if prods:
            df = pd.DataFrame(prods)
            st.dataframe(df[['name', 'category', 'price', 'cost_price', 'stock']], use_container_width=True)
            
            # Bulk Delete (Admin Only)
            if st.session_state.role == "admin":
                with st.expander("Admin Actions"):
                    d_id = st.number_input("ID to Delete", 0)
                    if st.button("Delete Item", type="secondary") and d_id:
                        db.run("DELETE FROM products WHERE id=?", (d_id,))
                        log_audit("DELETE", f"Deleted Product ID {d_id}")
                        refresh_app()

    # --- 4. CUSTOMERS ---
    elif choice == "Customers":
        st.title("👥 Customer Database")
        with st.expander("Add Customer"):
            with st.form("new_c"):
                n = st.text_input("Name"); p = st.text_input("Phone"); a = st.text_input("Address")
                clim = st.number_input("Credit Limit", 50000)
                if st.form_submit_button("Save"):
                    if db.run("INSERT INTO customers (phone, name, address, joined_date, credit_limit) VALUES (?,?,?,?,?)", (p, n, a, str(datetime.date.today()), clim)):
                        refresh_app()
                    else: st.error("Exists")
        
        _, custs, _ = get_master_lists()
        if custs: st.dataframe(pd.DataFrame(custs), use_container_width=True)

    # --- 5. EXPENSES (PROFIT KILLERS) ---
    elif choice == "Expenses":
        st.title("💸 Operational Expenses")
        c1, c2 = st.columns([1, 2])
        with c1:
            with st.form("exp"):
                cat = st.selectbox("Category", ["Rent", "Salary", "Tea", "Transport", "Electricity"])
                amt = st.number_input("Amount", 1.0); note = st.text_input("Note")
                if st.form_submit_button("Record"):
                    db.run("INSERT INTO expenses (date, category, amount, note, added_by) VALUES (?,?,?,?,?)", 
                           (str(datetime.date.today()), cat, amt, note, st.session_state.user))
                    refresh_app()
        with c2:
            exps = db.run("SELECT date, category, amount, note FROM expenses ORDER BY date DESC LIMIT 10", fetch=True)
            if exps: st.dataframe(pd.DataFrame(exps), use_container_width=True)

    # --- 6. SUPPLIERS (NEW) ---
    elif choice == "Suppliers":
        st.title("🚚 Supplier Management")
        with st.form("new_sup"):
            c1, c2 = st.columns(2)
            n = c1.text_input("Company Name"); p = c2.text_input("Contact Phone")
            a = st.text_input("Address")
            if st.form_submit_button("Add Supplier"):
                db.run("INSERT INTO suppliers (name, phone, address) VALUES (?,?,?)", (n,p,a))
                refresh_app()
        
        _, _, sups = get_master_lists()
        if sups: st.dataframe(pd.DataFrame(sups), use_container_width=True)

    # --- 7. LEDGER ---
    elif choice == "Ledger":
        st.title("📖 Customer Ledger")
        _, custs, _ = get_master_lists()
        
        if custs:
            c_map = {f"{c['name']} ({c['phone']})": c for c in custs}
            sel = st.selectbox("Select Customer", list(c_map.keys()))
            cust = c_map[sel]
            
            col1, col2 = st.columns(2)
            d1 = col1.date_input("From", datetime.date.today() - datetime.timedelta(days=365))
            d2 = col2.date_input("To", datetime.date.today())
            
            if st.button("Load History"):
                txs = db.run(f"SELECT * FROM transactions WHERE customer_phone='{cust['phone']}' AND date BETWEEN '{d1}' AND '{d2}' ORDER BY created_at DESC", fetch=True)
                if txs:
                    st.dataframe(pd.DataFrame(txs)[['date', 'invoice_id', 'total_amount', 'paid_amount', 'due_amount']], use_container_width=True)
                    
                    st.markdown("### Reprint")
                    sale_txs = [t for t in txs if t['type'] == 'SALE']
                    if sale_txs:
                        inv_ids = [t['invoice_id'] for t in sale_txs]
                        sel_inv = st.selectbox("Select Invoice", inv_ids)
                        if st.button("Generate Copy"):
                            inv_data = next(t for t in sale_txs if t['invoice_id'] == sel_inv)
                            items = db.run(f"SELECT * FROM invoice_items WHERE invoice_id='{sel_inv}'", fetch=True)
                            pdf = create_invoice(inv_data, items, cust)
                            st.download_button("Download PDF", pdf, f"{sel_inv}.pdf", "application/pdf")
                else: st.info("No data")

    # --- 8. REPORTS (ADMIN ONLY) ---
    elif choice == "Reports" and st.session_state.role == "admin":
        st.title("📈 Business Intelligence")
        
        if st.button("Export All Sales (CSV)"):
            df = pd.DataFrame(db.run("SELECT * FROM transactions", fetch=True))
            st.download_button("Download CSV", df.to_csv(), "sales_dump.csv")
            
        st.markdown("### 📝 Audit Logs")
        logs = db.run("SELECT timestamp, username, action, details FROM system_logs ORDER BY timestamp DESC LIMIT 50", fetch=True)
        if logs: st.dataframe(pd.DataFrame(logs), use_container_width=True)

if __name__ == "__main__":
    main()
