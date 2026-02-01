
import streamlit as st
import pandas as pd
import datetime
import time
from fpdf import FPDF
import sqlite3
import os
import hashlib

# ==========================================
# 1. SYSTEM CONFIGURATION & CONSTANTS
# ==========================================
st.set_page_config(
    page_title="KKG Enterprise ERP",
    page_icon="🚜",
    layout="wide",
    initial_sidebar_state="expanded"
)

BUSINESS_INFO = {
    "name": "KISAN KHIDMAT GHAR",
    "address": "Chakoora, Pulwama, J&K",
    "phone": "+91 9622749245",
    "email": "contact@kkg.com",
    "currency": "₹"
}

# Hardcoded Admin for Phase 1 (To be moved to DB in Phase 3)
USERS = {
    "admin": "kkg@123",  # Owner
    "staff": "staff1"    # Counter Staff
}

# ==========================================
# 2. IMMERSIVE UI ENGINE (Custom CSS)
# ==========================================
def inject_custom_css():
    st.markdown("""
        <style>
        /* IMPORT FONTS */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        /* GLOBAL RESET */
        .stApp {
            background-color: #f1f5f9;
            font-family: 'Inter', sans-serif;
        }
        
        /* SIDEBAR STYLING */
        [data-testid="stSidebar"] {
            background-color: #0f172a;
            border-right: 1px solid #1e293b;
        }
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
            color: #f8fafc !important;
        }
        
        /* LOGIN CONTAINER */
        .login-container {
            max-width: 400px;
            margin: 100px auto;
            padding: 40px;
            background: white;
            border-radius: 16px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
            text-align: center;
        }
        
        /* METRIC CARDS (Glassmorphism) */
        div[data-testid="stMetric"] {
            background-color: white;
            border: 1px solid #e2e8f0;
            padding: 24px;
            border-radius: 16px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            transition: transform 0.2s;
        }
        div[data-testid="stMetric"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        }
        [data-testid="stMetricLabel"] {
            color: #64748b;
            font-size: 0.875rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        [data-testid="stMetricValue"] {
            color: #0f172a;
            font-size: 1.875rem;
            font-weight: 800;
        }
        
        /* CUSTOM BUTTONS */
        .stButton button {
            background: linear-gradient(to bottom, #2563eb, #1d4ed8);
            color: white !important;
            font-weight: 600;
            padding: 0.6rem 1.2rem;
            border-radius: 8px;
            border: none;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            width: 100%;
        }
        .stButton button:hover {
            background: linear-gradient(to bottom, #1d4ed8, #1e40af);
            box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.3);
        }
        
        /* SECONDARY BUTTON (Danger/Delete) */
        button[kind="secondary"] {
            background: white !important;
            color: #ef4444 !important;
            border: 1px solid #fecaca !important;
        }
        
        /* DATA TABLES */
        [data-testid="stDataFrame"] {
            background: white;
            padding: 1rem;
            border-radius: 12px;
            border: 1px solid #e2e8f0;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
        }
        
        /* INPUT FIELDS */
        .stTextInput input, .stNumberInput input, .stSelectbox select, .stDateInput input {
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            padding: 0.5rem;
            color: #1e293b;
        }
        .stTextInput input:focus, .stNumberInput input:focus {
            border-color: #3b82f6;
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
        }
        
        /* HEADERS */
        h1, h2, h3 {
            color: #0f172a;
            font-weight: 700;
            letter-spacing: -0.025em;
        }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 3. ROBUST DATABASE ENGINE (Hybrid)
# ==========================================
@st.cache_resource
def get_db_connection():
    """
    Establishes a persistent connection to the database.
    Supports both SQLite (Local) and Postgres (Cloud) seamlessly.
    """
    # 1. Try Cloud (Postgres)
    if hasattr(st, "secrets") and "postgres" in st.secrets:
        try:
            import psycopg2
            conn = psycopg2.connect(st.secrets["postgres"]["url"])
            return "POSTGRES", conn
        except Exception as e:
            return "ERROR", None
    
    # 2. Fallback to Local (SQLite)
    try:
        conn = sqlite3.connect("kkg_database.sqlite", check_same_thread=False)
        return "SQLITE", conn
    except Exception as e:
        return "ERROR", None

def run_query(query, params=None, fetch=False):
    """
    Executes a query with automatic error recovery and transaction management.
    """
    db_type, conn = get_db_connection()
    
    if not conn:
        return [] if fetch else False

    # Postgres Parameter Substitution Adjustment
    if db_type == "POSTGRES":
        query = query.replace('?', '%s')
        # Auto-reconnect if connection dropped
        if conn.closed:
            st.cache_resource.clear()
            db_type, conn = get_db_connection()

    try:
        cur = conn.cursor()
        
        # Enable dictionary access for SQLite rows
        if db_type == "SQLITE":
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
        
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
        # Emergency Rollback for Postgres
        if db_type == "POSTGRES":
            conn.rollback()
        # Log error but don't crash UI if possible
        # st.error(f"Database Error: {e}") 
        return [] if fetch else False

# ==========================================
# 4. SYSTEM INITIALIZATION & MIGRATION
# ==========================================
def init_system():
    """Creates tables if they don't exist."""
    db_type, _ = get_db_connection()
    if not db_type or db_type == "ERROR": return

    pk = "SERIAL PRIMARY KEY" if db_type == "POSTGRES" else "INTEGER PRIMARY KEY AUTOINCREMENT"
    
    # Define Schema
    tables = [
        # Products: Now includes Cost Price for Profit Calculation
        f"CREATE TABLE IF NOT EXISTS products (id {pk}, name TEXT, category TEXT, price REAL, cost_price REAL DEFAULT 0, stock INTEGER, low_stock_threshold INTEGER DEFAULT 5)",
        
        # Customers: Includes Credit Limit
        f"CREATE TABLE IF NOT EXISTS customers (phone TEXT PRIMARY KEY, name TEXT, address TEXT, joined_date TEXT, credit_limit REAL DEFAULT 50000)",
        
        # Transactions: Master Ledger
        f"CREATE TABLE IF NOT EXISTS transactions (invoice_id TEXT PRIMARY KEY, customer_phone TEXT, date TEXT, type TEXT, total_amount REAL, paid_amount REAL, due_amount REAL, payment_mode TEXT, notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        
        # Invoice Items: Detail Lines
        f"CREATE TABLE IF NOT EXISTS invoice_items (id {pk}, invoice_id TEXT, product_name TEXT, quantity INTEGER, unit_price REAL, total_price REAL)",
        
        # Expenses: For Net Profit Calculation
        f"CREATE TABLE IF NOT EXISTS expenses (id {pk}, date TEXT, category TEXT, amount REAL, note TEXT, added_by TEXT)",
        
        # System Logs: Audit Trail
        f"CREATE TABLE IF NOT EXISTS system_logs (id {pk}, timestamp TEXT, username TEXT, action TEXT, details TEXT)"
    ]
    
    for q in tables:
        run_query(q)

# Run initialization once
init_system()

# ==========================================
# 5. DATA CACHING LAYER (RAM Speed)
# ==========================================
# These functions load data into memory to prevent database lag during UI interaction

@st.cache_data(ttl=60)
def get_dashboard_metrics():
    today = datetime.date.today().isoformat()
    
    # Revenue Today
    sales = run_query(f"SELECT SUM(total_amount) as v FROM transactions WHERE date='{today}' AND type='SALE'", fetch=True)
    sales_val = sales[0]['v'] or 0
    
    # Expenses Today
    exps = run_query(f"SELECT SUM(amount) as v FROM expenses WHERE date='{today}'", fetch=True)
    exp_val = exps[0]['v'] or 0
    
    # Total Market Credit
    total_sales = run_query("SELECT SUM(total_amount) as v FROM transactions WHERE type='SALE'", fetch=True)[0]['v'] or 0
    total_paid = run_query("SELECT SUM(paid_amount) as v FROM transactions", fetch=True)[0]['v'] or 0
    receivables = total_sales - total_paid
    
    return sales_val, exp_val, receivables

@st.cache_data(ttl=300)
def get_master_data():
    prods = run_query("SELECT * FROM products ORDER BY name", fetch=True)
    custs = run_query("SELECT * FROM customers ORDER BY name", fetch=True)
    return prods, custs

def force_refresh():
    st.cache_data.clear()
    st.rerun()

# ==========================================
# 6. PROFESSIONAL PDF ENGINE
# ==========================================
class PDF(FPDF):
    def header(self):
        # Company Logo/Header Area
        self.set_font('Arial', 'B', 24)
        self.set_text_color(15, 23, 42) # Dark Navy
        self.cell(0, 10, BUSINESS_INFO["name"], 0, 1, 'C')
        
        self.set_font('Arial', '', 10)
        self.set_text_color(100, 116, 139) # Slate Gray
        self.cell(0, 5, BUSINESS_INFO["address"], 0, 1, 'C')
        self.cell(0, 5, f"Helpline: {BUSINESS_INFO['phone']}", 0, 1, 'C')
        
        self.ln(5)
        self.set_draw_color(226, 232, 240) # Light Gray Line
        self.set_line_width(0.5)
        self.line(10, 35, 200, 35)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(148, 163, 184)
        self.cell(0, 10, f'Computer Generated Invoice | Page {self.page_no()}', 0, 0, 'C')

def generate_invoice_pdf(tx_data, items, cust_data):
    pdf = PDF()
    pdf.add_page()
    
    # Title Section
    pdf.set_font('Arial', 'B', 16)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(120, 10, "INVOICE", 0, 0)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(70, 10, f"#{tx_data['invoice_id']}", 0, 1, 'R')
    
    # Customer Details Box
    pdf.set_fill_color(248, 250, 252)
    pdf.rect(10, 50, 190, 25, 'F')
    
    pdf.set_y(52)
    pdf.set_x(12)
    pdf.set_font('Arial', 'B', 10)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(20, 5, "Bill To:", 0, 0)
    pdf.set_font('Arial', '', 10)
    pdf.cell(100, 5, f"{cust_data['name']} ({cust_data['phone']})", 0, 1)
    
    pdf.set_x(12)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(20, 5, "Address:", 0, 0)
    pdf.set_font('Arial', '', 10)
    pdf.cell(100, 5, f"{cust_data['address']}", 0, 1)
    
    pdf.set_y(52)
    pdf.set_x(140)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(20, 5, "Date:", 0, 0)
    pdf.set_font('Arial', '', 10)
    pdf.cell(30, 5, f"{tx_data['date']}", 0, 1)
    
    pdf.ln(25)
    
    # Table Header
    pdf.set_fill_color(15, 23, 42) # Dark Header
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(10, 10, "#", 1, 0, 'C', 1)
    pdf.cell(90, 10, "Product Description", 1, 0, 'L', 1)
    pdf.cell(30, 10, "Rate", 1, 0, 'R', 1)
    pdf.cell(20, 10, "Qty", 1, 0, 'C', 1)
    pdf.cell(40, 10, "Total", 1, 1, 'R', 1)
    pdf.ln(10)
    
    # Table Rows
    pdf.set_text_color(15, 23, 42)
    pdf.set_font('Arial', '', 10)
    fill = False
    
    for idx, item in enumerate(items):
        name = item.get('product_name') or item.get('name')
        price = float(item.get('unit_price') or item.get('price') or 0)
        qty = int(item.get('quantity') or item.get('qty') or 0)
        total = float(item.get('total_price') or item.get('total') or 0)
        
        pdf.cell(10, 10, str(idx+1), 1, 0, 'C', fill)
        pdf.cell(90, 10, str(name)[:45], 1, 0, 'L', fill)
        pdf.cell(30, 10, f"{price:,.0f}", 1, 0, 'R', fill)
        pdf.cell(20, 10, str(qty), 1, 0, 'C', fill)
        pdf.cell(40, 10, f"{total:,.0f}", 1, 1, 'R', fill)
        pdf.ln(10)
        # fill = not fill # Alternating rows
        
    pdf.ln(5)
    
    # Totals Block
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(140, 8, "Sub Total", 0, 0, 'R')
    pdf.cell(50, 8, f"Rs {tx_data['total_amount']:,.0f}", 0, 1, 'R')
    
    pdf.cell(140, 8, "Paid Amount", 0, 0, 'R')
    pdf.set_text_color(22, 163, 74) # Green
    pdf.cell(50, 8, f"Rs {tx_data['paid_amount']:,.0f}", 0, 1, 'R')
    
    pdf.set_text_color(15, 23, 42)
    pdf.set_font('Arial', 'B', 12)
    
    # Balance Highlight
    if tx_data['due_amount'] > 0:
        pdf.set_text_color(220, 38, 38) # Red
    pdf.cell(140, 10, "Balance Due", 0, 0, 'R')
    pdf.cell(50, 10, f"Rs {tx_data['due_amount']:,.0f}", 0, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 7. APP MODULES (LOGIN & MAIN)
# ==========================================
def login_page():
    inject_custom_css()
    st.markdown("""
        <div class="login-container">
            <h1 style="color:#0f172a; margin-bottom:10px;">🚜 KKG ERP</h1>
            <p style="color:#64748b; margin-bottom:30px;">Secure Business Access</p>
        </div>
    """, unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        with st.form("login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Access Dashboard"):
                if username in USERS and USERS[username] == password:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = username
                    st.session_state['role'] = "admin" if username == "admin" else "staff"
                    st.rerun()
                else:
                    st.error("Invalid Credentials")

def main():
    inject_custom_css()
    
    if 'logged_in' not in st.session_state:
        login_page()
        return

    # --- SIDEBAR NAV ---
    st.sidebar.markdown(f"""
        <div style='text-align: center; padding: 20px 0; border-bottom: 1px solid #1e293b; margin-bottom: 20px;'>
            <div style='font-size: 3rem;'>🚜</div>
            <h2 style='color: white; margin: 0;'>KKG ERP</h2>
            <p style='color: #94a3b8; font-size: 0.8rem; margin-top:5px;'>User: {st.session_state['username'].upper()}</p>
        </div>
    """, unsafe_allow_html=True)
    
    menu_options = ["Dashboard", "POS Terminal", "Inventory", "Customers", "Ledger", "Expenses"]
    if st.session_state['role'] == "staff":
        menu_options = ["POS Terminal", "Customers", "Inventory"] # Staff restricted view
        
    menu = st.sidebar.radio("Navigation", menu_options, label_visibility="collapsed")
    
    if st.sidebar.button("Log Out"):
        st.session_state.clear()
        st.rerun()

    # --- MODULES ---
    
    # 1. DASHBOARD
    if menu == "Dashboard":
        st.title("Executive Overview")
        st.markdown(f"**Date:** {datetime.date.today().strftime('%d %B, %Y')}")
        
        sales, exps, debt = get_dashboard_metrics()
        profit = sales - exps # Simple gross profit
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Revenue Today", f"₹{sales:,.0f}")
        c2.metric("Expenses Today", f"₹{exps:,.0f}")
        c3.metric("Net Profit (Est)", f"₹{profit:,.0f}", delta="Daily Margin")
        c4.metric("Market Debt", f"₹{debt:,.0f}", delta="Receivables", delta_color="inverse")
        
        st.markdown("### 📊 Business Trends")
        # Sales Chart
        trend_df = pd.DataFrame(run_query("SELECT date, SUM(total_amount) as sales FROM transactions WHERE type='SALE' GROUP BY date ORDER BY date DESC LIMIT 14", fetch=True))
        if not trend_df.empty:
            trend_df = trend_df.set_index('date').sort_index()
            st.line_chart(trend_df, height=300)
        else:
            st.info("Start selling to see trends.")

    # 2. POS TERMINAL
    elif menu == "POS Terminal":
        st.title("🛒 POS Terminal")
        
        # Load cached data for speed
        prods, custs = get_master_data()
        
        if not prods or not custs:
            st.warning("⚠️ System Empty. Please add Customers and Inventory first.")
            st.stop()
            
        # Fast Maps
        c_map = {f"{c['name']} | {c['phone']}": c for c in custs}
        p_map = {f"{p['name']} (₹{p['price']:.0f})": p for p in prods}
        
        col_input, col_cart = st.columns([1.2, 1])
        
        with col_input:
            st.markdown("##### New Transaction")
            with st.container(): # Card
                # Form prevents reload lag
                with st.form("add_item_form"):
                    c_sel = st.selectbox("Customer", list(c_map.keys()))
                    p_sel = st.selectbox("Product", list(p_map.keys()))
                    qty = st.number_input("Quantity", 1, 1000)
                    
                    if st.form_submit_button("Add to Bill"):
                        if 'cart' not in st.session_state: st.session_state.cart = []
                        prod = p_map[p_sel]
                        
                        # Stock Validation
                        current_cart_qty = sum(item['qty'] for item in st.session_state.cart if item['id'] == prod['id'])
                        if (current_cart_qty + qty) > prod['stock']:
                            st.error(f"Stock Error! Only {prod['stock']} available.")
                        else:
                            st.session_state.cart.append({**prod, 'qty': qty, 'total': qty * prod['price']})
                            st.success(f"Added {prod['name']}")

        with col_cart:
            st.markdown("##### Current Cart")
            if 'cart' in st.session_state and st.session_state.cart:
                cart_df = pd.DataFrame(st.session_state.cart)
                # Nice Table
                st.dataframe(cart_df[['name', 'price', 'qty', 'total']], hide_index=True, use_container_width=True)
                
                total = cart_df['total'].sum()
                
                st.markdown(f"""
                <div style="background:#dbeafe; padding:15px; border-radius:10px; display:flex; justify-content:space-between; align-items:center;">
                    <span style="color:#1e40af; font-weight:600;">Total Payable</span>
                    <span style="color:#1e3a8a; font-size:24px; font-weight:800;">₹{total:,.0f}</span>
                </div>
                """, unsafe_allow_html=True)
                
                st.write("")
                with st.form("checkout"):
                    paid = st.number_input("Amount Received", min_value=0.0, value=0.0)
                    mode = st.selectbox("Payment Mode", ["Cash", "UPI", "Credit"])
                    
                    if st.form_submit_button("✅ COMPLETE SALE"):
                        cust = c_map[c_sel]
                        inv_id = f"INV-{int(time.time())}"
                        due = total - paid
                        
                        # Transaction
                        run_query("INSERT INTO transactions (invoice_id, customer_phone, date, type, total_amount, paid_amount, due_amount, payment_mode) VALUES (?,?,?,?,?,?,?,?)",
                                  (inv_id, cust['phone'], str(datetime.date.today()), 'SALE', total, paid, due, mode))
                        
                        # Items
                        for item in st.session_state.cart:
                            run_query("INSERT INTO invoice_items (invoice_id, product_name, quantity, unit_price, total_price) VALUES (?,?,?,?,?)",
                                      (inv_id, item['name'], item['qty'], item['price'], item['total']))
                            run_query("UPDATE products SET stock = stock - ? WHERE id = ?", (item['qty'], item['id']))
                        
                        # PDF
                        tx_data = {'invoice_id': inv_id, 'date': str(datetime.date.today()), 'total_amount': total, 'paid_amount': paid, 'due_amount': due}
                        st.session_state.pdf = generate_invoice_pdf(tx_data, st.session_state.cart, cust)
                        
                        # Reset
                        st.session_state.cart = []
                        force_refresh()
                        st.rerun()
            
            if 'pdf' in st.session_state:
                st.success("Transaction Saved!")
                st.download_button("🖨️ Print Invoice", st.session_state.pdf, "invoice.pdf", "application/pdf")
                if st.button("Start New Sale"):
                    del st.session_state.pdf
                    st.rerun()

    # 3. INVENTORY MANAGEMENT
    elif menu == "Inventory":
        st.title("📦 Inventory Control")
        
        with st.expander("Add New Item"):
            with st.form("add_prod"):
                c1, c2, c3, c4 = st.columns(4)
                n = c1.text_input("Item Name")
                cat = c2.text_input("Category")
                sp = c3.number_input("Selling Price (₹)", 0.0)
                stk = c4.number_input("Stock Qty", 0)
                
                # New: Cost Price for Profit Tracking
                cp = st.number_input("Cost Price (Optional - for Profit Calc)", 0.0)
                
                if st.form_submit_button("Save Item"):
                    run_query("INSERT INTO products (name, category, price, cost_price, stock) VALUES (?,?,?,?,?)", (n, cat, sp, cp, stk))
                    force_refresh()
                    st.success("Item Added")
                    st.rerun()
        
        # Display Table
        df = pd.DataFrame(get_master_data()[0])
        if not df.empty:
            st.dataframe(df[['name', 'category', 'price', 'stock']], use_container_width=True)
            
            # Delete Action
            if st.session_state['role'] == "admin":
                with st.expander("Administrative Actions"):
                    d_id = st.number_input("Enter ID to Delete", min_value=0)
                    if st.button("Delete Product", type="secondary") and d_id > 0:
                        run_query("DELETE FROM products WHERE id=?", (d_id,))
                        force_refresh()
                        st.warning(f"Product {d_id} Deleted")
                        st.rerun()

    # 4. CUSTOMER MANAGEMENT
    elif menu == "Customers":
        st.title("👥 Customer Database")
        
        with st.expander("Register New Customer"):
            with st.form("reg_cust"):
                c1, c2 = st.columns(2)
                n = c1.text_input("Full Name")
                p = c2.text_input("Phone Number")
                a = st.text_input("Address")
                if st.form_submit_button("Register"):
                    if run_query("INSERT INTO customers (phone, name, address, joined_date) VALUES (?,?,?,?)", (p, n, a, str(datetime.date.today()))):
                        force_refresh()
                        st.success("Registered")
                        st.rerun()
                    else:
                        st.error("Phone number already exists.")
        
        # Customer List
        df = pd.DataFrame(get_master_data()[1])
        if not df.empty:
            st.dataframe(df, use_container_width=True)

    # 5. EXPENSES
    elif menu == "Expenses":
        st.title("💸 Expense Tracker")
        
        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown("##### Record Expense")
            with st.form("exp"):
                cat = st.selectbox("Category", ["Rent", "Salary", "Electricity", "Tea/Refreshment", "Transport", "Other"])
                amt = st.number_input("Amount (₹)", min_value=1.0)
                note = st.text_input("Description")
                if st.form_submit_button("Save Expense"):
                    run_query("INSERT INTO expenses (date, category, amount, note, added_by) VALUES (?,?,?,?,?)",
                              (str(datetime.date.today()), cat, amt, note, st.session_state['username']))
                    st.success("Recorded")
                    st.rerun()
        
        with c2:
            st.markdown("##### Recent Expenses")
            exps = run_query("SELECT date, category, amount, note FROM expenses ORDER BY date DESC LIMIT 10", fetch=True)
            if exps:
                st.dataframe(pd.DataFrame(exps), use_container_width=True)

    # 6. LEDGER
    elif menu == "Ledger":
        st.title("📖 Customer Ledger")
        
        custs = get_master_data()[1]
        if not custs: st.stop()
        
        c_map = {f"{c['name']} ({c['phone']})": c for c in custs}
        sel = st.selectbox("Select Customer", list(c_map.keys()))
        cust = c_map[sel]
        
        col1, col2 = st.columns(2)
        d1 = col1.date_input("From", datetime.date.today() - datetime.timedelta(days=30))
        d2 = col2.date_input("To", datetime.date.today())
        
        if st.button("View Statement"):
            txs = run_query(f"SELECT * FROM transactions WHERE customer_phone='{cust['phone']}' AND date BETWEEN '{d1}' AND '{d2}' ORDER BY created_at DESC", fetch=True)
            if txs:
                df = pd.DataFrame(txs)
                st.dataframe(df[['date', 'invoice_id', 'type', 'total_amount', 'paid_amount', 'due_amount']], use_container_width=True)
                
                # Reprint
                st.markdown("---")
                st.markdown("##### 🖨️ Reprint Bill")
                sale_txs = [t for t in txs if t['type'] == 'SALE']
                if sale_txs:
                    inv_ids = [t['invoice_id'] for t in sale_txs]
                    sel_inv = st.selectbox("Select Invoice ID", inv_ids)
                    if st.button("Generate Copy"):
                        inv_data = next(t for t in sale_txs if t['invoice_id'] == sel_inv)
                        items = run_query(f"SELECT * FROM invoice_items WHERE invoice_id='{sel_inv}'", fetch=True)
                        pdf = generate_invoice_pdf(inv_data, items, cust)
                        st.download_button("Download PDF", pdf, f"{sel_inv}.pdf", "application/pdf")
            else:
                st.info("No transactions found in this period.")

if __name__ == "__main__":
    main()
