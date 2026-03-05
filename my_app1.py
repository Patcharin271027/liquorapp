import streamlit as st
import pandas as pd
from st_supabase_connection import SupabaseConnection
from datetime import datetime, date

# 1. ตั้งค่าหน้าจอ
st.set_page_config(layout="wide", page_title="ระบบจัดการยอดซื้อบ้านลุงทอม Cloud")

# 2. เชื่อมต่อ Cloud Database
try:
    # ใช้ .client เพื่อให้รองรับทั้ง Table และ Storage
    conn = st.connection("supabase", type=SupabaseConnection).client 
except Exception as e:
    st.error("❌ ไม่สามารถเชื่อมต่อฐานข้อมูลได้")
    st.stop()

st.title("🥃 ระบบบันทึกยอดซื้อบ้านลุงทอม (Cloud Version)")

# --- แถบด้านซ้าย (Sidebar): จัดการรายชื่อ ---
with st.sidebar:
    st.header("⚙️ ตั้งค่าระบบ")
    try:
        h_res = conn.table("config_hotels").select("name").execute()
        hotels = sorted([i['name'] for i in h_res.data]) if h_res.data else []
        s_res = conn.table("config_suppliers").select("name").execute()
        suppliers = sorted([i['name'] for i in s_res.data]) if s_res.data else []
    except:
        hotels, suppliers = [], []

    with st.expander("🏢 จัดการรายชื่อโรงแรม"):
        new_h = st.text_input("ชื่อโรงแรมใหม่", key="new_hotel")
        if st.button("เพิ่มโรงแรม", use_container_width=True):
            if new_h:
                conn.table("config_hotels").insert({"name": new_h.strip()}).execute()
                st.rerun()
        if hotels:
            h_to_del = st.selectbox("เลือกโรงแรมที่จะลบ", [""] + hotels)
            if st.button("❌ ลบชื่อโรงแรม"):
                conn.table("config_hotels").delete().eq("name", h_to_del).execute()
                st.rerun()

# --- ส่วนหลัก: บันทึกยอดซื้อและแนบบิล ---
with st.expander("📝 บันทึกยอดซื้อใหม่", expanded=True):
    if not hotels or not suppliers:
        st.info("💡 กรุณาเพิ่มรายชื่อโรงแรมและ Supplier ที่แถบด้านซ้ายก่อนนะคะ")
    else:
        with st.form("main_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            sup_val = col1.selectbox("เลือก Supplier", suppliers)
            hotel_val = col1.selectbox("เลือกโรงแรม", hotels)
            date_val = col2.date_input("วันที่ซื้อ", date.today())
            amount_val = col2.number_input("ยอดเงิน (บาท)", min_value=0.0, step=0.01)
            uploaded_file = st.file_uploader("แนบบิล (JPG, PNG, PDF)", type=['pdf', 'jpg', 'png', 'jpeg'])
            
            if st.form_submit_button("บันทึกข้อมูล"):
                if amount_val > 0:
                    file_url = ""
                    if uploaded_file:
                        # สร้างชื่อไฟล์ใหม่ด้วย timestamp ป้องกันชื่อซ้ำและภาษาไทย
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        file_name = f"{timestamp}_{uploaded_file.name}"
                        
                        # อัปโหลดพร้อมระบุประเภทไฟล์เพื่อให้เปิดดูได้ปกติ
                        conn.storage.from_("liquor_attachments").upload(
                            file_name, 
                            uploaded_file.getvalue(), 
                            {"content-type": uploaded_file.type}
                        )
                        file_url = conn.storage.from_("liquor_attachments").get_public_url(file_name)
                    
                    # บันทึกลงตาราง
                    conn.table("spirit_sales").insert({
                        "supplier": sup_val, "hotel": hotel_val, 
                        "sale_date": str(date_val), "amount": amount_val, "file_url": file_url
                    }).execute()
                    st.success("✅ บันทึกสำเร็จ!")
                    st.rerun()

# --- ส่วนรายงาน ---
st.divider()
st.subheader("📊 รายงานสรุปยอดซื้อ")
try:
    res = conn.table("spirit_sales").select("*").execute()
    df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
    if not df.empty:
        df['sale_date'] = pd.to_datetime(df['sale_date'])
        # ตาราง Pivot และปุ่มดูบิล/ลบข้อมูล
        st.dataframe(df.sort_values('sale_date'), use_container_width=True)
        for i, row in df.iterrows():
            if row['file_url']:
                st.link_button(f"🔗 ดูบิล ID {row['id']}", row['file_url'])
            if st.button(f"🗑️ ลบ ID {row['id']}", key=f"del_{row['id']}"):
                conn.table("spirit_sales").delete().eq("id", row['id']).execute()
                st.rerun()
except:
    st.info("รอการบันทึกรายการแรก...")
