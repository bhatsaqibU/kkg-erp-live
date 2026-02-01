import streamlit as st
import pandas as pd
import datetime
import time
from fpdf import FPDF
import sqlite3
import os
import hashlib
import random
import base64
import io

# ==========================================
# PART 1: ENTERPRISE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="KKG Enterprise OS",
    page_icon="🚜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Business Metadata - The Single Source of Truth
META = {
    "brand": "KISAN KHIDMAT GHAR",
    "branch": "Chakoora HQ",
    "address": "Main Market, Chakoora, Pulwama, J&K - 192301",
    "phone": "+91 9622749245",
    "email": "support@kkg-agri.com",
    "gst": "01AAAAA0000A1Z5",
    "currency": "₹",
    "version": "v32.0 (Industrial Standard)"
}

# Role-Based Access Control (RBAC) Map
USERS = {
    "admin": {
        "hash": "kkg@123", 
        "role": "CEO", 
        "name": "Owner",
        "permissions": ["all"]
    },
    "staff": {
        "hash": "staff1", 
        "role": "Manager", 
        "name": "Counter Staff",
        "permissions": ["pos", "inventory_read", "customers_read"]
    }
}

DB_FILE = "kkg_master.sqlite"

# ==========================================
# PART 2: THE UI ENGINE (GLASSMORPHISM)
# ==========================================
def inject_enterprise_css():
    st.markdown("""
        <style>
        /* CORE FONTS & THEME */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        
        :root {
            --primary: #2563eb;
            --primary-dark: #1e40af;
            --secondary: #0f172a;
            --bg-light: #f8fafc;
            --text-dark: #0f172a;
            --glass-bg: rgba(255, 255, 255, 0.95);
            --glass-border: 1px solid rgba(255, 255, 255, 0.2);
            --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
        }

        .stApp {
            background-color: var(--bg-light);
            font-family: 'Inter', sans-serif;
            color: var(--text-dark);
        }
        
        /* PREMIUM SIDEBAR */
        [data-testid="stSidebar"] {
            background-color: var(--secondary);
            border-right: 1px solid #1e293b;
        }
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] p, 
        [data-testid="stSidebar"] span, [data-testid="stSidebar"] label, .stRadio div {
            color: #f1f5f9 !important;
        }
        
        /* METRIC CARDS (Glass Effect) */
        div[data-testid="stMetric"] {
            background: var(--glass-bg);
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 24px;
            box-shadow: var(--shadow-md);
            transition: all 0.3s ease;
        }
        div[data-testid="stMetric"]:hover {
            transform: translateY(-5px);
            box-shadow: var(--shadow-lg);
            border-color: var(--primary);
        }
        [data-testid="stMetricLabel"] {
            font-size: 0.85rem;
            font-weight: 600;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        [data-testid="stMetricValue"] {
            font-size: 2rem;
            font-weight: 800;
            color: var(--text-dark);
        }
        
        /* INDUSTRIAL BUTTONS */
        .stButton button {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            color: white !important;
            font-weight: 600;
            border-radius: 8px;
            border: none;
            padding: 0.75rem 1rem;
            width: 100%;
            transition: all 0.2s ease;
            box-shadow: var(--shadow-sm);
        }
        .stButton button:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-md);
        }
        .stButton button:active {
            transform: scale(0.98);
        }
        
        /* DESTRUCTIVE ACTIONS */
        button[kind="secondary"] {
            background: #fff1f2 !important;
            color: #be123c !important;
            border: 1px solid #fda4af !important;
        }
        button[kind="secondary"]:hover {
            background: #ffe4e6 !important;
            border-color: #f43f5e !important;
        }
        
        /* DATA TABLES */
        [data-testid="stDataFrame"] {
            background: white;
            border-radius: 12px;
            border: 1px solid #e2e8f0;
            padding: 16px;
            box-shadow: var(--shadow-sm);
        }
        
        /* INPUT FIELDS */
        .stTextInput input, .stNumberInput input, .stSelectbox select, .stDateInput input {
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            padding: 10px;
            font-size: 1rem;
            transition: border-color 0.2s;
        }
        .stTextInput input:focus, .stNumberInput input:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
        }
        
        /* ALERTS & STATUS */
        .kkg-status-box {
            padding: 16px;
            border-radius: 8px;
            margin-bottom: 16px;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .status-success { background: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
        .status-warning { background: #ffedd5; color: #9a3412; border: 1px solid #fed7aa; }
        .status-error { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# PART 3: THE SELF-HEALING DATABASE MANAGER
# ==========================================
@st.cache_resource
def get_db_connection():
    """
    Establishes a resilient connection to either Cloud (Postgres) or Local (SQLite).
    This function persists across re-runs to eliminate connection latency.
    """
    # 1. Attempt Cloud Connection
    if hasattr(st, "secrets") and "postgres" in st.secrets:
        try:
            import psycopg2
            # sslmode='require' is mandatory for Supabase
            return "POSTGRES", psycopg2.connect(st.secrets["postgres"]["url"], sslmode='require')
        except Exception as e:
            # Silent fallback allows offline mode to work if cloud fails
            print(f"Cloud DB Error: {e}")
            pass
    
    # 2. Local Fallback (SQLite)
    # check_same_thread=False is crucial for Streamlit's threading model
    return "SQLITE", sqlite3.connect(DB_FILE, check_same_thread=False)

class DatabaseEngine:
    def __init__(self):
        self.db_type, self.conn = get_db_connection()

    def _get_cursor(self):
        # Refresh connection if dropped (Self-Healing)
        if self.db_type == "POSTGRES" and self.conn.closed:
            st.cache_resource.clear()
            self.db_type, self.conn = get_db_connection()
        
        if self.db_type == "SQLITE":
            self.conn.row_factory = sqlite3.Row
            return self.conn.cursor()
        else:
            return self.conn.cursor()

    def run(self, query, params=None, fetch=False):
        """
        The central executive for all data operations.
        Wraps every query in a try-except block to prevent app crashes.
        """
        if not self.conn: return [] if fetch else False

        # Postgres uses %s placeholder, SQLite uses ?
        if self.db_type == "POSTGRES":
            query = query.replace('?', '%s')

        try:
            cur = self._get_cursor()
            cur.execute(query, params or ())
            
            if fetch:
                # Standardize output as List of Dictionaries
                if self.db_type == "SQLITE":
                    res = [dict(row) for row in cur.fetchall()]
                else:
                    cols = [desc[0] for desc in cur.description]
                    res = [dict(zip(cols, row)) for row in cur.fetchall()]
                cur.close()
                return res
            else:
                self.conn.commit()
                cur.close()
                return True

        except Exception as e:
            # Industrial Error Handling
            if self.db_type == "POSTGRES":
                self.conn.rollback() # Unfreeze the database
            
            # Log error securely (don't show full trace to user)
            print(f"CRITICAL DB ERROR: {str(e)} | QUERY: {query}")
            return [] if fetch else False

# Initialize the Engine
db = DatabaseEngine()

# ==========================================
# PART 4: DATA MODELS & INITIALIZATION
# ==========================================
def init_data_structure():
    """
    Ensures the database schema exists.
    Runs only if tables are missing to save startup time.
    """
    pk = "SERIAL PRIMARY KEY" if db.db_type == "POSTGRES" else "INTEGER PRIMARY KEY AUTOINCREMENT"
    
    schema = [
        # INVENTORY: Tracks goods, pricing, and stock levels
        f"""CREATE TABLE IF NOT EXISTS products (
            id {pk}, 
            name TEXT NOT NULL, 
            category TEXT, 
            price REAL NOT NULL, 
            cost_price REAL DEFAULT 0, 
            stock INTEGER DEFAULT 0, 
            min_stock INTEGER DEFAULT 5,
            supplier TEXT
        )""",
        
        # CRM: Customer data and credit tracking
        f"""CREATE TABLE IF NOT EXISTS customers (
            phone TEXT PRIMARY KEY, 
            name TEXT NOT NULL, 
            address TEXT, 
            joined_date TEXT, 
            credit_limit REAL DEFAULT 50000, 
            risk_score TEXT DEFAULT 'LOW'
        )""",
        
        # TRANSACTIONS: The financial ledger
        f"""CREATE TABLE IF NOT EXISTS transactions (
            invoice_id TEXT PRIMARY KEY, 
            customer_phone TEXT, 
            date TEXT, 
            type TEXT, 
            total_amount REAL, 
            paid_amount REAL, 
            due_amount REAL, 
            payment_mode TEXT, 
            notes TEXT, 
            created_by TEXT, 
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        
        # INVOICE ITEMS: Granular detail of every sale
        f"""CREATE TABLE IF NOT EXISTS invoice_items (
            id {pk}, 
            invoice_id TEXT, 
            product_name TEXT, 
            quantity INTEGER, 
            unit_price REAL, 
            cost_price REAL, 
            total_price REAL
        )""",
        
        # EXPENSES: Operational costs
        f"""CREATE TABLE IF NOT EXISTS expenses (
            id {pk}, 
            date TEXT, 
            category TEXT, 
            amount REAL, 
            note TEXT, 
            added_by TEXT
        )""",
        
        # AUDIT LOGS: Security tracking
        f"""CREATE TABLE IF NOT EXISTS audit_logs (
            id {pk}, 
            timestamp TEXT, 
            username TEXT, 
            action TEXT, 
            details TEXT
        )"""
    ]
    
    for sql in schema:
        db.run(sql)

init_data_structure()

# ==========================================
# PART 5: BUSINESS LOGIC LAYER
# ==========================================
def log_security_event(action, details):
    """Writes to the audit log."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user = st.session_state.get('username', 'system')
    db.run("INSERT INTO audit_logs (timestamp, username, action, details) VALUES (?,?,?,?)", 
           (ts, user, action, details))

# --- LIVE FINANCIALS (CRASH-PROOF) ---
def get_live_financials():
    """
    Fetches financial health metrics in real-time.
    Uses COALESCE to ensure NO NULL values return (Preventing the '0' bug).
    """
    today = datetime.date.today().isoformat()
    
    # 1. Total Revenue Today (Using COALESCE to fix 'None' issues)
    sales_res = db.run(f"SELECT COALESCE(SUM(total_amount), 0) as v FROM transactions WHERE date=? AND type='SALE'", (today,), fetch=True)
    revenue = sales_res[0]['v'] if sales_res else 0
    
    # 2. Total Expenses Today
    exp_res = db.run(f"SELECT COALESCE(SUM(amount), 0) as v FROM expenses WHERE date=?", (today,), fetch=True)
    expenses = exp_res[0]['v'] if exp_res else 0
    
    # 3. Total Market Debt (Receivables)
    debt_res_s = db.run("SELECT COALESCE(SUM(total_amount), 0) as v FROM transactions WHERE type='SALE'", fetch=True)
    debt_res_p = db.run("SELECT COALESCE(SUM(paid_amount), 0) as v FROM transactions", fetch=True)
    
    total_sales = debt_res_s[0]['v'] if debt_res_s else 0
    total_paid = debt_res_p[0]['v'] if debt_res_p else 0
    debt = total_sales - total_paid
    
    net_profit = revenue - expenses
    
    return revenue, expenses, debt, net_profit

# --- DATA CACHING (SPEED LAYER) ---
@st.cache_data(ttl=600)
def get_master_data():
    """
    Loads Products and Customers into RAM.
    TTL=600 means it refreshes every 10 minutes automatically.
    """
    prods = db.run("SELECT * FROM products ORDER BY name", fetch=True)
    custs = db.run("SELECT * FROM customers ORDER BY name", fetch=True)
    return prods, custs

def force_system_refresh():
    """Clears cache to force a re-fetch from DB."""
    st.cache_data.clear()
    st.rerun()

# ==========================================
# PART 6: PROFESSIONAL DOCUMENT ENGINE
# ==========================================
class PDFGenerator(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 22)
        self.set_text_color(15, 23, 42) # Dark Navy
        self.cell(0, 10, META["brand"], 0, 1, 'C')
        
        self.set_font('Arial', '', 10)
        self.set_text_color(100, 116, 139) # Slate Gray
        self.cell(0, 5, META["address"], 0, 1, 'C')
        self.cell(0, 5, f"Helpline: {META['phone']} | GST: {META['gst']}", 0, 1, 'C')
        
        self.ln(5)
        self.set_draw_color(203, 213, 225) # Slate-300
        self.set_line_width(0.5)
        self.line(10, 35, 200, 35)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(148, 163, 184)
        self.cell(0, 10, 'Computer Generated Invoice | Valid without signature', 0, 0, 'C')

def create_invoice(tx_data, cart_items, customer_data):
    """Generates a PDF invoice byte stream."""
    pdf = PDFGenerator()
    pdf.add_page()
    
    # 1. Invoice Meta
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(15, 23, 42)
    title = "TAX INVOICE" if tx_data['type'] == 'SALE' else "RETURN RECEIPT"
    pdf.cell(100, 10, title, 0, 0)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(90, 10, f"Inv #: {tx_data['invoice_id']}", 0, 1, 'R')
    
    # 2. Customer & Date Block
    pdf.set_fill_color(241, 245, 249) # Slate-100
    pdf.rect(10, 48, 190, 22, 'F')
    
    pdf.set_y(50); pdf.set_x(12)
    pdf.set_font('Arial', 'B', 10); pdf.set_text_color(15, 23, 42)
    pdf.cell(20, 5, "Bill To:", 0, 0)
    pdf.set_font('Arial', '', 10)
    pdf.cell(100, 5, f"{customer_data['name']} ({customer_data['phone']})", 0, 1)
    
    pdf.set_x(12)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(20, 5, "Address:", 0, 0)
    pdf.set_font('Arial', '', 10)
    pdf.cell(100, 5, f"{customer_data['address']}", 0, 1)
    
    pdf.set_y(50); pdf.set_x(140)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(20, 5, "Date:", 0, 0)
    pdf.set_font('Arial', '', 10)
    pdf.cell(30, 5, f"{tx_data['date']}", 0, 1)
    
    pdf.ln(20)
    
    # 3. Table Header
    pdf.set_fill_color(15, 23, 42) # Dark Header
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(10, 10, "#", 1, 0, 'C', 1)
    pdf.cell(90, 10, "Product Description", 1, 0, 'L', 1)
    pdf.cell(30, 10, "Rate", 1, 0, 'R', 1)
    pdf.cell(20, 10, "Qty", 1, 0, 'C', 1)
    pdf.cell(40, 10, "Total", 1, 1, 'R', 1)
    pdf.ln(10)
    
    # 4. Table Rows
    pdf.set_text_color(15, 23, 42)
    pdf.set_font('Arial', '', 10)
    
    for idx, item in enumerate(cart_items):
        name = item.get('product_name') or item.get('name')
        price = float(item.get('unit_price') or item.get('price'))
        qty = int(item.get('quantity') or item.get('qty'))
        total = float(item.get('total_price') or item.get('total'))
        
        pdf.cell(10, 10, str(idx+1), 1, 0, 'C')
        pdf.cell(90, 10, str(name)[:45], 1, 0, 'L')
        pdf.cell(30, 10, f"{price:,.0f}", 1, 0, 'R')
        pdf.cell(20, 10, str(qty), 1, 0, 'C')
        pdf.cell(40, 10, f"{total:,.0f}", 1, 1, 'R')
        pdf.ln(10)
    
    # 5. Financial Summary
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 11)
    
    pdf.cell(150, 10, "Grand Total", 0, 0, 'R')
    pdf.cell(40, 10, f"Rs {tx_data['total_amount']:,.0f}", 0, 1, 'R')
    
    pdf.cell(150, 8, "Amount Paid", 0, 0, 'R')
    pdf.set_text_color(22, 163, 74) # Green
    pdf.cell(40, 8, f"Rs {float(tx_data.get('paid_amount', 0)):,.0f}", 0, 1, 'R')
    
    # Dynamic Due Color
    due = float(tx_data.get('due_amount', 0))
    if due > 0:
        pdf.set_text_color(220, 38, 38) # Red
    else:
        pdf.set_text_color(15, 23, 42)
        
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(150, 10, "Balance Pending", 0, 0, 'R')
    pdf.cell(40, 10, f"Rs {due:,.0f}", 0, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# PART 7: AUTHENTICATION MODULE
# ==========================================
def render_login():
    inject_enterprise_css()
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    
    with c2:
        st.markdown(f"""
        <div style="background:white; padding:40px; border-radius:16px; box-shadow:0 20px 25px -5px rgba(0,0,0,0.1); border:1px solid #e2e8f0; text-align:center;">
            <h1 style="color:#0f172a; font-size:2rem; margin-bottom:10px;">🚜 {META['brand']}</h1>
            <p style="color:#64748b;">Enterprise Business OS • Secure Access</p>
        </div>
        <br>
        """, unsafe_allow_html=True)
        
        with st.form("auth_form"):
            u = st.text_input("Username", placeholder="Enter ID")
            p = st.text_input("Password", type="password", placeholder="Enter Key")
            if st.form_submit_button("Authenticate"):
                if u in USERS and USERS[u]["hash"] == p:
                    st.session_state.logged_in = True
                    st.session_state.user = u
                    st.session_state.role = USERS[u]["role"]
                    log_security_event("LOGIN", f"User {u} accessed system")
                    st.rerun()
                else:
                    st.error("❌ Access Denied: Invalid Credentials")

# ==========================================
# PART 8: MAIN APPLICATION LOGIC
# ==========================================
def main():
    inject_enterprise_css()
    
    if 'logged_in' not in st.session_state:
        render_login()
        return

    # --- SIDEBAR NAV ---
    st.sidebar.markdown(f"""
        <div style='text-align: center; padding: 20px 0; margin-bottom: 20px;'>
            <div style='font-size: 3rem;'>🚜</div>
            <h2 style='color: white; margin: 0;'>KKG</h2>
            <p style='color: #94a3b8; font-size: 0.8rem;'>{META['version']}</p>
            <div style='background:#1e293b; padding:8px; border-radius:6px; margin-top:15px;'>
                <small style='color:#38bdf8; font-weight:bold;'>👤 {st.session_state.user.upper()}</small>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Permission-Based Menu
    menu = ["Dashboard", "POS Terminal", "Inventory", "Customers", "Expenses", "Ledger", "Reports"]
    if st.session_state.role == "Manager":
        menu = ["POS Terminal", "Inventory", "Customers"]
        
    choice = st.sidebar.radio("Main Menu", menu, label_visibility="collapsed")
    st.sidebar.markdown("---")
    
    if st.sidebar.button("Log Out"):
        log_security_event("LOGOUT", f"User {st.session_state.user} signed out")
        st.session_state.clear()
        st.rerun()

    # ---------------------------------------------------------
    # MODULE: EXECUTIVE DASHBOARD
    # ---------------------------------------------------------
    if choice == "Dashboard":
        st.title("🚀 Business Command Center")
        st.caption(f"Real-time overview for {datetime.date.today().strftime('%A, %d %B %Y')}")
        
        # Real-time Metrics (No Cache to prevent 'Zero' bug)
        rev, exp, debt, profit = get_live_financials()
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Revenue Today", f"₹{rev:,.0f}", delta="Gross Sales")
        c2.metric("Expenses", f"₹{exp:,.0f}", delta="Operational")
        c3.metric("Net Profit", f"₹{profit:,.0f}", delta="Real Margin")
        c4.metric("Market Debt", f"₹{debt:,.0f}", delta="Receivables", delta_color="inverse")
        
        st.markdown("---")
        
        # Visual Analytics
        g1, g2 = st.columns([2, 1])
        with g1:
            st.subheader("📉 Sales Velocity (Last 14 Days)")
            trend = db.run("SELECT date, SUM(total_amount) as sales FROM transactions WHERE type='SALE' GROUP BY date ORDER BY date DESC LIMIT 14", fetch=True)
            if trend:
                df = pd.DataFrame(trend)
                st.line_chart(df.set_index('date'), height=300)
            else:
                st.info("Insufficient data for trend analysis.")
                
        with g2:
            st.subheader("⚠️ Stock Alerts")
            low_stock = db.run("SELECT name, stock FROM products WHERE stock < min_stock LIMIT 5", fetch=True)
            if low_stock:
                st.dataframe(pd.DataFrame(low_stock), use_container_width=True)
            else:
                st.success("All stock levels healthy.")

    # ---------------------------------------------------------
    # MODULE: POS TERMINAL (Zero Latency)
    # ---------------------------------------------------------
    elif choice == "POS Terminal":
        st.title("🛒 Sales Terminal")
        
        # Load Cached Master Data (Instant Dropdowns)
        prods, custs = get_master_data()
        
        if not prods or not custs:
            st.warning("⚠️ System Initialization Required: Please add Inventory and Customers.")
            st.stop()
            
        # Hash Maps for O(1) Lookup
        c_map = {f"{c['name']} | {c['phone']}": c for c in custs}
        p_map = {f"{p['name']} (₹{p['price']:.0f})": p for p in prods}
        
        col_form, col_cart = st.columns([1.2, 1])
        
        # Left: Item Selection
        with col_form:
            st.markdown("##### Item Entry")
            with st.container():
                # Form prevents reload lag
                with st.form("pos_entry"):
                    c_sel = st.selectbox("Select Customer", list(c_map.keys()))
                    p_sel = st.selectbox("Search Product", list(p_map.keys()))
                    qty = st.number_input("Quantity", min_value=1, value=1)
                    
                    add_btn = st.form_submit_button("Add to Cart ➕")
                    
                    if add_btn:
                        if 'cart' not in st.session_state: st.session_state.cart = []
                        prod = p_map[p_sel]
                        
                        # Stock Validation Logic
                        in_cart = sum(item['qty'] for item in st.session_state.cart if item['id'] == prod['id'])
                        if (in_cart + qty) > prod['stock']:
                            st.error(f"❌ Stock Error! Only {prod['stock']} units available.")
                        else:
                            st.session_state.cart.append({
                                **prod, 
                                'qty': qty, 
                                'total': qty * prod['price']
                            })
                            st.success(f"Added {prod['name']}")

        # Right: Cart & Checkout
        with col_cart:
            st.markdown("##### Current Bill")
            if 'cart' in st.session_state and st.session_state.cart:
                df = pd.DataFrame(st.session_state.cart)
                st.dataframe(df[['name', 'price', 'qty', 'total']], hide_index=True, use_container_width=True)
                
                # Dynamic Totals
                total = df['total'].sum()
                st.markdown(f"""
                <div style="background:#dbeafe; padding:15px; border-radius:10px; display:flex; justify-content:space-between; align-items:center; border:1px solid #bfdbfe;">
                    <span style="color:#1e40af; font-weight:600;">Net Payable</span>
                    <span style="color:#1e3a8a; font-size:24px; font-weight:800;">₹{total:,.0f}</span>
                </div>
                """, unsafe_allow_html=True)
                
                st.write("")
                
                # Checkout
                with st.form("checkout"):
                    paid = st.number_input("Amount Received", min_value=0.0, value=0.0)
                    mode = st.selectbox("Payment Mode", ["Cash", "UPI", "Credit/Udhaari"])
                    
                    if st.form_submit_button("✅ Finalize Sale"):
                        cust = c_map[c_sel]
                        inv_id = f"INV-{int(time.time())}"
                        due = total - paid
                        
                        # 1. Master Transaction
                        db.run("INSERT INTO transactions (invoice_id, customer_phone, date, type, total_amount, paid_amount, due_amount, payment_mode, created_by) VALUES (?,?,?,?,?,?,?,?,?)",
                               (inv_id, cust['phone'], str(datetime.date.today()), 'SALE', total, paid, due, mode, st.session_state.user))
                        
                        # 2. Line Items & Stock Deduction
                        for i in st.session_state.cart:
                            db.run("INSERT INTO invoice_items (invoice_id, product_name, quantity, unit_price, cost_price, total_price) VALUES (?,?,?,?,?,?)",
                                   (inv_id, i['name'], i['qty'], i['price'], i.get('cost_price', 0), i['total']))
                            db.run("UPDATE products SET stock = stock - ? WHERE id = ?", (i['qty'], i['id']))
                        
                        # 3. Log
                        log_security_event("SALE", f"Invoice {inv_id} created for {cust['name']}")
                        
                        # 4. Generate PDF
                        tx_data = {'invoice_id': inv_id, 'date': str(datetime.date.today()), 'total_amount': total, 'paid_amount': paid, 'due_amount': due, 'type': 'SALE'}
                        st.session_state.pdf = create_invoice(tx_data, st.session_state.cart, cust)
                        
                        # 5. Clear
                        st.session_state.cart = []
                        force_system_refresh()
                        st.rerun()
            
            if 'pdf' in st.session_state:
                st.success("Transaction Saved Successfully!")
                st.download_button("🖨️ Download Invoice PDF", st.session_state.pdf, "invoice.pdf", "application/pdf")
                if st.button("Start New Sale"):
                    del st.session_state.pdf
                    st.rerun()

    # --- 3. INVENTORY MANAGEMENT ---
    elif choice == "Inventory":
        st.title("📦 Inventory Control")
        
        with st.expander("➕ Add New Product"):
            with st.form("new_prod"):
                c1, c2, c3, c4 = st.columns(4)
                n = c1.text_input("Product Name")
                cat = c2.text_input("Category")
                sp = c3.number_input("Selling Price (₹)", 0.0)
                cp = c4.number_input("Cost Price (₹)", 0.0)
                stk = st.number_input("Initial Stock", 0)
                
                if st.form_submit_button("Save to Inventory"):
                    db.run("INSERT INTO products (name, category, price, cost_price, stock) VALUES (?,?,?,?,?)", (n, cat, sp, cp, stk))
                    force_system_refresh()
                    st.success("Product Added")
        
        prods, _ = get_master_data()
        
        # INDUSTRIAL FIX FOR KEYERROR CRASH
        if prods:
            df = pd.DataFrame(prods)
            # Ensure columns exist before displaying
            if not df.empty:
                st.dataframe(df[['id', 'name', 'category', 'price', 'cost_price', 'stock']], use_container_width=True)
                
                if st.session_state.role == "CEO":
                    with st.expander("danger Zone"):
                        d_id = st.number_input("Enter ID to Delete", 0)
                        if st.button("Delete Product", type="secondary") and d_id:
                            db.run("DELETE FROM products WHERE id=?", (d_id,))
                            log_security_event("DELETE", f"Product ID {d_id} removed")
                            force_system_refresh()
                            st.rerun()
        else:
            st.info("Inventory is empty. Add products to see the table.")

    # --- 4. CUSTOMER MANAGEMENT ---
    elif choice == "Customers":
        st.title("👥 Customer Database")
        
        with st.expander("➕ Register Customer"):
            with st.form("new_cust"):
                n = st.text_input("Full Name")
                p = st.text_input("Phone Number")
                a = st.text_input("Address")
                lim = st.number_input("Credit Limit", 50000)
                
                if st.form_submit_button("Save Customer"):
                    if db.run("INSERT INTO customers (phone, name, address, joined_date, credit_limit) VALUES (?,?,?,?,?)", (p, n, a, str(datetime.date.today()), lim)):
                        force_system_refresh()
                        st.success("Registered")
                    else: st.error("Phone number already exists!")
        
        _, custs = get_master_data()
        if custs: st.dataframe(pd.DataFrame(custs), use_container_width=True)

    # --- 5. LEDGER & HISTORY ---
    elif choice == "Ledger":
        st.title("📖 Customer Ledger")
        
        _, custs = get_master_data()
        if custs:
            c_map = {f"{c['name']} ({c['phone']})": c for c in custs}
            sel = st.selectbox("Select Customer", list(c_map.keys()))
            cust = c_map[sel]
            
            c1, c2 = st.columns(2)
            d1 = c1.date_input("From Date", datetime.date.today() - datetime.timedelta(days=365))
            d2 = c2.date_input("To Date", datetime.date.today())
            
            if st.button("Load Statement"):
                txs = db.run(f"SELECT * FROM transactions WHERE customer_phone='{cust['phone']}' AND date BETWEEN '{d1}' AND '{d2}' ORDER BY created_at DESC", fetch=True)
                if txs:
                    st.dataframe(pd.DataFrame(txs)[['date', 'invoice_id', 'type', 'total_amount', 'paid_amount', 'due_amount']], use_container_width=True)
                    
                    st.markdown("### 🖨️ Reprint Bill")
                    sale_txs = [t for t in txs if t['type'] == 'SALE']
                    if sale_txs:
                        inv_ids = [t['invoice_id'] for t in sale_txs]
                        sel_inv = st.selectbox("Select Invoice ID", inv_ids)
                        if st.button("Generate Copy"):
                            inv_data = next(t for t in sale_txs if t['invoice_id'] == sel_inv)
                            items = db.run(f"SELECT * FROM invoice_items WHERE invoice_id='{sel_inv}'", fetch=True)
                            pdf = create_invoice(inv_data, items, cust)
                            st.download_button("Download PDF", pdf, f"{sel_inv}.pdf", "application/pdf")
                else: st.info("No transaction history found.")

    # --- 6. EXPENSES ---
    elif choice == "Expenses":
        st.title("💸 Operational Expenses")
        with st.form("new_exp"):
            c1, c2 = st.columns(2)
            cat = c1.selectbox("Category", ["Rent", "Salary", "Tea/Refreshment", "Transport", "Electricity", "Other"])
            amt = c2.number_input("Amount", 1.0)
            note = st.text_input("Note")
            if st.form_submit_button("Record Expense"):
                db.run("INSERT INTO expenses (date, category, amount, note, added_by) VALUES (?,?,?,?,?)", 
                       (str(datetime.date.today()), cat, amt, note, st.session_state.user))
                st.success("Recorded")
                force_system_refresh()
        
        exps = db.run("SELECT * FROM expenses ORDER BY date DESC", fetch=True)
        if exps: st.dataframe(pd.DataFrame(exps), use_container_width=True)

if __name__ == "__main__":
    main()
