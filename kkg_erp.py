import streamlit as st
import pandas as pd
import datetime
import time
from fpdf import FPDF
import os

# ==========================================
# 1. DATABASE ADAPTER (Hybrid)
# ==========================================
class DBHandler:
    def __init__(self):
        # Check if running on Cloud
        if "postgres" in st.secrets:
            self.type = "POSTGRES"
            import psycopg2
            self.lib = psycopg2
            self.dsn = st.secrets["postgres"]["url"]
        else:
            self.type = "SQLITE"
            import sqlite3
            self.lib = sqlite3
            self.db_file = "kkg_database.sqlite"

    def get_conn(self):
        try:
            if self.type == "POSTGRES":
                return self.lib.connect(self.dsn)
            else:
                return self.lib.connect(self.db_file, check_same_thread=False)
        except Exception as e:
            st.error(f"Database Connection Failed: {e}")
            st.stop()

    def run_query(self, query, params=None, fetch=False):
        conn = self.get_conn()
        if self.type == "POSTGRES":
            query = query.replace('?', '%s')
            
        try:
            if self.type == "SQLITE":
                conn.row_factory = self.lib.Row
                cur = conn.cursor()
            else:
                cur = conn.cursor()
                
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            
            if fetch:
                cols = [desc[0] for desc in cur.description]
                res = [dict(zip(cols, row)) for row in cur.fetchall()]
                conn.close()
                return res
            else:
                conn.commit()
                conn.close()
                return True
        except Exception as e:
            conn.close()
            st.error(f"DB Query Error: {e}")
            return [] if fetch else False

db = DBHandler()

# ==========================================
# 2. INITIALIZATION
# ==========================================
def init_db_tables():
    pk_def = "SERIAL PRIMARY KEY" if db.type == "POSTGRES" else "INTEGER PRIMARY KEY AUTOINCREMENT"
    queries = [
        f'''CREATE TABLE IF NOT EXISTS products (id {pk_def}, name TEXT, category TEXT, price REAL, stock INTEGER)''',
        '''CREATE TABLE IF NOT EXISTS customers (phone TEXT PRIMARY KEY, name TEXT, address TEXT, joined_date TEXT)''',
        '''CREATE TABLE IF NOT EXISTS transactions (invoice_id TEXT PRIMARY KEY, customer_phone TEXT, date TEXT, type TEXT, total_amount REAL, paid_amount REAL, due_amount REAL, payment_mode TEXT, notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''',
        f'''CREATE TABLE IF NOT EXISTS invoice_items (id {pk_def}, invoice_id TEXT, product_name TEXT, quantity INTEGER, unit_price REAL, total_price REAL)'''
    ]
    for q in queries:
        db.run_query(q)

init_db_tables()

# ==========================================
# 3. VISUAL CONFIG & UTILS
# ==========================================
st.set_page_config(page_title="KKG ERP", page_icon="🚜", layout="wide")
BUSINESS_INFO = {"name": "KISAN KHIDMAT GHAR", "address": "Chakoora, Pulwama, J&K", "phone": "+91 9906XXXXXX"}

st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; font-family: 'Inter', sans-serif; }
    [data-testid="stSidebar"] { background-color: #0f172a; border-right: 1px solid #1e293b; }
    [data-testid="stSidebar"] * { color: #f8fafc !important; }
    div[data-testid="stMetric"] { background-color: white; border: 1px solid #e2e8f0; padding: 20px; border-radius: 12px; }
    [data-testid="stMetricValue"] { color: #0f172a !important; font-weight: 700; }
    .stButton button { background-color: #2563eb; color: white !important; font-weight: 600; border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 18)
        self.cell(0, 10, BUSINESS_INFO['name'], 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.cell(0, 5, BUSINESS_INFO['address'], 0, 1, 'C')
        self.cell(0, 5, BUSINESS_INFO['phone'], 0, 1, 'C')
        self.ln(10)
        self.line(10, 35, 200, 35)

def generate_invoice_pdf(tx_data, items, cust_data):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, "INVOICE", 0, 1, 'C')
    pdf.ln(5)
    
    pdf.set_font('Arial', '', 10)
    pdf.cell(100, 5, f"Bill To: {cust_data['name']}", 0, 0)
    pdf.cell(90, 5, f"Invoice #: {tx_data['invoice_id']}", 0, 1, 'R')
    pdf.cell(100, 5, f"Phone: {cust_data['phone']}", 0, 0)
    pdf.cell(90, 5, f"Date: {tx_data['date']}", 0, 1, 'R')
    pdf.ln(10)
    
    pdf.set_fill_color(241, 245, 249)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(90, 10, 'Item', 1, 0, 'L', 1)
    pdf.cell(30, 10, 'Rate', 1, 0, 'R', 1)
    pdf.cell(30, 10, 'Qty', 1, 0, 'C', 1)
    pdf.cell(40, 10, 'Total', 1, 1, 'R', 1)
    
    pdf.set_font('Arial', '', 10)
    for item in items:
        name = item.get('product_name') or item.get('name') or "Unknown"
        price = float(item.get('unit_price') or item.get('price') or 0)
        qty = int(item.get('quantity') or item.get('qty') or 0)
        total = float(item.get('total_price') or item.get('total') or 0)
        pdf.cell(90, 10, str(name), 1, 0, 'L')
        pdf.cell(30, 10, f"{price:.0f}", 1, 0, 'R')
        pdf.cell(30, 10, str(qty), 1, 0, 'C')
        pdf.cell(40, 10, f"{total:.0f}", 1, 1, 'R')
    
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(150, 10, 'Grand Total', 0, 0, 'R')
    pdf.cell(40, 10, f"Rs {tx_data['total_amount']:.0f}", 1, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 4. APP UI
# ==========================================
def main():
    st.sidebar.markdown("""<div style='text-align: center; padding: 20px;'><h1>🚜 KKG ERP</h1></div>""", unsafe_allow_html=True)
    menu = st.sidebar.radio("Navigation", ["Dashboard", "Billing (POS)", "Inventory", "Customers", "Ledger"])

    # --- DASHBOARD ---
    if menu == "Dashboard":
        st.title("Executive Dashboard")
        today = datetime.date.today().isoformat()
        
        try:
            res_sales = db.run_query("SELECT SUM(total_amount) as v FROM transactions WHERE date=? AND type='SALE'", (today,), fetch=True)
            sales = res_sales[0]['v'] if res_sales and res_sales[0]['v'] else 0
            
            res_tot = db.run_query("SELECT SUM(total_amount) as v FROM transactions WHERE type='SALE'", fetch=True)
            tot_sales = res_tot[0]['v'] if res_tot and res_tot[0]['v'] else 0
            
            res_paid = db.run_query("SELECT SUM(paid_amount) as v FROM transactions", fetch=True)
            tot_paid = res_paid[0]['v'] if res_paid and res_paid[0]['v'] else 0
            
            res_stock = db.run_query("SELECT COUNT(*) as c FROM products WHERE stock < 5", fetch=True)
            low_stock = res_stock[0]['c'] if res_stock and res_stock[0]['c'] else 0
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Today's Sales", f"₹{sales:,.0f}")
            c2.metric("Market Receivables", f"₹{tot_sales - tot_paid:,.0f}")
            c3.metric("Low Stock Alerts", f"{low_stock}")
        except:
            st.info("System initialized. Please add customers and products.")

    # --- INVENTORY ---
    elif menu == "Inventory":
        st.title("📦 Inventory")
        with st.expander("Add Product"):
            with st.form("add"):
                n = st.text_input("Name"); p = st.number_input("Price", min_value=0.0); s = st.number_input("Stock", min_value=0)
                if st.form_submit_button("Save"):
                    db.run_query("INSERT INTO products (name, price, stock) VALUES (?,?,?)", (n,p,s))
                    st.success("Saved"); st.rerun()
        
        prods = db.run_query("SELECT * FROM products", fetch=True)
        if prods:
            df = pd.DataFrame(prods)
            for i, r in df.iterrows():
                c1, c2, c3, c4 = st.columns([2,1,1,1])
                c1.write(f"**{r['name']}**")
                c2.write(f"₹{r['price']}")
                c3.write(f"{r['stock']}")
                if c4.button("Delete", key=f"d_{r['id']}"):
                    db.run_query("DELETE FROM products WHERE id=?", (r['id'],))
                    st.rerun()
        else:
            st.warning("No products found.")

    # --- CUSTOMERS ---
    elif menu == "Customers":
        st.title("👥 Customers")
        with st.expander("Register Customer"):
            with st.form("cust"):
                n = st.text_input("Name"); p = st.text_input("Phone"); a = st.text_input("Address")
                if st.form_submit_button("Save"):
                    if db.run_query("INSERT INTO customers VALUES (?,?,?,?)", (p,n,a,str(datetime.date.today()))):
                        st.success("Saved"); st.rerun()
                    else: st.error("Phone exists")
        
        custs = db.run_query("SELECT * FROM customers", fetch=True)
        if custs:
            df = pd.DataFrame(custs)
            for i, r in df.iterrows():
                c1, c2, c3 = st.columns([2,2,1])
                c1.write(r['name']); c2.write(r['phone'])
                if c3.button("Delete", key=f"dc_{r['phone']}"):
                    db.run_query("DELETE FROM customers WHERE phone=?", (r['phone'],)); st.rerun()
        else:
            st.warning("No customers found.")

    # --- BILLING ---
    elif menu == "Billing (POS)":
        st.title("🛒 POS")
        custs = db.run_query("SELECT * FROM customers", fetch=True)
        prods = db.run_query("SELECT * FROM products", fetch=True)
        
        if not custs or not prods: st.warning("Add Customers & Inventory first"); st.stop()
        
        c1, c2 = st.columns([1.5, 1])
        with c1:
            # Dropdowns
            c_idx = st.selectbox("Customer", range(len(custs)), format_func=lambda x: f"{custs[x]['name']} ({custs[x]['phone']})")
            sel_cust = custs[c_idx]
            
            p_idx = st.selectbox("Product", range(len(prods)), format_func=lambda x: f"{prods[x]['name']} (₹{prods[x]['price']})")
            sel_prod = prods[p_idx]
            
            qty = st.number_input("Qty", min_value=1, value=1)
            
            if 'cart' not in st.session_state: st.session_state.cart = []
            
            if st.button("Add"):
                item = dict(sel_prod)
                item['qty'] = qty
                item['total'] = qty * sel_prod['price']
                st.session_state.cart.append(item)
        
        with c2:
            st.subheader("Cart")
            if st.session_state.cart:
                df = pd.DataFrame(st.session_state.cart)
                st.dataframe(df[['name', 'qty', 'total']], use_container_width=True)
                
                total = df['total'].sum()
                st.markdown(f"### Total: ₹{total:,.0f}")
                paid = st.number_input("Paid", value=0.0)
                
                if st.button("Confirm Sale", type="primary"):
                    inv_id = f"INV-{int(time.time())}"
                    due = total - paid
                    
                    db.run_query("INSERT INTO transactions (invoice_id, customer_phone, date, type, total_amount, paid_amount, due_amount) VALUES (?,?,?,?,?,?,?)",
                                 (inv_id, sel_cust['phone'], str(datetime.date.today()), 'SALE', total, paid, due))
                    
                    for item in st.session_state.cart:
                        db.run_query("INSERT INTO invoice_items (invoice_id, product_name, quantity, unit_price, total_price) VALUES (?,?,?,?,?)",
                                     (inv_id, item['name'], item['qty'], item['price'], item['total']))
                    
                    st.session_state.pdf = generate_invoice_pdf({'invoice_id': inv_id, 'date': str(datetime.date.today()), 'total_amount': total, 'paid_amount': paid, 'due_amount': due}, st.session_state.cart, sel_cust)
                    st.session_state.cart = []
                    st.rerun()
            
            if 'pdf' in st.session_state:
                st.success("Done!")
                st.download_button("Download Bill", st.session_state.pdf, "bill.pdf", "application/pdf")

    # --- LEDGER ---
    elif menu == "Ledger":
        st.title("📖 Ledger")
        custs = db.run_query("SELECT * FROM customers", fetch=True)
        
        # SAFETY CHECK FOR EMPTY DB
        if not custs:
            st.warning("No customers found. Go to 'Customers' tab to register one.")
            st.stop() # Prevents the crash
            
        c_idx = st.selectbox("Customer", range(len(custs)), format_func=lambda x: custs[x]['name'])
        sel_cust = custs[c_idx]
        
        txs = db.run_query("SELECT * FROM transactions WHERE customer_phone=? ORDER BY created_at DESC", (sel_cust['phone'],), fetch=True)
        if txs:
            st.dataframe(pd.DataFrame(txs)[['date', 'invoice_id', 'total_amount', 'paid_amount', 'due_amount']])
        else:
            st.info("No history.")

if __name__ == "__main__":
    main()
