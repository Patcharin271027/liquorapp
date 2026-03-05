import streamlit as st
import pandas as pd
from st_supabase_connection import SupabaseConnection
from datetime import datetime, date
import plotly.express as px

# 1. ตั้งค่าหน้าจอ
st.set_page_config(layout="wide", page_title="ระบบจัดการยอดซื้อบ้านลุงทอม Cloud")

# 2. เชื่อมต่อ Cloud Database
try:
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

# --- ส่วนหลัก: บันทึกจำนวนขวดและแนบบิล ---
with st.expander("📝 บันทึกจำนวนขวดใหม่", expanded=True):
    if not hotels or not suppliers:
        st.info("💡 กรุณาเพิ่มรายชื่อโรงแรมและ Supplier ที่แถบด้านซ้ายก่อนนะคะ")
    else:
        with st.form("main_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            sup_val = col1.selectbox("เลือก Supplier", suppliers)
            hotel_val = col1.selectbox("เลือกโรงแรม", hotels)
            date_val = col2.date_input("วันที่ซื้อ", date.today())
            amount_val = col2.number_input("จำนวนขวด", min_value=0, step=1)
            uploaded_file = st.file_uploader("แนบบิล (JPG, PNG, PDF)", type=['pdf', 'jpg', 'png', 'jpeg'])
            
            if st.form_submit_button("บันทึกข้อมูล"):
                if amount_val > 0:
                    file_url = ""
                    if uploaded_file:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        file_name = f"{timestamp}_{uploaded_file.name}"
                        conn.storage.from_("liquor_attachments").upload(
                            file_name, uploaded_file.getvalue(), {"content-type": uploaded_file.type}
                        )
                        file_url = conn.storage.from_("liquor_attachments").get_public_url(file_name)
                    
                    conn.table("spirit_sales").insert({
                        "supplier": sup_val, "hotel": hotel_val, 
                        "sale_date": str(date_val), "amount": amount_val, "file_url": file_url
                    }).execute()
                    st.success("✅ บันทึกสำเร็จ!")
                    st.rerun()

# --- ส่วนรายงานและกราฟ ---
st.divider()
st.subheader("📊 รายงานสรุปและสัดส่วนการซื้อ")
try:
    res = conn.table("spirit_sales").select("*").execute()
    df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
    
    if not df.empty:
        df['sale_date'] = pd.to_datetime(df['sale_date'])
        
        # ส่วนตัวกรองวันที่
        with st.container(border=True):
            st.write("🔍 **ตัวกรองช่วงเวลา**")
            c1, c2 = st.columns(2)
            start_d = c1.date_input("เริ่มต้น", date.today().replace(day=1))
            end_d = c2.date_input("สิ้นสุด", date.today())
            
        mask = (df['sale_date'].dt.date >= start_d) & (df['sale_date'].dt.date <= end_d)
        df_filtered = df.loc[mask].copy()

        if not df_filtered.empty:
            # 1. กราฟวงกลม
            df_pie = df_filtered.groupby('hotel')['amount'].sum().reset_index()
            total_all = df_pie['amount'].sum()
            fig = px.pie(df_pie, values='amount', names='hotel', title='สัดส่วนการซื้อแยกตามโรงแรม (%)', hole=0.3)
            st.plotly_chart(fig, use_container_width=True)

            # 2. ตารางสรุปเปอร์เซ็นต์
            df_pie['สัดส่วน (%)'] = (df_pie['amount'] / total_all * 100).round(2)
            df_pie.columns = ['ชื่อโรงแรม', 'จำนวนขวดรวม', 'สัดส่วน (%)']
            st.write("📋 **สรุปยอดรวมและเปอร์เซ็นต์**")
            st.table(df_pie)
            st.info(f"✨ ยอดรวมขวดทั้งหมดในช่วงเวลานี้: {int(total_all)} ขวด")

            # 3. ตาราง Pivot (จัดเรียงเดือนอย่างถูกต้อง)
            df_filtered = df_filtered.sort_values('sale_date') # เรียงลำดับเวลาในข้อมูลดิบก่อน
            df_filtered['month_year'] = df_filtered['sale_date'].dt.strftime('%b-%y')
            
            # ใช้ Categorical เพื่อบังคับลำดับเดือนตามเวลาจริง ไม่ใช่ตัวอักษร
            month_order = df_filtered.sort_values('sale_date')['month_year'].unique()
            df_filtered['month_year'] = pd.Categorical(df_filtered['month_year'], categories=month_order, ordered=True)

            pivot = df_filtered.pivot_table(
                index=['supplier', 'hotel'], columns='month_year', 
                values='amount', aggfunc='sum', fill_value=0, 
                margins=True, margins_name='TOTAL', sort=False
            )
            st.write("📅 **รายงานสรุปรายเดือน (เรียงตามเวลา)**")
            st.dataframe(pivot.astype(int), use_container_width=True)

            # ส่วนจัดการไฟล์แนบ
            with st.expander("📝 ดูบิลแนบ และ จัดการข้อมูล"):
                for i, row in df_filtered.sort_values('sale_date', ascending=False).iterrows():
                    st.write(f"ID: {row['id']} | {row['hotel']} | {int(row['amount']):,} ขวด ({row['sale_date'].date()})")
                    c1, c2 = st.columns([2, 1])
                    if row['file_url']:
                        c1.link_button(f"🔗 ดูบิล ID {row['id']}", row['file_url'])
                    if c2.button(f"🗑️ ลบ ID {row['id']}", key=f"del_{row['id']}", type="primary"):
                        conn.table("spirit_sales").delete().eq("id", row['id']).execute()
                        st.rerun()
except:
    st.info("รอการบันทึกรายการแรก...")
