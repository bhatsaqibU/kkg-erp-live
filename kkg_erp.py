import streamlit as st
import pandas as pd
import datetime
import time
from fpdf import FPDF
import sqlite3
import os

# ==========================================
# 1. DATABASE ENGINE (Self-Healing & Persistent)
# ==========================================
@st.cache_resource
def get_db_connection():
    """Establishes a PERSISTENT connection to the database."""
    # Cloud Mode (Postgres)
    if hasattr(st, "secrets") and "postgres" in st.secrets:
        import psycopg2
        try:
            return "POSTGRES", psycopg2.connect(st.secrets["postgres"]["url"])
        except Exception as e:
            return None, None
    
    # Local Mode (SQLite)
    return "SQLITE", sqlite3.connect("kkg_database.sqlite", check_same_thread=False)

def run_query(query, params=None, fetch=False):
    db_type, conn = get_db_connection()
    if not conn: return [] if fetch else False

    # Auto-Reconnect for Cloud
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
        return [] if fetch else False

# One-time Init (Cached to prevent startup lag)
@st.cache_resource
def init_system():
    db_type, _ = get_db_connection()
    if not db_type: return
    pk = "SERIAL PRIMARY KEY" if db_type == "POSTGRES" else "INTEGER PRIMARY KEY AUTOINCREMENT"
    queries = [
        f"CREATE TABLE IF NOT EXISTS products (id {pk}, name TEXT, category TEXT, price REAL, stock INTEGER)",
        "CREATE TABLE IF NOT EXISTS customers (phone TEXT PRIMARY KEY, name TEXT, address TEXT, joined_date TEXT)",
        "CREATE TABLE IF NOT EXISTS transactions (invoice_id TEXT PRIMARY KEY, customer_phone TEXT, date TEXT, type TEXT, total_amount REAL, paid_amount REAL, due_amount REAL, payment_mode TEXT, notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
        f"CREATE TABLE IF NOT EXISTS invoice_items (id {pk}, invoice_id TEXT, product_name TEXT, quantity INTEGER, unit_price REAL, total_price REAL)"
    ]
    for q in queries: run_query(q)

init_system()

# ==========================================
# 2. SMART CACHING (The "Instant" Feel)
# ==========================================
@st.cache_data(ttl=60)
def get_dashboard_stats():
    today = datetime.date.today().isoformat()
    sales_data = run_query(f"SELECT SUM(total_amount) as v FROM transactions WHERE date='{today}' AND type='SALE'", fetch=True)
    sales_val = sales_data[0]['v'] if sales_data and sales_data[0]['v'] else 0
    
    totals = run_query("SELECT SUM(total_amount) as s, SUM(paid_amount) as p FROM transactions", fetch=True)
    receivables = (totals[0]['s'] or 0) - (totals[0]['p'] or 0) if totals else 0
    
    low_stock = run_query("SELECT COUNT(*) as c FROM products WHERE stock < 5", fetch=True)
    stock_alert = low_stock[0]['c'] if low_stock else 0
    
    return sales_val, receivables, stock_alert

@st.cache_data(ttl=60)
def get_charts_data():
    # Sales Trend
    trend = run_query("SELECT date, SUM(total_amount) as sales FROM transactions WHERE type='SALE' GROUP BY date ORDER BY date DESC LIMIT 7", fetch=True)
    trend_df = pd.DataFrame(trend) if trend else pd.DataFrame(columns=['date', 'sales'])
    if not trend_df.empty:
        trend_df['date'] = pd.to_datetime(trend_df['date'])
        trend_df = trend_df.sort_values('date')

    # Top Products
    top = run_query("SELECT product_name, SUM(quantity) as qty FROM invoice_items GROUP BY product_name ORDER BY qty DESC LIMIT 5", fetch=True)
    top_df = pd.DataFrame(top) if top else pd.DataFrame(columns=['product_name', 'qty'])
    
    return trend_df, top_df

@st.cache_data(ttl=300)
def get_cached_data(query):
    return run_query(query, fetch=True)

def refresh_data():
    st.cache_data.clear()

# ==========================================
# 3. PROFESSIONAL PDF ENGINE
# ==========================================
class PDF(FPDF):
    def header(self):
        # Logo placeholder logic could go here
        self.set_font('Arial', 'B', 22)
        self.cell(0, 10, "KISAN KHIDMAT GHAR", 0, 1, 'C')
        self.set_font('Arial', 'B', 10)
        self.cell(0, 5, "Chakoora, Pulwama, J&K", 0, 1, 'C')
        self.cell(0, 5, "Contact: 9622749245", 0, 1, 'C')
        self.ln(10)
        self.set_draw_color(0, 0, 0)
        self.set_line_width(0.5)
        self.line(10, 32, 200, 32)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Generated by KKG ERP - Page {self.page_no()}', 0, 0, 'C')

def generate_pdf(tx, items, cust):
    pdf = PDF()
    pdf.add_page()
    
    # Invoice Header Info
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(130, 10, "INVOICE", 0, 0)
    pdf.set_font('Arial', '', 10)
    pdf.cell(60, 10, f"Date: {tx['date']}", 0, 1, 'R')
    
    # Customer Details Block
    pdf.set_fill_color(245, 247, 250)
    pdf.rect(10, pdf.get_y(), 190, 25, 'F')
    pdf.set_xy(12, pdf.get_y() + 2)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(20, 5, "Bill To:", 0, 0)
    pdf.set_font('Arial', '', 10)
    pdf.cell(100, 5, f"{cust['name']}", 0, 1)
    
    pdf.set_x(12)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(20, 5, "Phone:", 0, 0)
    pdf.set_font('Arial', '', 10)
    pdf.cell(100, 5, f"{cust['phone']}", 0, 1)
    
    pdf.set_x(12)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(20, 5, "Invoice #:", 0, 0)
    pdf.set_font('Arial', '', 10)
    pdf.cell(100, 5, f"{tx['invoice_id']}", 0, 1)
    pdf.ln(10)
    
    # Table Header
    pdf.set_fill_color(41, 128, 185) # Blue header
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(10, 8, "#", 1, 0, 'C', 1)
    pdf.cell(95, 8, "Product Description", 1, 0, 'L', 1)
    pdf.cell(25, 8, "Rate", 1, 0, 'R', 1)
    pdf.cell(20, 8, "Qty", 1, 0, 'C', 1)
    pdf.cell(40, 8, "Total", 1, 1, 'R', 1)
    pdf.ln(8)
    
    # Table Content
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Arial', '', 10)
    
    for idx, i in enumerate(items):
        name = i.get('product_name') or i.get('name') or "Item"
        price = float(i.get('unit_price', i.get('price', 0)))
        qty = int(i.get('quantity', i.get('qty', 0)))
        total = float(i.get('total_price', i.get('total', 0)))
        
        pdf.cell(10, 8, str(idx+1), 1, 0, 'C')
        pdf.cell(95, 8, str(name)[:50], 1, 0, 'L')
        pdf.cell(25, 8, f"{price:,.0f}", 1, 0, 'R')
        pdf.cell(20, 8, str(qty), 1, 0, 'C')
        pdf.cell(40, 8, f"{total:,.0f}", 1, 1, 'R')
        pdf.ln(8)
    
    # Summary Block
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 11)
    
    pdf.cell(140, 8, "Sub Total", 0, 0, 'R')
    pdf.cell(50, 8, f"Rs {tx['total_amount']:,.0f}", 1, 1, 'R')
    
    pdf.cell(140, 8, "Paid Amount", 0, 0, 'R')
    pdf.cell(50, 8, f"Rs {float(tx.get('paid_amount', 0)):,.0f}", 1, 1, 'R')
    
    # Due Amount Highlighting
    due = float(tx.get('due_amount', 0))
    if due > 0:
        pdf.set_text_color(220, 53, 69) # Red
    else:
        pdf.set_text_color(40, 167, 69) # Green
        
    pdf.cell(140, 10, "Balance Due", 0, 0, 'R')
    pdf.cell(50, 10, f"Rs {due:,.0f}", 1, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 4. IMMERSIVE UI ENGINE
# ==========================================
st.set_page_config(page_title="KKG ERP", page_icon="🌾", layout="wide")

st.markdown("""
    <style>
    /* Global Theme */
    .stApp { background-color: #f3f4f6; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { 
        background-color: #1e293b; 
        border-right: 1px solid #334155;
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] p { color: #f8fafc; }
    
    /* Navigation Buttons */
    div[role="radiogroup"] label {
        background: transparent;
        color: #cbd5e1;
        padding: 10px;
        border-radius: 8px;
        margin-bottom: 5px;
        transition: all 0.3s;
    }
    div[role="radiogroup"] label:hover {
        background: #334155;
        color: white;
    }
    
    /* Cards (Metrics) */
    div[data-testid="stMetric"] {
        background-color: white;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        border-left: 6px solid #3b82f6;
    }
    [data-testid="stMetricValue"] { color: #1e293b; font-size: 28px; font-weight: 800; }
    [data-testid="stMetricLabel"] { color: #64748b; font-weight: 600; }
    
    /* Tables */
    [data-testid="stDataFrame"] {
        background: white;
        border-radius: 12px;
        padding: 15px;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
    }
    
    /* Buttons */
    .stButton button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
        border: none;
        padding: 10px 24px;
        border-radius: 8px;
        font-weight: 600;
        box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.3);
        width: 100%;
        transition: transform 0.1s;
    }
    .stButton button:active { transform: scale(0.98); }
    
    /* Secondary/Delete Buttons */
    button[kind="secondary"] {
        background: #fee2e2 !important;
        color: #ef4444 !important;
        border: 1px solid #fecaca !important;
        box-shadow: none;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 5. APP MODULES
# ==========================================
def main():
    st.sidebar.markdown(f"""
        <div style='text-align: center; padding: 20px 0; border-bottom: 1px solid #334155; margin-bottom: 20px;'>
            <div style='font-size: 40px; margin-bottom: 10px;'>🌾</div>
            <h2 style='color: white; margin: 0; font-size: 24px;'>KKG ERP</h2>
            <p style='color: #94a3b8; font-size: 13px; margin-top: 5px;'>{BUSINESS_INFO['name']}</p>
        </div>
    """, unsafe_allow_html=True)
    
    menu = st.sidebar.radio("Main Menu", ["Dashboard", "Billing (POS)", "Inventory", "Customers", "Ledger"], label_visibility="collapsed")

    # --- DASHBOARD ---
    if menu == "Dashboard":
        st.title("📊 Executive Dashboard")
        sales, receivables, stock_alert = get_dashboard_stats()
        trend_df, top_df = get_charts_data()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Today's Sales", f"₹{sales:,.0f}")
        c2.metric("Market Receivables", f"₹{receivables:,.0f}")
        c3.metric("Low Stock Items", stock_alert, delta_color="inverse")
        
        st.markdown("---")
        
        g1, g2 = st.columns(2)
        with g1:
            st.subheader("📈 Sales Trend")
            if not trend_df.empty:
                st.line_chart(trend_df.set_index('date'), height=300, color="#3b82f6")
            else:
                st.info("No sales data yet.")
                
        with g2:
            st.subheader("🏆 Top Products")
            if not top_df.empty:
                st.bar_chart(top_df.set_index('product_name'), height=300, color="#10b981")
            else:
                st.info("Start selling to see data.")
                
        if st.button("Refresh Data", key="refresh_dash"): 
            refresh_data()
            st.rerun()

    # --- POS (Billing) ---
    elif menu == "Billing (POS)":
        st.title("🛒 Billing Terminal")
        
        # Prefetch data for speed
        all_cust = get_cached_data("SELECT * FROM customers")
        all_prod = get_cached_data("SELECT * FROM products")
        
        if not all_cust or not all_prod:
            st.warning("⚠️ Setup Required: Add Customers & Inventory first.")
            st.stop()
            
        c_map = {f"{c['name']} ({c['phone']})": c for c in all_cust}
        p_map = {f"{p['name']} (₹{p['price']:.0f} | Stock: {p['stock']})": p for p in all_prod}
        
        col_form, col_cart = st.columns([1.2, 1])
        
        with col_form:
            st.markdown("### Selection")
            with st.container(): # Card-like container
                sel_c_name = st.selectbox("Customer", list(c_map.keys()))
                sel_p_name = st.selectbox("Product", list(p_map.keys()))
                qty = st.number_input("Quantity", min_value=1, value=1)
                
                if 'cart' not in st.session_state: st.session_state.cart = []
                
                if st.button("Add Item +", key="add_btn"):
                    prod = p_map[sel_p_name]
                    # Smart Stock Check
                    current_cart_qty = sum(item['qty'] for item in st.session_state.cart if item['id'] == prod['id'])
                    if (current_cart_qty + qty) > prod['stock']:
                        st.error(f"❌ Stock Error! Only {prod['stock']} available.")
                    else:
                        st.session_state.cart.append({**prod, 'qty': qty, 'total': qty * prod['price']})
                        st.success("Added to Cart")

        with col_cart:
            st.markdown("### Current Bill")
            if st.session_state.cart:
                df = pd.DataFrame(st.session_state.cart)
                # Custom HTML Table for better look
                st.dataframe(df[['name', 'qty', 'total']], use_container_width=True, hide_index=True)
                
                total = df['total'].sum()
                st.markdown(f"""<div style="background-color:#dbeafe; padding:15px; border-radius:8px; text-align:right;">
                                <span style="color:#1e40af; font-size:14px;">Total Amount</span><br>
                                <span style="color:#1e3a8a; font-size:28px; font-weight:bold;">₹{total:,.0f}</span>
                                </div>""", unsafe_allow_html=True)
                
                paid = st.number_input("Amount Paid", min_value=0.0, value=0.0)
                
                if st.button("✅ FINALIZE & PRINT BILL", type="primary"):
                    cust = c_map[sel_c_name]
                    inv_id = f"INV-{int(time.time())}"
                    due = total - paid
                    
                    # Atomic Write
                    run_query("INSERT INTO transactions (invoice_id, customer_phone, date, type, total_amount, paid_amount, due_amount) VALUES (?,?,?,?,?,?,?)",
                              (inv_id, cust['phone'], str(datetime.date.today()), 'SALE', total, paid, due))
                    
                    for item in st.session_state.cart:
                        run_query("INSERT INTO invoice_items (invoice_id, product_name, quantity, unit_price, total_price) VALUES (?,?,?,?,?)",
                                  (inv_id, item['name'], item['qty'], item['price'], item['total']))
                        run_query("UPDATE products SET stock = stock - ? WHERE id = ?", (item['qty'], item['id']))
                    
                    # PDF Generation
                    st.session_state.pdf = generate_pdf({'invoice_id': inv_id, 'date': str(datetime.date.today()), 'total_amount': total, 'paid_amount': paid, 'due_amount': due}, st.session_state.cart, cust)
                    
                    st.session_state.cart = []
                    refresh_data()
                    st.rerun()
            
            if 'pdf' in st.session_state:
                st.success("Bill Generated Successfully!")
                st.download_button("📥 Download PDF Bill", st.session_state.pdf, "invoice.pdf", "application/pdf")

    # --- INVENTORY ---
    elif menu == "Inventory":
        st.title("📦 Inventory Management")
        
        with st.expander("➕ Add New Item", expanded=False):
            with st.form("add_i"):
                c1, c2, c3 = st.columns(3)
                n = c1.text_input("Product Name")
                p = c2.number_input("Selling Price", min_value=0.0)
                s = c3.number_input("Stock Quantity", min_value=0)
                if st.form_submit_button("Save Item"):
                    run_query("INSERT INTO products (name, price, stock) VALUES (?,?,?)", (n,p,s))
                    refresh_data(); st.success("Saved"); st.rerun()
        
        df = pd.DataFrame(get_cached_data("SELECT * FROM products"))
        if not df.empty:
            for i, r in df.iterrows():
                with st.container():
                    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                    c1.markdown(f"**{r['name']}**")
                    c2.markdown(f"₹{r['price']}")
                    c3.markdown(f"{r['stock']} units")
                    if c4.button("🗑️", key=f"del_{r['id']}", type="secondary", help="Delete Item"):
                        run_query("DELETE FROM products WHERE id=?", (r['id'],))
                        refresh_data(); st.rerun()
                    st.markdown("<hr style='margin:5px 0; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)

    # --- CUSTOMERS ---
    elif menu == "Customers":
        st.title("👥 Customer List")
        with st.expander("➕ Add New Customer", expanded=False):
            with st.form("add_c"):
                n = st.text_input("Full Name")
                p = st.text_input("Phone Number (ID)")
                a = st.text_input("Address")
                if st.form_submit_button("Register"):
                    if run_query("INSERT INTO customers VALUES (?,?,?,?)", (p,n,a,str(datetime.date.today()))):
                        refresh_data(); st.success("Saved"); st.rerun()
                    else: st.error("Customer already exists!")
        
        df = pd.DataFrame(get_cached_data("SELECT * FROM customers"))
        if not df.empty:
            for i, r in df.iterrows():
                c1, c2, c3 = st.columns([2, 2, 1])
                c1.write(f"**{r['name']}**")
                c2.write(r['phone'])
                if c3.button("🗑️", key=f"dc_{r['phone']}", type="secondary"):
                    check = run_query("SELECT count(*) as c FROM transactions WHERE customer_phone=?", (r['phone'],), fetch=True)
                    if check[0]['c'] == 0:
                        run_query("DELETE FROM customers WHERE phone=?", (r['phone'],)); refresh_data(); st.rerun()
                    else: st.error("Cannot delete: Has transactions")
                st.markdown("<hr style='margin:5px 0; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)

    # --- LEDGER ---
    elif menu == "Ledger":
        st.title("📖 Customer Ledger")
        all_cust = get_cached_data("SELECT * FROM customers")
        
        if all_cust:
            c_map = {f"{c['name']} ({c['phone']})": c for c in all_cust}
            sel = st.selectbox("Select Customer to View History", list(c_map.keys()))
            cust = c_map[sel]
            
            if st.button("Load History"):
                txs = run_query(f"SELECT * FROM transactions WHERE customer_phone='{cust['phone']}' ORDER BY created_at DESC", fetch=True)
                if txs:
                    st.dataframe(pd.DataFrame(txs)[['date', 'invoice_id', 'total_amount', 'paid_amount', 'due_amount']], use_container_width=True)
                    
                    st.markdown("### 🖨️ Reprint Bill")
                    sale_txs = [t for t in txs if t['type'] == 'SALE']
                    if sale_txs:
                        inv_ids = [t['invoice_id'] for t in sale_txs]
                        sel_inv = st.selectbox("Select Invoice", inv_ids)
                        if st.button("Generate PDF Copy"):
                            inv_data = next(t for t in sale_txs if t['invoice_id'] == sel_inv)
                            items = run_query(f"SELECT * FROM invoice_items WHERE invoice_id='{sel_inv}'", fetch=True)
                            pdf = generate_pdf(inv_data, items, cust)
                            st.download_button("Download PDF", pdf, f"{sel_inv}.pdf", "application/pdf")
                else: st.info("No Transaction History")

if __name__ == "__main__":
    main()
