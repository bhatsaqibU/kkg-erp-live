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

BUSINESS_INFO = {
    "name": "KISAN KHIDMAT GHAR",
    "address": "Chakoora, Pulwama, J&K",
    "phone": "+91 9622749245",
    "gst": "01AAAAA0000A1Z5"
}

# User Roles (In production, these should be in the DB, but hardcoded for reliability here)
USERS = {
    "admin": {"pass": "kkg@123", "role": "admin"},
    "staff": {"pass": "staff1", "role": "staff"}
}

# ==========================================
# 2. IMMERSIVE UI ENGINE (Glassmorphism)
# ==========================================
def inject_css():
    st.markdown("""
        <style>
        /* BASE THEME */
        .stApp { background-color: #f8fafc; font-family: 'Inter', sans-serif; }
        
        /* SIDEBAR (Dark Navy) */
        [data-testid="stSidebar"] {
            background-color: #0f172a;
            border-right: 1px solid #1e293b;
        }
        [data-testid="stSidebar"] * { color: #f1f5f9 !important; }
        
        /* METRIC CARDS */
        div[data-testid="stMetric"] {
            background: white !important;
            border: 1px solid #e2e8f0;
            padding: 20px !important;
            border-radius: 12px !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            transition: transform 0.2s;
        }
        div[data-testid="stMetric"]:hover { transform: translateY(-2px); }
        [data-testid="stMetricValue"] { color: #0f172a !important; font-weight: 800; }
        
        /* BUTTONS (Gradient Blue) */
        .stButton button {
            background: linear-gradient(135deg, #2563eb, #1d4ed8);
            color: white !important;
            font-weight: 600;
            border-radius: 8px;
            border: none;
            padding: 0.6rem 1rem;
            width: 100%;
            box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2);
        }
        .stButton button:hover { background: #1e40af; }
        
        /* DANGER BUTTONS */
        button[kind="secondary"] {
            background: #fee2e2 !important;
            color: #dc2626 !important;
            border: 1px solid #fecaca !important;
        }
        
        /* INPUTS */
        input, select {
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 8px;
        }
        
        /* TABLES */
        [data-testid="stDataFrame"] {
            background: white;
            border-radius: 12px;
            border: 1px solid #e2e8f0;
            padding: 10px;
        }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 3. SELF-HEALING DATABASE ENGINE
# ==========================================
@st.cache_resource
def get_db_connection():
    """Establishes a connection. Returns (Type, ConnectionObject)."""
    # Cloud Mode (Postgres)
    if hasattr(st, "secrets") and "postgres" in st.secrets:
        import psycopg2
        try:
            return "POSTGRES", psycopg2.connect(st.secrets["postgres"]["url"])
        except: return None, None
    
    # Local Mode (SQLite)
    return "SQLITE", sqlite3.connect("kkg_database.sqlite", check_same_thread=False)

def run_query(query, params=None, fetch=False):
    db_type, conn = get_db_connection()
    if not conn: return [] if fetch else False

    # Auto-Reconnect logic for Cloud
    if db_type == "POSTGRES":
        query = query.replace('?', '%s')
        if conn.closed:
            st.cache_resource.clear()
            db_type, conn = get_db_connection()

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
            cur.close()
            return res
        else:
            conn.commit()
            cur.close()
            return True

    except Exception as e:
        if db_type == "POSTGRES":
            conn.rollback()
        # Log error internally but keep UI clean
        print(f"DB Error: {e}")
        return [] if fetch else False

# ==========================================
# 4. SYSTEM INITIALIZATION
# ==========================================
def init_system():
    db_type, _ = get_db_connection()
    if not db_type: return
    pk = "SERIAL PRIMARY KEY" if db_type == "POSTGRES" else "INTEGER PRIMARY KEY AUTOINCREMENT"
    
    # Comprehensive Schema for Real Business
    tables = [
        f"CREATE TABLE IF NOT EXISTS products (id {pk}, name TEXT, category TEXT, price REAL, cost_price REAL DEFAULT 0, stock INTEGER, low_stock_threshold INTEGER DEFAULT 5)",
        f"CREATE TABLE IF NOT EXISTS customers (phone TEXT PRIMARY KEY, name TEXT, address TEXT, joined_date TEXT, credit_limit REAL DEFAULT 50000)",
        f"CREATE TABLE IF NOT EXISTS suppliers (id {pk}, name TEXT, phone TEXT, address TEXT)",
        f"CREATE TABLE IF NOT EXISTS transactions (invoice_id TEXT PRIMARY KEY, customer_phone TEXT, date TEXT, type TEXT, total_amount REAL, paid_amount REAL, due_amount REAL, payment_mode TEXT, notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        f"CREATE TABLE IF NOT EXISTS invoice_items (id {pk}, invoice_id TEXT, product_name TEXT, quantity INTEGER, unit_price REAL, total_price REAL)",
        f"CREATE TABLE IF NOT EXISTS expenses (id {pk}, date TEXT, category TEXT, amount REAL, note TEXT, added_by TEXT)",
        f"CREATE TABLE IF NOT EXISTS system_logs (id {pk}, timestamp TEXT, username TEXT, action TEXT, details TEXT)"
    ]
    for q in tables: run_query(q)

init_system()

# ==========================================
# 5. SMART CACHING (Performance Layer)
# ==========================================
@st.cache_data(ttl=60)
def get_dashboard_metrics():
    today = datetime.date.today().isoformat()
    
    # Sales
    sales = run_query(f"SELECT SUM(total_amount) as v FROM transactions WHERE date='{today}' AND type='SALE'", fetch=True)
    sales_val = sales[0]['v'] or 0
    
    # Expenses
    exps = run_query(f"SELECT SUM(amount) as v FROM expenses WHERE date='{today}'", fetch=True)
    exp_val = exps[0]['v'] or 0
    
    # Receivables (Market Debt)
    totals = run_query("SELECT SUM(total_amount) as s, SUM(paid_amount) as p FROM transactions", fetch=True)
    receivables = (totals[0]['s'] or 0) - (totals[0]['p'] or 0) if totals else 0
    
    return sales_val, exp_val, receivables

@st.cache_data(ttl=300)
def get_master_data():
    """Loads heavy lists into RAM for instant dropdowns."""
    prods = run_query("SELECT * FROM products ORDER BY name", fetch=True)
    custs = run_query("SELECT * FROM customers ORDER BY name", fetch=True)
    return prods, custs

def force_refresh():
    st.cache_data.clear()
    st.rerun()

def log_audit(action, detail):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user = st.session_state.get('username', 'system')
    run_query("INSERT INTO system_logs (timestamp, username, action, details) VALUES (?,?,?,?)", (ts, user, action, detail))

# ==========================================
# 6. PROFESSIONAL PDF ENGINE
# ==========================================
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 20)
        self.set_text_color(15, 23, 42)
        self.cell(0, 10, BUSINESS_INFO["name"], 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.set_text_color(100, 116, 139)
        self.cell(0, 5, BUSINESS_INFO["address"], 0, 1, 'C')
        self.cell(0, 5, f"Helpline: {BUSINESS_INFO['phone']}", 0, 1, 'C')
        self.ln(10); self.set_draw_color(200, 200, 200); self.line(10, 32, 200, 32); self.ln(5)

def generate_invoice_pdf(tx, items, cust):
    pdf = PDF()
    pdf.add_page()
    
    # Invoice Details
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(100, 10, "INVOICE", 0, 0)
    pdf.set_font('Arial', '', 10)
    pdf.cell(90, 10, f"No: {tx['invoice_id']}", 0, 1, 'R')
    
    # Customer Block
    pdf.set_fill_color(248, 250, 252)
    pdf.rect(10, 45, 190, 20, 'F')
    pdf.set_y(48)
    pdf.set_x(12)
    pdf.cell(100, 5, f"Bill To: {cust['name']} ({cust['phone']})", 0, 1)
    pdf.set_x(12)
    pdf.cell(100, 5, f"Date: {tx['date']}", 0, 1)
    pdf.ln(15)
    
    # Table Header
    pdf.set_fill_color(15, 23, 42)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(10, 8, "#", 1, 0, 'C', 1)
    pdf.cell(90, 8, "Item", 1, 0, 'L', 1)
    pdf.cell(30, 8, "Rate", 1, 0, 'R', 1)
    pdf.cell(20, 8, "Qty", 1, 0, 'C', 1)
    pdf.cell(40, 8, "Total", 1, 1, 'R', 1)
    pdf.ln(8)
    
    # Items
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Arial', '', 10)
    for idx, i in enumerate(items):
        name = i.get('product_name') or i.get('name')
        price = float(i.get('unit_price', i.get('price', 0)))
        qty = int(i.get('quantity', i.get('qty', 0)))
        total = float(i.get('total_price', i.get('total', 0)))
        
        pdf.cell(10, 8, str(idx+1), 1, 0, 'C')
        pdf.cell(90, 8, str(name)[:45], 1, 0, 'L')
        pdf.cell(30, 8, f"{price:,.0f}", 1, 0, 'R')
        pdf.cell(20, 8, str(qty), 1, 0, 'C')
        pdf.cell(40, 8, f"{total:,.0f}", 1, 1, 'R')
        pdf.ln(8)
    
    # Totals
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(150, 8, "Grand Total", 0, 0, 'R')
    pdf.cell(40, 8, f"Rs {tx['total_amount']:,.0f}", 0, 1, 'R')
    
    pdf.set_font('Arial', '', 10)
    pdf.cell(150, 8, "Paid Amount", 0, 0, 'R')
    pdf.cell(40, 8, f"Rs {float(tx.get('paid_amount', 0)):,.0f}", 0, 1, 'R')
    
    # Balance Highlighting
    due = float(tx.get('due_amount', 0))
    if due > 0:
        pdf.set_font('Arial', 'B', 11)
        pdf.set_text_color(220, 38, 38)
        pdf.cell(150, 10, "Balance Due", 0, 0, 'R')
        pdf.cell(40, 10, f"Rs {due:,.0f}", 0, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 7. APP MODULES
# ==========================================
def login_screen():
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    c1,c2,c3 = st.columns([1,2,1])
    with c2:
        with st.form("login_form"):
            st.markdown("<h2 style='text-align:center;'>🔐 KKG ERP</h2>", unsafe_allow_html=True)
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                if u in USERS and USERS[u]["pass"] == p:
                    st.session_state.logged_in = True
                    st.session_state.username = u
                    st.session_state.role = USERS[u]["role"]
                    log_audit("LOGIN", f"User {u} logged in")
                    st.rerun()
                else: st.error("Invalid Credentials")

def main():
    inject_css()
    
    if 'logged_in' not in st.session_state:
        login_screen()
        return

    # SIDEBAR
    st.sidebar.markdown(f"""
        <div style='text-align: center; padding: 20px 0; border-bottom: 1px solid #1e293b; margin-bottom: 20px;'>
            <div style='font-size: 3rem;'>🚜</div>
            <h2 style='color: white; margin: 0;'>KKG ERP</h2>
            <p style='color: #94a3b8; font-size: 0.8rem; margin-top:5px;'>User: {st.session_state.username.upper()}</p>
        </div>
    """, unsafe_allow_html=True)
    
    menu = ["Dashboard", "POS", "Inventory", "Customers", "Expenses", "Ledger"]
    if st.session_state.role == "staff":
        menu = ["POS", "Inventory", "Customers"]
        
    choice = st.sidebar.radio("Navigation", menu, label_visibility="collapsed")
    
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    # --- DASHBOARD ---
    if choice == "Dashboard":
        st.title("Executive Dashboard")
        sales, exps, receivables = get_dashboard_metrics()
        profit = sales - exps # Simplified Net Profit
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Today's Revenue", f"₹{sales:,.0f}")
        c2.metric("Today's Expenses", f"₹{exps:,.0f}")
        c3.metric("Net Profit (Est)", f"₹{profit:,.0f}", delta="Cash Flow")
        c4.metric("Market Debt", f"₹{receivables:,.0f}", delta_color="inverse")
        
        st.markdown("---")
        st.markdown("### 📉 Recent Activity")
        recent = run_query("SELECT date, invoice_id, total_amount FROM transactions ORDER BY created_at DESC LIMIT 5", fetch=True)
        if recent: st.dataframe(pd.DataFrame(recent), use_container_width=True)

    # --- POS (Billing) ---
    elif choice == "POS":
        st.title("🛒 Sales Terminal")
        prods, custs = get_master_data()
        
        if not prods: st.warning("Add Inventory First"); st.stop()
        
        c_map = {f"{c['name']} | {c['phone']}": c for c in custs}
        p_map = {f"{p['name']} (₹{p['price']:.0f})": p for p in prods}
        
        col1, col2 = st.columns([1.5, 1])
        with col1:
            st.markdown("##### Add Items")
            with st.form("add_cart"):
                sel_c = st.selectbox("Customer", list(c_map.keys()))
                sel_p = st.selectbox("Product", list(p_map.keys()))
                qty = st.number_input("Qty", 1, 1000)
                if st.form_submit_button("Add to Bill"):
                    if 'cart' not in st.session_state: st.session_state.cart = []
                    prod = p_map[sel_p]
                    if qty > prod['stock']:
                        st.error(f"Low Stock! Only {prod['stock']} available.")
                    else:
                        st.session_state.cart.append({**prod, 'qty': qty, 'total': qty*prod['price']})
                        st.success("Added")

        with col2:
            st.markdown("##### Current Bill")
            if 'cart' in st.session_state and st.session_state.cart:
                cart_df = pd.DataFrame(st.session_state.cart)
                st.dataframe(cart_df[['name', 'qty', 'total']], hide_index=True)
                
                total = cart_df['total'].sum()
                st.markdown(f"### Total: ₹{total:,.0f}")
                
                with st.form("pay"):
                    paid = st.number_input("Amount Received", 0.0)
                    mode = st.selectbox("Mode", ["Cash", "UPI", "Credit"])
                    if st.form_submit_button("✅ Finalize Sale"):
                        cust = c_map[sel_c]
                        inv_id = f"INV-{int(time.time())}"
                        due = total - paid
                        
                        run_query("INSERT INTO transactions (invoice_id, customer_phone, date, type, total_amount, paid_amount, due_amount, payment_mode) VALUES (?,?,?,?,?,?,?,?)",
                                  (inv_id, cust['phone'], str(datetime.date.today()), 'SALE', total, paid, due, mode))
                        
                        for i in st.session_state.cart:
                            run_query("INSERT INTO invoice_items (invoice_id, product_name, quantity, unit_price, total_price) VALUES (?,?,?,?,?)",
                                      (inv_id, i['name'], i['qty'], i['price'], i['total']))
                            run_query("UPDATE products SET stock = stock - ? WHERE id = ?", (i['qty'], i['id']))
                        
                        log_audit("SALE", f"Sold {inv_id} to {cust['name']}")
                        st.session_state.pdf = generate_invoice_pdf({'invoice_id': inv_id, 'date': str(datetime.date.today()), 'total_amount': total, 'paid_amount': paid, 'due_amount': due}, st.session_state.cart, cust)
                        st.session_state.cart = []
                        force_refresh()
                        st.rerun()
            
            if 'pdf' in st.session_state:
                st.download_button("Download Bill", st.session_state.pdf, "invoice.pdf", "application/pdf")

    # --- INVENTORY ---
    elif choice == "Inventory":
        st.title("📦 Inventory Management")
        
        with st.expander("Add New Product"):
            with st.form("new_p"):
                c1, c2, c3, c4 = st.columns(4)
                n = c1.text_input("Name")
                cat = c2.text_input("Category")
                sp = c3.number_input("Selling Price", 0.0)
                cp = c4.number_input("Cost Price", 0.0)
                stk = st.number_input("Stock", 0)
                if st.form_submit_button("Save Item"):
                    run_query("INSERT INTO products (name, category, price, cost_price, stock) VALUES (?,?,?,?,?)", (n, cat, sp, cp, stk))
                    force_refresh(); st.success("Saved"); st.rerun()
        
        prods, _ = get_master_data()
        df = pd.DataFrame(prods)
        if not df.empty:
            st.dataframe(df[['name', 'category', 'price', 'stock']], use_container_width=True)
            if st.session_state.role == "admin":
                d_id = st.number_input("ID to Delete", 0)
                if st.button("Delete Product", type="secondary") and d_id:
                    run_query("DELETE FROM products WHERE id=?", (d_id,))
                    log_audit("DELETE", f"Deleted Product ID {d_id}")
                    force_refresh(); st.rerun()

    # --- CUSTOMERS ---
    elif choice == "Customers":
        st.title("👥 Customer List")
        with st.expander("Register Customer"):
            with st.form("new_c"):
                n = st.text_input("Name")
                p = st.text_input("Phone")
                a = st.text_input("Address")
                if st.form_submit_button("Save"):
                    if run_query("INSERT INTO customers (phone, name, address, joined_date) VALUES (?,?,?,?)", (p, n, a, str(datetime.date.today()))):
                        force_refresh(); st.success("Saved"); st.rerun()
                    else: st.error("Exists")
        
        _, custs = get_master_data()
        st.dataframe(pd.DataFrame(custs), use_container_width=True)

    # --- EXPENSES ---
    elif choice == "Expenses":
        st.title("💸 Expenses & Overheads")
        with st.form("exp"):
            c1, c2 = st.columns(2)
            cat = c1.selectbox("Category", ["Rent", "Salary", "Tea", "Transport", "Other"])
            amt = c2.number_input("Amount", 1.0)
            note = st.text_input("Note")
            if st.form_submit_button("Record Expense"):
                run_query("INSERT INTO expenses (date, category, amount, note, added_by) VALUES (?,?,?,?,?)", 
                          (str(datetime.date.today()), cat, amt, note, st.session_state.username))
                st.success("Recorded")
                force_refresh()
        
        exps = run_query("SELECT * FROM expenses ORDER BY date DESC", fetch=True)
        if exps: st.dataframe(pd.DataFrame(exps), use_container_width=True)

    # --- LEDGER ---
    elif choice == "Ledger":
        st.title("📖 Customer Ledger")
        _, custs = get_master_data()
        if custs:
            c_map = {f"{c['name']} ({c['phone']})": c for c in custs}
            sel = st.selectbox("Select Customer", list(c_map.keys()))
            cust = c_map[sel]
            
            if st.button("Load History"):
                txs = run_query(f"SELECT * FROM transactions WHERE customer_phone='{cust['phone']}' ORDER BY created_at DESC", fetch=True)
                if txs:
                    st.dataframe(pd.DataFrame(txs)[['date', 'invoice_id', 'total_amount', 'paid_amount', 'due_amount']], use_container_width=True)
                    
                    st.markdown("### Reprint")
                    sale_txs = [t for t in txs if t['type'] == 'SALE']
                    if sale_txs:
                        inv_ids = [t['invoice_id'] for t in sale_txs]
                        sel_inv = st.selectbox("Select Invoice", inv_ids)
                        if st.button("Generate Copy"):
                            inv_data = next(t for t in sale_txs if t['invoice_id'] == sel_inv)
                            items = run_query(f"SELECT * FROM invoice_items WHERE invoice_id='{sel_inv}'", fetch=True)
                            pdf = generate_invoice_pdf(inv_data, items, cust)
                            st.download_button("Download", pdf, f"{sel_inv}.pdf", "application/pdf")
                else: st.info("No history")

if __name__ == "__main__":
    init_system()
    main()
