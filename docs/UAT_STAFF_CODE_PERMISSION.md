# UAT Staff Code Permission Checklist

เอกสารนี้ใช้ทดสอบ UAT หลังระบบ permission เปลี่ยนมาใช้ `staff_code` เป็น key หลัก

ขอบเขตการทดสอบ:
- CRM data อ่าน/เขียนจาก Neon PostgreSQL
- Supabase ใช้เฉพาะ Auth/Login
- ไม่ทดสอบ migration หรือ schema change
- ทดสอบบน environment ที่ deploy ล่าสุด

ข้อมูลทดสอบที่ควรเตรียม:
- บัญชี `EDITOR`
- บัญชีพนักงานที่มี `staff_code = SAIFON`
- ลูกค้าที่มี `crm_data_imports.staff_code = SAIFON`
- ลูกค้าที่มี `crm_data_imports.staff_code` เป็นของคนอื่น
- รายการสินค้ามากกว่า 1 SKU สำหรับทดสอบ Multi SKU

## 1. EDITOR: Customers Owner Assignment

### Checklist
- [ ] Login ด้วยบัญชี `EDITOR`
- [ ] เข้าเมนู Customers / ค้นหาลูกค้า
- [ ] ค้นหาลูกค้าหนึ่งรายการที่มีข้อมูลอยู่แล้ว
- [ ] กดดูประวัติหรือเปิดส่วนรายละเอียดลูกค้า
- [ ] เปลี่ยนผู้ดูแลจาก dropdown มอบหมายผู้ดูแล
- [ ] กดบันทึกผู้ดูแล
- [ ] ตรวจในหน้าเว็บว่า `owner` เปลี่ยนเป็นชื่อผู้ดูแลใหม่
- [ ] ตรวจใน Neon ว่า `staff_code` เปลี่ยนเป็นรหัสของผู้ดูแลใหม่พร้อมกัน
- [ ] ทดสอบ Export `.xlsx`
- [ ] ทดสอบ Update URL

### Expected Result
- EDITOR เห็นลูกค้าทั้งหมด
- Dropdown ผู้ดูแลแสดงชื่อพนักงานปกติ
- บันทึกผู้ดูแลสำเร็จโดยไม่เกิด `TypeError`
- `owner` และ `staff_code` เปลี่ยนพร้อมกัน
- Export ใช้งานได้เฉพาะ EDITOR
- Update URL ใช้งานได้เฉพาะ EDITOR

### Fail Action
- ถ้า dropdown error ให้ตรวจ `pages/customers.py` ว่ามี custom object เข้า `st.selectbox` หรือไม่
- ถ้า `owner` เปลี่ยนแต่ `staff_code` ไม่เปลี่ยน ให้หยุด UAT และตรวจ caller ของ `assign_owner_to_order_record`
- ถ้า Export หรือ Update URL เปิดให้ role อื่นใช้ได้ ให้ตรวจ permission policy ของ Customers

## 2. STAFF: SAIFON Visibility

### Checklist
- [ ] Login ด้วยบัญชีพนักงานที่ผูก `staff_code = SAIFON`
- [ ] เข้า Dashboard
- [ ] ตรวจ KPI และรายงานยอดขาย
- [ ] เข้า Follow-up
- [ ] ตรวจว่ารายการที่เห็นเป็นของ `SAIFON` เท่านั้น
- [ ] เปิด Customer Detail ของลูกค้า `SAIFON`
- [ ] เปิด Customer Detail ของลูกค้าคนอื่นผ่าน URL โดยตรง

### Expected Result
- Dashboard แสดงเฉพาะข้อมูล `staff_code = SAIFON`
- Follow-up แสดงเฉพาะข้อมูล `staff_code = SAIFON`
- Customer Detail ของ `SAIFON` เปิดได้
- Customer Detail ของคนอื่นต้องแสดงข้อความไม่มีสิทธิ์เข้าถึง
- ไม่มี fallback จาก `owner` หรือ `staff_name` มาเป็น permission key

### Fail Action
- ถ้า STAFF เห็นข้อมูลคนอื่น ให้หยุด UAT และตรวจ `_followup_staff_scope`, dashboard report scope, และ `customer_detail` guard
- ถ้า STAFF ไม่เห็นข้อมูลตัวเอง ให้ตรวจ `crm_user_roles.staff_code` และ `crm_data_imports.staff_code`
- ถ้าเปิด detail คนอื่นได้ ให้ตรวจ `pages/customer_detail.py`

## 3. Manual Order: STAFF Owner Lock and Multi SKU

### Checklist
- [ ] Login ด้วยบัญชี STAFF เช่น `SAIFON`
- [ ] เข้าเมนูเพิ่มคำสั่งซื้อ
- [ ] กรอกหมายเลขคำสั่งซื้อ
- [ ] กรอกชื่อลูกค้า
- [ ] กรอกเบอร์โทรอย่างน้อย 1 เบอร์
- [ ] เลือกสินค้า SKU แรก
- [ ] ระบุจำนวนและราคา
- [ ] เพิ่มสินค้า SKU ที่สอง
- [ ] ถ้าเลือก SKU เดิมและชื่อสินค้าเดิม ให้ตรวจว่า qty รวมกัน
- [ ] กดบันทึกคำสั่งซื้อ
- [ ] ตรวจ Neon ว่า record ที่สร้างมี `owner` เป็นชื่อของ STAFF คนนั้น
- [ ] ตรวจ Neon ว่า record ที่สร้างมี `staff_code = SAIFON`

### Expected Result
- STAFF ไม่สามารถเลือกผู้ดูแลคนอื่นได้
- ระบบล็อก owner/staff_code ตาม user ที่ login
- Multi SKU บันทึกเป็นหลาย row หรือรวม qty ตาม logic ปัจจุบัน
- Save success แล้ว form reset พร้อมกรอกคำสั่งซื้อใหม่
- ไม่มีการ derive `staff_code` จากชื่อ owner

### Fail Action
- ถ้า STAFF เลือก owner คนอื่นได้ ให้ตรวจ `ui/manual_order_ui.py`
- ถ้า `staff_code` ว่างหรือเป็นชื่อไทย ให้หยุด UAT และตรวจ Manual Order payload
- ถ้า Multi SKU พัง ให้ตรวจเฉพาะ UI/form state ก่อน ห้ามแตะ Import Excel pipeline

## 4. Follow-up: STAFF Editing Scope

### Checklist
- [ ] Login ด้วยบัญชี STAFF เช่น `SAIFON`
- [ ] เข้า Follow-up
- [ ] ตรวจว่ารายการทั้งหมดเป็น `staff_code = SAIFON`
- [ ] เปิด popup ติดตามลูกค้าของตัวเอง
- [ ] เปลี่ยนสถานะลูกค้า
- [ ] เปลี่ยนสถานะติดตาม
- [ ] เปลี่ยนความสำคัญ
- [ ] ใส่วันนัดติดตาม
- [ ] ใส่โน้ตติดตาม
- [ ] กดบันทึก Follow-up
- [ ] พยายามเปิดหรือแก้ record ของ staff_code อื่นผ่าน URL/route/interaction ที่มี

### Expected Result
- STAFF เห็นเฉพาะลูกค้าของตัวเอง
- STAFF บันทึก Follow-up ได้เฉพาะ record ของตัวเอง
- STAFF ไม่เห็นหรือไม่สามารถแก้ record ของคนอื่น
- EDITOR ยังเห็นและจัดการได้ทุก record
- Follow-up visibility ใช้ `staff_code` เท่านั้น

### Fail Action
- ถ้า STAFF เห็นข้อมูลคนอื่น ให้ตรวจ query ใน `fetch_followup_page`
- ถ้า STAFF แก้ข้อมูลคนอื่นได้ ให้ตรวจ modal save payload และ permission guard
- ถ้า EDITOR ถูกจำกัดผิด ให้ตรวจ `can_manage_all`

## Final Sign-off

- [ ] EDITOR test ผ่าน
- [ ] STAFF visibility test ผ่าน
- [ ] Manual Order test ผ่าน
- [ ] Follow-up test ผ่าน
- [ ] ไม่พบ Supabase `/rest/v1/*` ใน runtime หลัก
- [ ] `git status` ไม่มี source code change ที่ไม่ตั้งใจ

UAT result:
- [ ] PASS
- [ ] PASS WITH NOTES
- [ ] FAIL

หมายเหตุ:
- ถ้า FAIL ให้หยุด deploy เพิ่ม และบันทึก screenshot + user email + staff_code + customer/order id ที่ทำให้ fail
