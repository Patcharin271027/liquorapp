import streamlit as st
import pandas as pd
from st_supabase_connection import SupabaseConnection
import plotly.express as px
from datetime import datetime, date

# 1. ตั้งค่าหน้าจอ
st.set_page_config(layout="wide", page_title="ระบบจัดการยอดซื้อบ้านลุงทอม")

# 2. เชื่อมต่อ Supabase
conn = st.connection("supabase", type=SupabaseConnection)

# --- แถบด้านซ้าย (Sidebar): จัดการรายชื่อผ่าน Cloud ---
with st.sidebar:
    st.header("⚙️ ตั้งค่าระบบ")
    
    # ดึงข้อมูลรายชื่อจาก Cloud
    hotels = [i['name'] for i in conn.table("config_hotels").select("name").execute().data]
    suppliers = [i['name'] for i in conn.table("config_suppliers").select("name").execute().data]

    with st.expander("🏢 จัดการโรงแรม"):
        new_h = st.text_input("ชื่อโรงแรมใหม่")
        if st.button("เพิ่มโรงแรม"):
            conn.table("config_hotels").insert({"name": new_h}).execute()
            st.rerun()

    with st.expander("🚚 จัดการ Supplier"):
        new_s = st.text_input("ชื่อ Supplier ใหม่")
        if st.button("เพิ่ม Supplier"):
            conn.table("config_suppliers").insert({"name": new_s}).execute()
            st.rerun()

# --- ส่วนหลัก: บันทึกข้อมูล ---
st.title("🥃 ระบบบันทึกยอดซื้อ (Cloud Version)")

with st.form("main_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    sup_val = col1.selectbox("เลือก Supplier", suppliers)
    hotel_val = col1.selectbox("เลือกโรงแรม", hotels)
    date_val = col2.date_input("วันที่ซื้อ", date.today())
    amount_val = col2.number_input("ยอดเงิน (บาท)", min_value=0.0)
    uploaded_file = st.file_uploader("แนบบิล", type=['pdf', 'jpg', 'png', 'jpeg'])
    
    if st.form_submit_button("บันทึกข้อมูล"):
        file_url = ""
        if uploaded_file:
            # อัปโหลดไฟล์ไปที่ Supabase Storage
            file_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}"
            # อัปโหลดไปที่ bucket ชื่อ 'liquor_attachments'
            conn.storage.from_("liquor_attachments").upload(file_name, uploaded_file.getvalue())
            # ดึง URL ของไฟล์ออกมา
            file_url = conn.storage.from_("liquor_attachments").get_public_url(file_name)
        
        # บันทึกข้อมูลลงตาราง
        conn.table("spirit_sales").insert({
            "supplier": sup_val, "hotel": hotel_val, 
            "sale_date": str(date_val), "amount": amount_val, "file_url": file_url
        }).execute()
        st.success("✅ บันทึกข้อมูลและไฟล์ลง Cloud เรียบร้อย!")
        st.rerun()

# --- ส่วนรายงาน ---
st.divider()
res = conn.table("spirit_sales").select("*").execute()
df = pd.DataFrame(res.data)

if not df.empty:
    df['sale_date'] = pd.to_datetime(df['sale_date'])
    st.subheader("📊 รายงานสรุปยอดซื้อ")
    st.dataframe(df, use_container_width=True)
    
    # เพิ่มปุ่มดูไฟล์แนบ
    for i, row in df.iterrows():
        if row['file_url']:
            st.link_button(f"🔗 ดูบิลรายการที่ {row['id']}", row['file_url'])

