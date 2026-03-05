import streamlit as st
import pandas as pd
from st_supabase_connection import SupabaseConnection
import plotly.express as px
from datetime import datetime, date
import io

# 1. ตั้งค่าหน้าจอ
st.set_page_config(layout="wide", page_title="ระบบจัดการยอดซื้อบ้านลุงทอม Cloud")

# 2. เชื่อมต่อ Cloud Database (พร้อมระบบกันล่ม)
try:
    # แก้ไขบรรทัดนี้เพื่อให้รองรับทั้งฐานข้อมูลและถังเก็บไฟล์ค่ะ
    conn = st.connection("supabase", type=SupabaseConnection).client 
except Exception as e:
    st.error("❌ ไม่สามารถเชื่อมต่อฐานข้อมูลได้")
    st.info("กรุณาตรวจสอบว่าใส่ URL และ Key ของก้อนใหม่ในหน้า Secrets หรือยังนะคะ")
    st.stop()

st.title("🥃 ระบบบันทึกยอดซื้อบ้านลุงทอม (Cloud Version)")

# --- แถบด้านซ้าย (Sidebar): จัดการรายชื่อผ่าน Cloud ---
with st.sidebar:
    st.header("⚙️ ตั้งค่าระบบ")
    
    # ดึงข้อมูลรายชื่อจาก Cloud ก้อนใหม่
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
                        file_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}"
                        conn.storage.from_("liquor_attachments").upload(file_name, uploaded_file.getvalue())
                        file_url = conn.storage.from_("liquor_attachments").get_public_url(file_name)
                    
                    conn.table("spirit_sales").insert({
                        "supplier": sup_val, "hotel": hotel_val, 
                        "sale_date": str(date_val), "amount": amount_val, "file_url": file_url
                    }).execute()
                    st.success("✅ บันทึกสำเร็จ!")
                    st.rerun()

# --- ส่วนรายงาน: เรียงลำดับจากเดือนเก่าไปหาเดือนใหม่ ---
st.divider()
st.subheader("📊 รายงานสรุปยอดซื้อ")

try:
    res = conn.table("spirit_sales").select("*").execute()
    df = pd.DataFrame(res.data) if res.data else pd.DataFrame()

    if not df.empty:
        df['sale_date'] = pd.to_datetime(df['sale_date'])
        
        # กรองข้อมูลช่วงวันที่
        with st.container(border=True):
            st.write("🔍 **ตัวกรองช่วงเวลา**")
            c1, c2 = st.columns(2)
            start_d = c1.date_input("เริ่มต้น", date.today().replace(day=1))
            end_d = c2.date_input("สิ้นสุด", date.today())
            
        mask = (df['sale_date'].dt.date >= start_d) & (df['sale_date'].dt.date <= end_d)
        df_filtered = df.loc[mask].copy()

        if not df_filtered.empty:
            # 1. เรียงวันที่จากเก่าไปใหม่
            df_filtered = df_filtered.sort_values('sale_date')
            df_filtered['month_year'] = df_filtered['sale_date'].dt.strftime('%b-%y')
            
            # 2. สร้างตาราง Pivot สรุปผล
            pivot = df_filtered.pivot_table(index=['supplier', 'hotel'], 
                                            columns='month_year', values='amount', 
                                            aggfunc='sum', fill_value=0, margins=True, 
                                            margins_name='TOTAL', sort=False)
            
            st.dataframe(pivot, use_container_width=True)
            
            # 3. จัดการข้อมูลดิบและไฟล์แนบ
            with st.expander("📝 แก้ไข/ลบ และ ดูบิลแนบ"):
                for i, row in df_filtered.iterrows():
                    st.write(f"ID: {row['id']} | {row['supplier']} | {row['amount']:,.2f} ฿ ({row['sale_date'].date()})")
                    c_view, c_del = st.columns([2, 1])
                    if row['file_url']:
                        c_view.link_button(f"🔗 ดูบิล ID {row['id']}", row['file_url'])
                    if c_del.button(f"🗑️ ลบ ID {row['id']}", key=f"del_{row['id']}", type="primary"):
                        conn.table("spirit_sales").delete().eq("id", row['id']).execute()
                        st.rerun()
        else:
            st.warning("⚠️ ไม่พบข้อมูลในช่วงวันที่เลือก")
    else:
        st.info("ยังไม่มีข้อมูลในระบบ")
except:
    st.info("รอการบันทึกรายการแรก...")

