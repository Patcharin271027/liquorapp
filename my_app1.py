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

# --- แถบด้านซ้าย (Sidebar): จัดการรายชื่อผ่าน Cloud ---
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
            h_to_del = st.selectbox("เลือกโรงแรมที่จะลบ", [""] + hotels, key="del_hotel")
            if st.button("❌ ลบชื่อโรงแรม"):
                conn.table("config_hotels").delete().eq("name", h_to_del).execute()
                st.rerun()

    with st.expander("🚚 จัดการรายชื่อ Supplier"):
        new_s = st.text_input("ชื่อ Supplier ใหม่", key="new_sup")
        if st.button("เพิ่ม Supplier", use_container_width=True):
            if new_s:
                conn.table("config_suppliers").insert({"name": new_s.strip()}).execute()
                st.rerun()
        if suppliers:
            s_to_del = st.selectbox("เลือก Supplier ที่จะลบ", [""] + suppliers, key="del_sup")
            if st.button("❌ ลบชื่อ Supplier"):
                conn.table("config_suppliers").delete().eq("name", s_to_del).execute()
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
                        # สร้างชื่อไฟล์ใหม่เพื่อป้องกันชื่อซ้ำและตัดปัญหาภาษาไทย
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        file_name = f"{timestamp}_{uploaded_file.name}"
                        
                        # อัปโหลดไฟล์พร้อมระบุประเภทเพื่อให้เปิดดูได้ปกติ
                        conn.storage.from_("liquor_attachments").upload(
                            file_name, 
                            uploaded_file.getvalue(), 
                            {"content-type": uploaded_file.type}
                        )
                        file_url = conn.storage.from_("liquor_attachments").get_public_url(file_name)
                    
                    # บันทึกข้อมูลลงฐานข้อมูล
                    conn.table("spirit_sales").insert({
                        "supplier": sup_val, 
                        "hotel": hotel_val, 
                        "sale_date": str(date_val), 
                        "amount": amount_val, 
                        "file_url": file_url
                    }).execute()
                    
                    st.success("✅ บันทึกสำเร็จ!")
                    st.rerun()
                else:
                    st.warning("⚠️ กรุณาใส่ยอดเงินที่มากกว่า 0 ค่ะ")

# --- ส่วนรายงาน ---
st.divider()
st.subheader("📊 รายงานสรุปยอดซื้อ")
try:
    res = conn.table("spirit_sales").select("*").execute()
    df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
    if not df.empty:
        df['sale_date'] = pd.to_datetime(df['sale_date'])
        # ตารางข้อมูลดิบ
        st.dataframe(df.sort_values('sale_date', ascending=False), use_container_width=True)
        
        # จัดการไฟล์แนบและปุ่มลบ
        with st.expander("📝 ดูบิลแนบ และ จัดการข้อมูล"):
            for i, row in df.iterrows():
                st.write(f"ID: {row['id']} | {row['hotel']} | {row['amount']:,.2f} ฿")
                c1, c2 = st.columns([2, 1])
                if row['file_url']:
                    c1.link_button(f"🔗 ดูบิล ID {row['id']}", row['file_url'])
                if c2.button(f"🗑️ ลบ ID {row['id']}", key=f"del_{row['id']}", type="primary"):
                    conn.table("spirit_sales").delete().eq("id", row['id']).execute()
                    st.rerun()
except:
    st.info("รอการบันทึกรายการแรก...")
