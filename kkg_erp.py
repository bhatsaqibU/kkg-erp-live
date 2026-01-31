import streamlit as st
import pandas as pd
import sqlite3
import datetime
import time
from fpdf import FPDF

# ==========================================
# 1. VISUAL DESIGN ENGINE (Platinum UI)
# ==========================================
st.set_page_config(page_title="KKG ERP", page_icon="🚜", layout="wide")

# This CSS exactly mimics the React Design you liked
st.markdown("""
    <style>
    /* 1. Main Background */
    .stApp {
        background-color: #f8fafc; /* Slate-50 */
        font-family: 'Inter', sans-serif;
    }

    /* 2. Sidebar Styling (Deep Navy) */
    [data-testid="stSidebar"] {
        background-color: #0f172a; /* Slate-900 */
        border-right: 1px solid #1e293b;
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] p {
        color: #f8fafc !important;
    }
    [data-testid="stRadio"] label {
        color: #94a3b8 !important; /* Slate-400 */
        font-weight: 500;
        padding: 10px;
        border-radius: 6px;
        transition: all 0.2s;
    }
    [data-testid="stRadio"] label:hover {
        background-color: #1e293b;
        color: white !important;
    }
    /* Active Menu Item (Bright Blue) */
    div[role="radiogroup"] > label[data-checked="true"] {
        background-color: #2563eb !important; /* Blue-600 */
        color: white !important;
        font-weight: 600;
    }

    /* 3. Cards & Metrics */
    div[data-testid="stMetric"], div.css-1r6slb0 {
        background-color: white !important;
        border: 1px solid #e2e8f0;
        padding: 24px !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    [data-testid="stMetricLabel"] p {
        color: #64748b !important; /* Slate-500 */
        font-size: 13px !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    [data-testid="stMetricValue"] div {
        color: #0f172a !important; /* Slate-900 */
        font-size: 30px !important;
        font-weight: 700 !important;
    }

    /* 4. Tables & Lists */
    .row-widget {
        background-color: white;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .row-header {
        background-color: #f1f5f9;
        padding: 15px;
        border-radius: 8px 8px 0 0;
        border: 1px solid #e2e8f0;
        border-bottom: none;
        font-weight: 600;
        color: #475569;
    }

    /* 5. Inputs & Buttons */
    .stTextInput input, .stNumberInput input, .stSelectbox select {
        border-radius: 8px;
        border: 1px solid #cbd5e1;
        padding: 10px;
    }
    .stButton button {
        background-color: #2563eb;
        color: white !important;
        border-radius: 8px;
        border: none;
        padding: 0.6rem 1.2rem;
        font-weight: 600;
        box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2);
    }
    .stButton button:hover {
        background-color: #1d4ed8;
    }
    /* Danger Button Styling */
    button[kind="secondary"] {
        background-color: #fee2e2 !important;
        color: #ef4444 !important;
        border: 1px solid #fecaca !important;
    }
    button[kind="secondary"]:hover {
        background-color: #fecaca !important;
    }
    </style>
""", unsafe_allow_html=True)

# Config
BUSINESS_INFO = {"name": "KISAN KHIDMAT GHAR", "address": "Chakoora, Pulwama, J&K", "phone": "+91 9906XXXXXX"}
DB_FILE = "kkg_database.sqlite"

# ==========================================
# 2. PDF ENGINE (Robust Version)
# ==========================================
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
    
    # Info Block
    pdf.set_font('Arial', '', 10)
    pdf.cell(100, 5, f"Bill To: {cust_data['name']}", 0, 0)
    pdf.cell(90, 5, f"Invoice #: {tx_data['invoice_id']}", 0, 1, 'R')
    pdf.cell(100, 5, f"Phone: {cust_data['phone']}", 0, 0)
    pdf.cell(90, 5, f"Date: {tx_data['date']}", 0, 1, 'R')
    pdf.ln(10)
    
    # Table
    pdf.set_fill_color(241, 245, 249) # Slate-100
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(90, 10, 'Item', 1, 0, 'L', 1)
    pdf.cell(30, 10, 'Rate', 1, 0, 'R', 1)
    pdf.cell(30, 10, 'Qty', 1, 0, 'C', 1)
    pdf.cell(40, 10, 'Total', 1, 1, 'R', 1)
    
    pdf.set_font('Arial', '', 10)
    for item in items:
        # Robust handling for different data structures (Cart vs DB)
        # 1. Product Name
        name = "Unknown"
        if isinstance(item, dict):
            name = item.get('product_name') or item.get('name') or "Unknown"
        else: # Access by attribute/column if row object
            name = getattr(item, 'product_name', getattr(item, 'name', "Unknown"))

        # 2. Price/Rate
        price = 0.0
        if isinstance(item, dict):
            price = item.get('unit_price') or item.get('price') or 0.0
        else:
            price = getattr(item, 'unit_price', getattr(item, 'price', 0.0))

        # 3. Quantity
        qty = 0
        if isinstance(item, dict):
            qty = item.get('quantity') or item.get('qty') or 0
        else:
            qty = getattr(item, 'quantity', getattr(item, 'qty', 0))

        # 4. Total
        total = 0.0
        if isinstance(item, dict):
            total = item.get('total_price') or item.get('total') or 0.0
        else:
            total = getattr(item, 'total_price', getattr(item, 'total', 0.0))
        
        # Ensure numeric values
        try: price = float(price) 
        except: price = 0.0
        try: total = float(total)
        except: total = 0.0

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
# 3. DATABASE
# ==========================================
def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, category TEXT, price REAL, stock INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS customers (phone TEXT PRIMARY KEY, name TEXT, address TEXT, joined_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (invoice_id TEXT PRIMARY KEY, customer_phone TEXT, date TEXT, type TEXT, total_amount REAL, paid_amount REAL, due_amount REAL, payment_mode TEXT, notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS invoice_items (id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_id TEXT, product_name TEXT, quantity INTEGER, unit_price REAL, total_price REAL)''')
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 4. MAIN APP
# ==========================================
def main():
    # Styled Sidebar Header
    st.sidebar.markdown("""
        <div style='text-align: center; padding: 20px 0;'>
            <div style='font-size: 3rem;'>🚜</div>
            <h2 style='color: white; margin: 0;'>KKG ERP</h2>
            <p style='color: #64748b; font-size: 0.8rem;'>Platinum Edition</p>
        </div>
    """, unsafe_allow_html=True)
    
    menu = st.sidebar.radio("Navigation", ["Dashboard", "Billing (POS)", "Inventory", "Customers", "Ledger"], label_visibility="collapsed")

    # --- DASHBOARD ---
    if menu == "Dashboard":
        st.title("Executive Dashboard")
        conn = get_db()
        today = datetime.date.today().isoformat()
        
        # Metrics
        sales = pd.read_sql(f"SELECT SUM(total_amount) as v FROM transactions WHERE date='{today}' AND type='SALE'", conn).iloc[0]['v'] or 0
        receivables = (pd.read_sql("SELECT SUM(total_amount) as v FROM transactions WHERE type='SALE'", conn).iloc[0]['v'] or 0) - \
                      (pd.read_sql("SELECT SUM(paid_amount) as v FROM transactions", conn).iloc[0]['v'] or 0)
        low_stock = pd.read_sql("SELECT COUNT(*) as c FROM products WHERE stock < 5", conn).iloc[0]['c']
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Today's Sales", f"₹{sales:,.0f}")
        c2.metric("Market Receivables", f"₹{receivables:,.0f}")
        c3.metric("Low Stock Alerts", f"{low_stock}")
        
        # Graphs
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.markdown("### 📈 Sales Trend")
            trend = pd.read_sql("SELECT date, SUM(total_amount) as sales FROM transactions WHERE type='SALE' GROUP BY date ORDER BY date DESC LIMIT 7", conn)
            if not trend.empty:
                st.line_chart(trend.set_index('date'), height=250)
            else:
                st.info("No data yet")
                
        with col_g2:
            st.markdown("### 🏆 Top Products")
            top = pd.read_sql("SELECT product_name, SUM(quantity) as qty FROM invoice_items GROUP BY product_name ORDER BY qty DESC LIMIT 5", conn)
            if not top.empty:
                st.bar_chart(top.set_index('product_name'), height=250)
            else:
                st.info("No data yet")

    # --- INVENTORY (Bulk Delete Enhanced) ---
    elif menu == "Inventory":
        st.title("📦 Inventory Management")
        
        with st.expander("➕ Add New Product", expanded=False):
            with st.form("add_p"):
                c1, c2, c3 = st.columns(3)
                n = c1.text_input("Name")
                p = c2.number_input("Price (₹)", min_value=0.0)
                s = c3.number_input("Stock Qty", min_value=0)
                if st.form_submit_button("Save Product"):
                    conn = get_db()
                    conn.execute("INSERT INTO products (name, price, stock) VALUES (?,?,?)", (n,p,s))
                    conn.commit()
                    conn.close()
                    st.success(f"Added {n}")
                    st.rerun()

        conn = get_db()
        products = pd.read_sql("SELECT * FROM products", conn)
        conn.close()

        if not products.empty:
            # Table Header
            st.markdown("""
            <div class="row-header" style="display: flex;">
                <div style="flex: 0.5;">Sel</div>
                <div style="flex: 2;">Name</div>
                <div style="flex: 1;">Price</div>
                <div style="flex: 1;">Stock</div>
            </div>
            """, unsafe_allow_html=True)
            
            selected_ids = []
            
            for _, row in products.iterrows():
                c_sel, c1, c2, c3 = st.columns([0.5, 2, 1, 1])
                with c_sel:
                    if st.checkbox("", key=f"sel_{row['id']}"):
                        selected_ids.append(row['id'])
                with c1: st.write(f"**{row['name']}**")
                with c2: st.write(f"₹{row['price']}")
                with c3: 
                    color = "red" if row['stock'] < 5 else "green"
                    st.markdown(f"<span style='color:{color}; font-weight:bold'>{row['stock']}</span>", unsafe_allow_html=True)
                st.markdown("<hr style='margin: 0; border-top: 1px solid #f1f5f9;'>", unsafe_allow_html=True)
            
            if selected_ids:
                st.write("") # Spacer
                if st.button(f"🗑️ Delete Selected ({len(selected_ids)})", type="primary"):
                    conn = get_db()
                    for pid in selected_ids:
                        conn.execute("DELETE FROM products WHERE id=?", (pid,))
                    conn.commit()
                    conn.close()
                    st.success("Deleted successfully!")
                    time.sleep(0.5)
                    st.rerun()

    # --- CUSTOMERS (Bulk Delete Enhanced) ---
    elif menu == "Customers":
        st.title("👥 Customer Management")
        
        with st.expander("➕ Register Customer", expanded=False):
            with st.form("add_c"):
                n = st.text_input("Name")
                ph = st.text_input("Phone (ID)")
                loc = st.text_input("Address")
                if st.form_submit_button("Register"):
                    conn = get_db()
                    try:
                        conn.execute("INSERT INTO customers VALUES (?,?,?,?)", (ph, n, loc, datetime.date.today()))
                        conn.commit()
                        st.success("Saved")
                        st.rerun()
                    except: st.error("Phone exists")
                    conn.close()

        conn = get_db()
        custs = pd.read_sql("SELECT * FROM customers", conn)
        conn.close()

        if not custs.empty:
            st.markdown("""
            <div class="row-header" style="display: flex;">
                <div style="flex: 0.5;">Sel</div>
                <div style="flex: 2;">Name</div>
                <div style="flex: 2;">Phone</div>
                <div style="flex: 2;">Address</div>
            </div>
            """, unsafe_allow_html=True)
            
            selected_phones = []
            
            for _, row in custs.iterrows():
                c_sel, c1, c2, c3 = st.columns([0.5, 2, 2, 2])
                with c_sel:
                    if st.checkbox("", key=f"sel_c_{row['phone']}"):
                        selected_phones.append(row['phone'])
                with c1: st.write(f"**{row['name']}**")
                with c2: st.write(f"{row['phone']}")
                with c3: st.write(f"{row['address']}")
                st.markdown("<hr style='margin: 0; border-top: 1px solid #f1f5f9;'>", unsafe_allow_html=True)
                
            if selected_phones:
                st.write("")
                if st.button(f"🗑️ Delete Selected Customers ({len(selected_phones)})", type="primary"):
                    conn = get_db()
                    deleted_count = 0
                    blocked_count = 0
                    
                    for phone in selected_phones:
                        # Safety check
                        tx_count = pd.read_sql(f"SELECT count(*) as c FROM transactions WHERE customer_phone='{phone}'", conn).iloc[0]['c']
                        if tx_count > 0:
                            blocked_count += 1
                        else:
                            conn.execute("DELETE FROM customers WHERE phone=?", (phone,))
                            deleted_count += 1
                            
                    conn.commit()
                    conn.close()
                    
                    msg = f"Deleted {deleted_count} customers."
                    if blocked_count > 0:
                        msg += f" (Skipped {blocked_count} due to existing transactions)."
                    
                    if blocked_count > 0: st.warning(msg)
                    else: st.success(msg)
                    
                    time.sleep(1)
                    st.rerun()

    # --- POS (Billing) ---
    elif menu == "Billing (POS)":
        st.title("🛒 Point of Sale")
        conn = get_db()
        cust_df = pd.read_sql("SELECT * FROM customers", conn)
        inv_df = pd.read_sql("SELECT * FROM products", conn)
        conn.close()

        if cust_df.empty or inv_df.empty:
            st.warning("Setup Inventory & Customers first.")
            return

        c1, c2 = st.columns([1.5, 1])
        with c1:
            st.markdown("### Select Items")
            cust_list = cust_df['name'] + " (" + cust_df['phone'] + ")"
            sel_cust_str = st.selectbox("Select Customer", cust_list)
            sel_phone = sel_cust_str.split('(')[-1].strip(')')
            
            prod_opts = {f"{r['name']} (₹{r['price']} | Stock: {r['stock']})": r for _, r in inv_df.iterrows()}
            sel_prod_k = st.selectbox("Search Product", list(prod_opts.keys()))
            sel_prod = prod_opts[sel_prod_k]
            
            col_q, col_b = st.columns([1, 1])
            qty = col_q.number_input("Quantity", min_value=1, value=1)
            
            if 'cart' not in st.session_state: st.session_state.cart = []
            
            if col_b.button("Add to Bill"):
                # Stock Check Logic
                in_cart = sum(i['qty'] for i in st.session_state.cart if i['id'] == sel_prod['id'])
                if (in_cart + qty) > sel_prod['stock']:
                    st.error(f"❌ Stock Error! Only {sel_prod['stock']} available.")
                else:
                    item = sel_prod.to_dict()
                    item['qty'] = qty
                    item['total'] = qty * sel_prod['price']
                    st.session_state.cart.append(item)
                    st.success("Added")

        with c2:
            st.markdown("### Current Bill")
            if st.session_state.cart:
                cart_df = pd.DataFrame(st.session_state.cart)
                # Display Cart with Delete Option
                for idx, row in cart_df.iterrows():
                    cols = st.columns([3, 1, 1])
                    cols[0].write(f"{row['name']} x{row['qty']}")
                    cols[1].write(f"₹{row['total']}")
                    if cols[2].button("X", key=f"rm_{idx}", type="secondary"):
                        st.session_state.cart.pop(idx)
                        st.rerun()
                
                grand_total = cart_df['total'].sum() if not cart_df.empty else 0
                st.markdown(f"### Total: ₹{grand_total:,.0f}")
                
                paid = st.number_input("Paid Amount", value=0.0)
                if st.button("✅ FINALIZE SALE", type="primary"):
                    conn = get_db()
                    inv_id = f"INV-{int(time.time())}"
                    due = grand_total - paid
                    
                    conn.execute("INSERT INTO transactions (invoice_id, customer_phone, date, type, total_amount, paid_amount, due_amount) VALUES (?,?,?,?,?,?,?)",
                                 (inv_id, sel_phone, datetime.date.today(), 'SALE', grand_total, paid, due))
                    
                    for item in st.session_state.cart:
                        conn.execute("INSERT INTO invoice_items (invoice_id, product_name, quantity, unit_price, total_price) VALUES (?,?,?,?,?)",
                                     (inv_id, item['name'], item['qty'], item['price'], item['total']))
                        conn.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (item['qty'], item['id']))
                    
                    conn.commit()
                    conn.close()
                    
                    # Generate PDF
                    cust_data = cust_df[cust_df['phone'] == sel_phone].iloc[0]
                    tx_data = {'invoice_id': inv_id, 'date': datetime.date.today(), 'total_amount': grand_total, 'paid_amount': paid, 'due_amount': due}
                    st.session_state.last_pdf = generate_invoice_pdf(tx_data, st.session_state.cart, cust_data)
                    st.session_state.cart = []
                    st.rerun()

            if 'last_pdf' in st.session_state:
                st.success("Sale Saved!")
                st.download_button("🖨️ Download Bill PDF", st.session_state.last_pdf, "bill.pdf", "application/pdf")

    # --- LEDGER ---
    elif menu == "Ledger":
        st.title("📖 Ledger")
        conn = get_db()
        cust_df = pd.read_sql("SELECT * FROM customers", conn)
        
        sel_cust_str = st.selectbox("Search Customer", cust_df['name'] + " (" + cust_df['phone'] + ")")
        phone = sel_cust_str.split('(')[-1].strip(')')
        
        txs = pd.read_sql(f"SELECT * FROM transactions WHERE customer_phone='{phone}' ORDER BY created_at DESC", conn)
        
        if not txs.empty:
            bal = txs[txs['type']=='SALE']['total_amount'].sum() - txs['paid_amount'].sum()
            st.metric("Outstanding Due", f"₹{bal:,.0f}")
            
            st.dataframe(txs[['date', 'invoice_id', 'type', 'total_amount', 'paid_amount', 'due_amount']], use_container_width=True)
            
            st.markdown("### Reprint Invoice")
            sale_ids = txs[txs['type']=='SALE']['invoice_id']
            if not sale_ids.empty:
                sel_inv = st.selectbox("Select Invoice", sale_ids)
                if st.button("Download PDF"):
                    items = pd.read_sql(f"SELECT * FROM invoice_items WHERE invoice_id='{sel_inv}'", conn)
                    inv_d = txs[txs['invoice_id']==sel_inv].iloc[0]
                    c_d = cust_df[cust_df['phone']==phone].iloc[0]
                    # Convert items df to list of dicts for PDF function
                    items_list = items.to_dict('records')
                    pdf = generate_invoice_pdf(inv_d, items_list, c_d)
                    st.download_button("Download", pdf, f"{sel_inv}.pdf", "application/pdf")
        else:
            st.info("No history.")

if __name__ == "__main__":
    main()