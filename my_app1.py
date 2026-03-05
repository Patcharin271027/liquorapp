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
                    
                    # ส่วนจัดการไฟล์แนบ
                    if uploaded_file:
                        # --- เพิ่มบรรทัดนี้: สร้างชื่อไฟล์เพื่อป้องกัน Error NameError ---
                        # เราจะใช้ วันที่_เวลา_ชื่อไฟล์เดิม เพื่อให้ชื่อไม่ซ้ำและเป็นภาษาอังกฤษ
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        file_name = f"{timestamp}_{uploaded_file.name}"
                        
                        # 1. อัปโหลดไฟล์พร้อมระบุประเภท (Content-Type) เพื่อให้เปิดดูได้ปกติ
                        conn.storage.from_("liquor_attachments").upload(
                            file_name, 
                            uploaded_file.getvalue(), 
                            {"content-type": uploaded_file.type}
                        )
                        
                        # 2. ดึงลิงก์สาธารณะมาเก็บไว้
                        file_url = conn.storage.from_("liquor_attachments").get_public_url(file_name)
                    
                    # ส่วนบันทึกข้อมูลลงตาราง spirit_sales
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
