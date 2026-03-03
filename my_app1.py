import streamlit as st
import sqlite3
import pandas as pd
import os
import io
import plotly.express as px
from datetime import datetime, date, timedelta

# 1. ตั้งค่าหน้าจอ
st.set_page_config(layout="wide", page_title="ระบบจัดการยอดซื้อบ้านลุงทอม & แนบไฟล์")

# 2. เตรียมโฟลเดอร์เก็บไฟล์แนบ
UPLOAD_DIR = "liquor_attachments"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# 3. เชื่อมต่อฐานข้อมูล
conn = sqlite3.connect('spirit_sales_v2.db', check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS config_hotels (id INTEGER PRIMARY KEY, name TEXT UNIQUE)')
c.execute('CREATE TABLE IF NOT EXISTS config_suppliers (id INTEGER PRIMARY KEY, name TEXT UNIQUE)')
c.execute('''CREATE TABLE IF NOT EXISTS spirit_sales 
             (id INTEGER PRIMARY KEY, supplier TEXT, hotel TEXT, 
              sale_date DATE, amount REAL, file_path TEXT)''')
conn.commit()

# --- แถบด้านซ้าย (Sidebar): ตั้งค่าระบบ ---
with st.sidebar:
    st.header("⚙️ ตั้งค่าระบบ")
    hotels = pd.read_sql_query("SELECT name FROM config_hotels", conn)['name'].tolist()
    suppliers = pd.read_sql_query("SELECT name FROM config_suppliers", conn)['name'].tolist()

    with st.expander("🏢 จัดการรายชื่อโรงแรม"):
        new_hotel = st.text_input("ชื่อโรงแรมใหม่")
        if st.button("เพิ่มโรงแรม", use_container_width=True):
            if new_hotel:
                try:
                    c.execute("INSERT INTO config_hotels (name) VALUES (?)", (new_hotel.strip(),))
                    conn.commit()
                    st.rerun()
                except: st.warning("มีชื่อนี้อยู่แล้ว")
        if hotels:
            del_h = st.selectbox("เลือกโรงแรมที่จะลบ", [""] + hotels)
            if st.button("❌ ลบชื่อโรงแรม"):
                c.execute("DELETE FROM config_hotels WHERE name=?", (del_h,))
                conn.commit()
                st.rerun()

    with st.expander("🚚 จัดการรายชื่อ Supplier"):
        new_sup = st.text_input("ชื่อ Supplier ใหม่")
        if st.button("เพิ่ม Supplier", use_container_width=True):
            if new_sup:
                try:
                    c.execute("INSERT INTO config_suppliers (name) VALUES (?)", (new_sup.strip(),))
                    conn.commit()
                    st.rerun()
                except: st.warning("มีชื่อนี้อยู่แล้ว")
        if suppliers:
            del_s = st.selectbox("เลือก Supplier ที่จะลบ", [""] + suppliers)
            if st.button("❌ ลบชื่อ Supplier"):
                c.execute("DELETE FROM config_suppliers WHERE name=?", (del_s,))
                conn.commit()
                st.rerun()

# --- ส่วนหลัก: บันทึกข้อมูล ---
st.title("🥃 ระบบบันทึกยอดซื้อบ้านลุงทอม พร้อมแนบบิล")

with st.expander("📝 บันทึกยอดขายใหม่", expanded=True):
    with st.form("main_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        sup_val = col1.selectbox("เลือก Supplier", suppliers if suppliers else ["เพิ่มข้อมูลที่ Sidebar"])
        hotel_val = col1.selectbox("เลือกโรงแรม", hotels if hotels else ["เพิ่มข้อมูลที่ Sidebar"])
        date_val = col2.date_input("วันที่ขาย", date.today())
        amount_val = col2.number_input("ยอดเงินยอดขาย (บาท)", min_value=0.0, step=0.01)
        uploaded_file = st.file_uploader("แนบไฟล์ใบเสร็จ/รูปภาพ", type=['pdf', 'jpg', 'png', 'jpeg'])
        
        if st.form_submit_button("บันทึกข้อมูล"):
            if amount_val > 0 and hotel_val != "เพิ่มข้อมูลที่ Sidebar":
                file_path = ""
                if uploaded_file:
                    file_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}"
                    file_path = os.path.join(UPLOAD_DIR, file_name)
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                c.execute("INSERT INTO spirit_sales (supplier, hotel, sale_date, amount, file_path) VALUES (?,?,?,?,?)",
                          (sup_val, hotel_val, date_val.strftime('%Y-%m-%d'), amount_val, file_path))
                conn.commit()
                st.success("✅ บันทึกสำเร็จ!")
                st.rerun()

# --- ส่วนรายงาน: ตัวกรองช่วงวันที่ (เพิ่มใหม่ตามคำขอ) ---
st.divider()
st.subheader("📊 รายงานสรุปยอดขายและตัวกรองข้อมูล")

df_raw = pd.read_sql_query("SELECT * FROM spirit_sales", conn)

if not df_raw.empty:
    df_raw['sale_date'] = pd.to_datetime(df_raw['sale_date'])
    
    # --- ช่องเลือกวันที่เริ่มต้นและสิ้นสุด ---
    with st.container(border=True):
        st.write("🔍 **เลือกช่วงเวลาที่ต้องการดูรายการ**")
        f_col1, f_col2 = st.columns(2)
        start_date = f_col1.date_input("📅 วันที่เริ่มต้น", date.today().replace(day=1))
        end_date = f_col2.date_input("📅 วันที่สิ้นสุด", date.today())

    # กรองข้อมูลตามช่วงวันที่ที่เลือก
    mask = (df_raw['sale_date'].dt.date >= start_date) & (df_raw['sale_date'].dt.date <= end_date)
    df_filtered = df_raw.loc[mask].copy()

    if not df_filtered.empty:
        df_filtered['month_year'] = df_filtered['sale_date'].dt.strftime('%b-%y')

        # 1. ตาราง Pivot Table
        pivot = df_filtered.pivot_table(index=['supplier', 'hotel'], columns='month_year', 
                                        values='amount', aggfunc='sum', fill_value=0, margins=True, margins_name='TOTAL')
        st.dataframe(pivot, use_container_width=True)

        # 2. กราฟวงกลมและสรุปเปอร์เซ็นต์
        hotel_sum = df_filtered.groupby('hotel')['amount'].sum().reset_index()
        total_amt = hotel_sum['amount'].sum()
        hotel_sum['%'] = (hotel_sum['amount'] / total_amt * 100).round(2)

        c_stat, c_chart = st.columns([4, 6])
        with c_stat:
            st.write("**🏨 สรุปรายโรงแรม**")
            st.dataframe(hotel_sum.style.format({'amount': '{:,.2f}', '%': '{:.2f}%'}), hide_index=True)
            st.metric("ยอดรวมในช่วงเวลาที่เลือก", f"{total_amt:,.2f} บาท")
        
        with c_chart:
            fig = px.pie(hotel_sum, values='amount', names='hotel', title="สัดส่วนยอดขายในช่วงวันที่เลือก (%)",
                         hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            fig.update_traces(textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)

        # 3. จัดการข้อมูล (แก้ไข/ลบ)
        st.write("---")
        with st.expander("📁 ตรวจสอบ/แก้ไข/ลบ ข้อมูลในช่วงเวลานี้"):
            for i, row in df_filtered.iterrows():
                st.write(f"ID: {row['id']} | {row['supplier']} | {row['hotel']} | {row['amount']:,.2f} ฿ ({row['sale_date'].date()})")
                edit_c, dl_c, del_c = st.columns([2, 2, 2])
                
                with edit_c.popover("📝 แก้ไข"):
                    with st.form(f"edit_{row['id']}"):
                        new_val = st.number_input("ยอดใหม่", value=float(row['amount']))
                        if st.form_submit_button("บันทึก"):
                            c.execute("UPDATE spirit_sales SET amount=? WHERE id=?", (new_val, row['id']))
                            conn.commit()
                            st.rerun()

                if row['file_path'] and os.path.exists(row['file_path']):
                    with open(row['file_path'], "rb") as f:
                        dl_c.download_button(f"📥 ไฟล์ ID {row['id']}", f, file_name=os.path.basename(row['file_path']))
                
                if del_c.button(f"🗑️ ลบ ID {row['id']}", key=f"del_{row['id']}", type="primary"):
                    if row['file_path'] and os.path.exists(row['file_path']):
                        try: os.remove(row['file_path'])
                        except: pass
                    c.execute("DELETE FROM spirit_sales WHERE id=?", (row['id'],))
                    conn.commit()
                    st.rerun()
                st.divider()
    else:
        st.warning("⚠️ ไม่พบข้อมูลในช่วงวันที่เลือก")
else:
    st.info("ยังไม่มีข้อมูลในระบบ")

conn.close()