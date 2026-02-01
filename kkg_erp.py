import streamlit as st
import pandas as pd
import datetime
import time
from fpdf import FPDF
import os
import sqlite3

# ==========================================
# 1. HIGH-PERFORMANCE DATABASE ENGINE
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
            st.error(f"Cloud DB Error: {e}")
            return None, None
    
    # Local Mode (SQLite)
    return "SQLITE", sqlite3.connect("kkg_database.sqlite", check_same_thread=False)

def run_query(query, params=None, fetch=False):
    db_type, conn = get_db_connection()
    if not conn: return [] if fetch else False

    # Auto-reconnect if cloud connection dropped
    if db_type == "POSTGRES" and conn.closed:
        st.cache_resource.clear()
        db_type, conn = get_db_connection()

    if db_type == "POSTGRES": query = query.replace('?', '%s')

    try:
        cur = conn.cursor()
        # Set Row factory for SQLite to access columns by name
        if db_type == "SQLITE": conn.row_factory = sqlite3.Row
        
        cur.execute(query, params or ())
        
        if fetch:
            if db_type == "SQLITE":
                # Convert SQLite Rows to dicts
                return [dict(row) for row in cur.fetchall()]
            else:
                # Convert Postgres tuples to dicts
                cols = [desc[0] for desc in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
        else:
            conn.commit()
            cur.close()
            return True
    except Exception as e:
        st.error(f"Query Failed: {e}")
        return [] if fetch else False

# One-time initialization
@st.cache_resource
def init_system():
    db_type, _ = get_db_connection()
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
# 2. DATA CACHING (The "Instant" Feel)
# ==========================================
@st.cache_data(ttl=300) 
def get_products_cached():
    return run_query("SELECT * FROM products", fetch=True)

@st.cache_data(ttl=300)
def get_customers_cached():
    return run_query("SELECT * FROM customers", fetch=True)

def refresh_data():
    st.cache_data.clear()

# ==========================================
# 3. ROBUST PDF ENGINE
# ==========================================
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 18)
        self.cell(0, 10, "KISAN KHIDMAT GHAR", 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.cell(0, 5, "Chakoora, Pulwama | +91 9906XXXXXX", 0, 1, 'C')
        self.ln(10); self.line(10, 30, 200, 30)

def generate_pdf(tx, items, cust):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, "INVOICE", 0, 1, 'C')
    
    pdf.set_font('Arial', '', 10)
    pdf.cell(100, 5, f"To: {cust['name']}", 0, 0)
    pdf.cell(90, 5, f"Inv: {tx['invoice_id']}", 0, 1, 'R')
    pdf.ln(5)
    pdf.cell(100, 5, f"Ph: {cust['phone']}", 0, 0)
    pdf.cell(90, 5, f"Date: {tx['date']}", 0, 1, 'R')
    pdf.ln(10)
    
    pdf.set_fill_color(240, 240, 240); pdf.set_font('Arial', 'B', 10)
    pdf.cell(90, 8, 'Item', 1, 0, 'L', 1); pdf.cell(30, 8, 'Rate', 1, 0, 'R', 1)
    pdf.cell(20, 8, 'Qty', 1, 0, 'C', 1); pdf.cell(50, 8, 'Total', 1, 1, 'R', 1)
    
    pdf.set_font('Arial', '', 10)
    for i in items:
        # Handle dict items or DB rows safely
        name = i.get('product_name') or i.get('name') or "Item"
        price = float(i.get('unit_price') or i.get('price') or 0)
        qty = int(i.get('quantity') or i.get('qty') or 0)
        total = float(i.get('total_price') or i.get('total') or 0)
        
        pdf.cell(90, 8, str(name)[:40], 1, 0, 'L')
        pdf.cell(30, 8, f"{price:.0f}", 1, 0, 'R')
        pdf.cell(20, 8, str(qty), 1, 0, 'C')
        pdf.cell(50, 8, f"{total:.0f}", 1, 1, 'R')
    
    pdf.ln(5); pdf.set_font('Arial', 'B', 12)
    pdf.cell(140, 10, 'Grand Total', 0, 0, 'R'); pdf.cell(50, 10, f"Rs {tx['total_amount']:.0f}", 1, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 4. INDUSTRIAL UI
# ==========================================
st.set_page_config(page_title="KKG ERP", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    /* Main Background */
    .stApp { background-color: #f8fafc; font-family: 'Inter', sans-serif; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #0f172a; }
    [data-testid="stSidebar"] * { color: #f8fafc !important; }
    
    /* Metrics */
    div[data-testid="stMetric"] {
        background-color: white !important;
        border: 1px solid #e2e8f0;
        padding: 24px !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    [data-testid="stMetricValue"] { color: #0f172a !important; font-weight: 700; }
    
    /* Buttons */
    .stButton button {
        background-color: #2563eb;
        color: white !important;
        border-radius: 8px;
        font-weight: 600;
        border: none;
        width: 100%;
    }
    .stButton button:hover { background-color: #1d4ed8; }
    
    /* Delete Button */
    button[kind="secondary"] { background-color: #fee2e2 !important; color: #dc2626 !important; }
    
    /* Tables */
    [data-testid="stDataFrame"] { background-color: white; border-radius: 10px; padding: 10px; }
    </style>
""", unsafe_allow_html=True)

def main():
    st.sidebar.markdown("""<div style='text-align: center; padding: 20px;'><h1>🚜 KKG ERP</h1><p style='font-size:12px; color:#94a3b8'>Ultimate Edition</p></div>""", unsafe_allow_html=True)
    menu = st.sidebar.radio("Nav", ["Dashboard", "POS", "Inventory", "Customers", "Ledger"], label_visibility="collapsed")

    # --- DASHBOARD ---
    if menu == "Dashboard":
        st.title("Executive Dashboard")
        
        # Fast cached stats
        today = datetime.date.today().isoformat()
        sales_data = run_query(f"SELECT SUM(total_amount) as v FROM transactions WHERE date='{today}' AND type='SALE'", fetch=True)
        sales_val = sales_data[0]['v'] if sales_data and sales_data[0]['v'] else 0
        
        totals = run_query("SELECT SUM(total_amount) as s, SUM(paid_amount) as p FROM transactions", fetch=True)
        receivables = (totals[0]['s'] or 0) - (totals[0]['p'] or 0)
        
        c1, c2 = st.columns(2)
        c1.metric("Today's Sales", f"₹{sales_val:,.0f}")
        c2.metric("Market Receivables", f"₹{receivables:,.0f}")
        
        if st.button("🔄 Refresh Data"): refresh_data(); st.rerun()

    # --- POS (FASTEST VERSION) ---
    elif menu == "POS":
        st.title("🛒 Speed POS")
        
        all_cust = get_customers_cached()
        all_prod = get_products_cached()
        
        if not all_cust or not all_prod: st.warning("Add Customers & Inventory first"); st.stop()
        
        c_map = {f"{c['name']} ({c['phone']})": c for c in all_cust}
        p_map = {f"{p['name']} (₹{p['price']:.0f} | Stock: {p['stock']})": p for p in all_prod}
        
        c1, c2 = st.columns([1, 1])
        with c1:
            sel_c_name = st.selectbox("Customer", list(c_map.keys()))
            sel_p_name = st.selectbox("Product", list(p_map.keys()))
            qty = st.number_input("Qty", 1, value=1)
            
            if 'cart' not in st.session_state: st.session_state.cart = []
            
            if st.button("Add to Cart", type="primary"):
                prod = p_map[sel_p_name]
                # Local check + Cart check
                in_cart = sum(i['qty'] for i in st.session_state.cart if i['id'] == prod['id'])
                if (in_cart + qty) > prod['stock']:
                    st.error(f"Low Stock! Only {prod['stock']} available.")
                else:
                    st.session_state.cart.append({**prod, 'qty': qty, 'total': qty * prod['price']})
                    st.success("Added")

        with c2:
            st.subheader("Bill")
            if st.session_state.cart:
                df = pd.DataFrame(st.session_state.cart)
                # Show simple table
                for i, row in df.iterrows():
                    cols = st.columns([3, 1, 1])
                    cols[0].write(f"{row['name']} x{row['qty']}")
                    cols[1].write(f"₹{row['total']:.0f}")
                    if cols[2].button("X", key=f"rm_{i}", type="secondary"):
                        st.session_state.cart.pop(i)
                        st.rerun()
                
                total = df['total'].sum()
                st.markdown(f"### Total: ₹{total:,.0f}")
                paid = st.number_input("Paid", 0.0)
                
                if st.button("✅ CONFIRM SALE"):
                    cust = c_map[sel_c_name]
                    inv_id = f"INV-{int(time.time())}"
                    due = total - paid
                    
                    # 1. Transaction
                    run_query("INSERT INTO transactions (invoice_id, customer_phone, date, type, total_amount, paid_amount, due_amount) VALUES (?,?,?,?,?,?,?)",
                              (inv_id, cust['phone'], str(datetime.date.today()), 'SALE', total, paid, due))
                    
                    # 2. Items & Stock
                    for item in st.session_state.cart:
                        run_query("INSERT INTO invoice_items (invoice_id, product_name, quantity, unit_price, total_price) VALUES (?,?,?,?,?)",
                                  (inv_id, item['name'], item['qty'], item['price'], item['total']))
                        run_query("UPDATE products SET stock = stock - ? WHERE id = ?", (item['qty'], item['id']))
                    
                    # 3. PDF
                    tx_data = {'invoice_id': inv_id, 'date': str(datetime.date.today()), 'total_amount': total}
                    st.session_state.pdf = generate_pdf(tx_data, st.session_state.cart, cust)
                    
                    # 4. Reset
                    st.session_state.cart = []
                    refresh_data()
                    st.rerun()
            
            if 'pdf' in st.session_state:
                st.download_button("Download Bill", st.session_state.pdf, "bill.pdf", "application/pdf")

    # --- INVENTORY ---
    elif menu == "Inventory":
        st.title("📦 Stock Management")
        with st.expander("Add Product"):
            with st.form("add_i"):
                n = st.text_input("Name"); p = st.number_input("Price"); s = st.number_input("Stock")
                if st.form_submit_button("Add"):
                    run_query("INSERT INTO products (name, price, stock) VALUES (?,?,?)", (n,p,s))
                    refresh_data(); st.success("Saved"); st.rerun()
        
        df = pd.DataFrame(get_products_cached())
        if not df.empty:
            for i, r in df.iterrows():
                c1, c2, c3, c4 = st.columns([2,1,1,1])
                c1.write(f"**{r['name']}**")
                c2.write(f"₹{r['price']}")
                c3.write(f"Stock: {r['stock']}")
                if c4.button("Delete", key=f"d_{r['id']}", type="secondary"):
                    run_query("DELETE FROM products WHERE id=?", (r['id'],))
                    refresh_data(); st.rerun()

    # --- CUSTOMERS ---
    elif menu == "Customers":
        st.title("👥 Customer List")
        with st.expander("Register Customer"):
            with st.form("add_c"):
                n = st.text_input("Name"); p = st.text_input("Phone"); a = st.text_input("Address")
                if st.form_submit_button("Add"):
                    if run_query("INSERT INTO customers VALUES (?,?,?,?)", (p,n,a,str(datetime.date.today()))):
                        refresh_data(); st.success("Saved"); st.rerun()
                    else: st.error("Exists")
        
        df = pd.DataFrame(get_customers_cached())
        if not df.empty:
            for i, r in df.iterrows():
                c1, c2, c3 = st.columns([2,2,1])
                c1.write(r['name']); c2.write(r['phone'])
                if c3.button("Delete", key=f"dc_{r['phone']}", type="secondary"):
                    # Check history first
                    check = run_query("SELECT count(*) as c FROM transactions WHERE customer_phone=?", (r['phone'],), fetch=True)
                    if check[0]['c'] == 0:
                        run_query("DELETE FROM customers WHERE phone=?", (r['phone'],))
                        refresh_data(); st.rerun()
                    else:
                        st.error("Cannot delete: Has transactions")

    # --- LEDGER ---
    elif menu == "Ledger":
        st.title("📖 History")
        all_cust = get_customers_cached()
        if all_cust:
            c_map = {f"{c['name']} ({c['phone']})": c for c in all_cust}
            sel = st.selectbox("Customer", list(c_map.keys()))
            cust = c_map[sel]
            
            if st.button("Load History"):
                txs = run_query(f"SELECT * FROM transactions WHERE customer_phone='{cust['phone']}' ORDER BY created_at DESC", fetch=True)
                if txs:
                    st.dataframe(pd.DataFrame(txs)[['date', 'invoice_id', 'total_amount', 'paid_amount', 'due_amount']], use_container_width=True)
                    
                    # Reprint Logic
                    st.markdown("### Reprint Invoice")
                    sale_txs = [t for t in txs if t['type'] == 'SALE']
                    if sale_txs:
                        inv_ids = [t['invoice_id'] for t in sale_txs]
                        sel_inv = st.selectbox("Select Invoice", inv_ids)
                        if st.button("Generate PDF"):
                            inv_data = next(t for t in sale_txs if t['invoice_id'] == sel_inv)
                            items = run_query(f"SELECT * FROM invoice_items WHERE invoice_id='{sel_inv}'", fetch=True)
                            pdf = generate_pdf(inv_data, items, cust)
                            st.download_button("Download", pdf, f"{sel_inv}.pdf", "application/pdf")
                else: st.info("No history")

if __name__ == "__main__":
    main()
