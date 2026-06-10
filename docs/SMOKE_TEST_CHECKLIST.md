# CRM Smoke Test Checklist

ใช้ checklist นี้ก่อน deploy ทุกครั้ง เพื่อยืนยันว่า CRM ยังทำงานถูกต้องหลังการแก้ไข โดยเฉพาะจุดที่เกี่ยวกับ Auth, Neon, Permission, Form state และหน้าหลักของระบบ

## ขอบเขตการทดสอบ

- ทดสอบผ่าน Streamlit app จริง
- ห้ามใช้ข้อมูล secrets ใน log หรือ screenshot
- ห้ามรัน migration ระหว่าง smoke test
- ห้ามแก้ข้อมูล production โดยไม่ตั้งใจ
- ถ้าต้องทดสอบการบันทึก ให้ใช้ข้อมูล test ที่ระบุชัดเจนและลบ/rollback ได้

## 1. Login / Logout

- [ ] เปิดเว็บแล้วเห็นหน้า login
- [ ] Login ด้วยบัญชี EDITOR สำเร็จ
- [ ] Login ด้วยบัญชี STAFF/พนักงาน สำเร็จ
- [ ] Logout แล้วกลับมาหน้า login
- [ ] หลัง logout ไม่สามารถเข้าหน้าภายในระบบได้โดยตรง
- [ ] ถ้า login fail แสดงข้อความที่เข้าใจง่าย และไม่ crash

## 2. Supabase Auth Only

- [ ] Login ใช้ Supabase Auth ได้ตามปกติ
- [ ] ไม่มีการอ่าน/เขียน Supabase Database
- [ ] ไม่มีการเรียก Supabase Storage
- [ ] ไม่มีการใช้ Supabase service role ใน browser
- [ ] Auth error เช่น 401/timeout ไม่ทำให้หน้าเว็บ crash

## 3. Customers Page

- [ ] หน้า "ค้นหาลูกค้า" เปิดได้
- [ ] EDITOR เห็นข้อมูลลูกค้าทั้งหมด
- [ ] STAFF/พนักงาน เห็นข้อมูลตาม behavior ปัจจุบันของหน้า Customers
- [ ] ค้นหาด้วยเบอร์โทรได้
- [ ] ค้นหาด้วยชื่อลูกค้าได้
- [ ] ค้นหาด้วยเลขคำสั่งซื้อได้
- [ ] Pagination ทำงานและไม่โหลดข้อมูลทั้ง table
- [ ] ปุ่มดูประวัติเปิดรายละเอียดได้
- [ ] URL แสดงเป็นลิงก์ "เปิดลิงก์" เมื่อมี URL
- [ ] กรณีไม่พบข้อมูล มี empty state ที่อ่านง่าย

## 4. Follow-up Page

- [ ] หน้า "ติดตามลูกค้า" เปิดได้
- [ ] EDITOR เห็นรายการที่เกี่ยวข้องทั้งหมดตาม filter
- [ ] STAFF/พนักงานเห็นข้อมูลที่ตัวเองดูแลตาม mapping ปัจจุบัน
- [ ] filter สถานะลูกค้าใช้งานได้
- [ ] filter สถานะติดตามใช้งานได้
- [ ] filter ความสำคัญใช้งานได้
- [ ] filter สินค้า/SKU ใช้งานได้
- [ ] ค้นหาด้วยเบอร์โทรได้
- [ ] กดเปิด popup ติดตามได้
- [ ] บันทึก Follow-up สำเร็จแล้ว popup ปิด/สถานะหน้าไม่ค้างผิด
- [ ] ไม่เกิด popup เด้งเองเมื่อค้นหาหรือเปลี่ยน filter

## 5. Manual Order

- [ ] หน้า "เพิ่มคำสั่งซื้อ" เปิดได้
- [ ] EDITOR เพิ่มคำสั่งซื้อได้
- [ ] STAFF/พนักงานเพิ่มคำสั่งซื้อได้ตามสิทธิ์ปัจจุบัน
- [ ] กรอกเลขคำสั่งซื้อได้
- [ ] กรอกชื่อลูกค้าได้
- [ ] กรอกเบอร์โทรหรือเบอร์สำรองอย่างน้อย 1 ช่องได้
- [ ] กรอก URL ได้
- [ ] กรอกที่อยู่ได้
- [ ] เลือกประเภทการขายได้: NEW_ORDER, UPSELL, FOLLOW
- [ ] ถ้าเลือก FOLLOW ยอดขายไม่ถูกนับในรายงานยอดขาย
- [ ] ถ้าบันทึกสำเร็จ form reset พร้อมกรอกใหม่
- [ ] ถ้าบันทึกไม่สำเร็จ form ไม่ถูก clear

## 6. Multi SKU

- [ ] เลือกสินค้าได้จาก dropdown
- [ ] เพิ่มสินค้าอย่างน้อย 1 รายการก่อนบันทึก
- [ ] qty ต้องมากกว่า 0
- [ ] SKU เดียวกันและชื่อสินค้าเดียวกัน รวม qty อัตโนมัติ
- [ ] SKU เดียวกันแต่ชื่อสินค้าต่างกัน แยกคนละรายการ
- [ ] ลบรายการสินค้าในคำสั่งซื้อได้
- [ ] บันทึก 1 order หลาย SKU แล้วระบบไม่ crash
- [ ] หลังบันทึกสำเร็จ รายการสินค้าถูก clear

## 7. Import Excel

- [ ] EDITOR เห็นส่วน Import Excel
- [ ] STAFF/พนักงานไม่สามารถใช้งาน Import Excel ตามสิทธิ์
- [ ] Upload รองรับไฟล์ .xlsx
- [ ] เลือก worksheet ได้
- [ ] mapping columns ได้
- [ ] preview ข้อมูลก่อน import ได้
- [ ] validate ข้อมูล required fields ได้
- [ ] แสดง valid rows และ invalid rows ได้
- [ ] confirm import ได้
- [ ] import history แสดงได้
- [ ] Import fail แสดง error ที่เข้าใจง่าย
- [ ] Manual Order UI และ Import Excel UI ไม่กระทบกัน

## 8. Products

- [ ] หน้า "สินค้า" เปิดได้จาก Sidebar
- [ ] EDITOR เพิ่มสินค้าได้
- [ ] EDITOR แก้ SKU / ชื่อสินค้า / กลุ่มสินค้าได้
- [ ] EDITOR ปิดใช้งานสินค้าได้
- [ ] STAFF/USER เห็นสินค้าแบบ read-only
- [ ] ค้นหาด้วย SKU ได้
- [ ] ค้นหาด้วยชื่อสินค้าได้
- [ ] Import สินค้าจาก .xlsx แสดง preview ก่อนยืนยัน
- [ ] SKU + ชื่อสินค้า + กลุ่มสินค้า ตรงกันทั้งหมดไม่เพิ่มซ้ำ
- [ ] SKU ต่างกันให้เพิ่มเป็นรายการใหม่ตาม rule ปัจจุบัน

## 9. User / Role

- [ ] หน้า "User / Role" เปิดได้เฉพาะ EDITOR/ADMIN ตาม policy ปัจจุบัน
- [ ] แสดง user จาก Neon table `crm_user_roles`
- [ ] เพิ่ม user ได้ถ้า role มีสิทธิ์
- [ ] แก้ email ได้ถ้า role มีสิทธิ์
- [ ] แก้ role ได้ถ้า role มีสิทธิ์
- [ ] แก้ staff_code และ staff_name ได้ถ้า role มีสิทธิ์
- [ ] active/inactive user ได้
- [ ] ทดสอบ mapping user แล้วเห็นจำนวนลูกค้าที่ user จะเห็น
- [ ] STAFF/พนักงานเข้าแก้ User / Role ไม่ได้

## 10. Dashboard Report

- [ ] หน้า Dashboard เปิดได้
- [ ] KPI cards โหลดได้
- [ ] รายงานยอดขายแสดงได้
- [ ] เลือกช่วงเวลา preset ได้ เช่น วันนี้, เมื่อวาน, 7 วัน, 30 วัน, เดือนนี้
- [ ] เลือกช่วงวันที่แบบกำหนดเองได้
- [ ] EDITOR เห็นยอดรวมทั้งหมด
- [ ] EDITOR filter ผู้ดูแลได้
- [ ] STAFF/พนักงานเห็นยอดเฉพาะข้อมูลของตัวเองตาม policy ปัจจุบัน
- [ ] NEW_ORDER แสดงยอดขาย/จำนวน/AOV ถูกต้อง
- [ ] UPSELL แสดงยอดขาย/จำนวน/AOV ถูกต้อง
- [ ] FOLLOW ไม่ถูกนับยอดขาย

## 11. Export XLSX

- [ ] EDITOR เห็นปุ่ม export xlsx ในหน้า Customers
- [ ] STAFF/พนักงานไม่เห็นหรือใช้งาน export ไม่ได้
- [ ] export แบบทั้งหมดได้
- [ ] export แบบรายวันได้
- [ ] export แบบรายเดือนได้
- [ ] export แบบเลือกช่วงวันที่ได้
- [ ] ไฟล์ที่ export มีหัวตารางตาม template ที่ใช้ import
- [ ] ข้อมูลที่ไม่มีค่าแสดงเป็นช่องว่าง
- [ ] 1 แถวต่อ 1 order หรือ 1 แถวตาม rule fallback กรณีไม่มีเลขออเดอร์

## 12. Permission

### EDITOR

- [ ] เห็นข้อมูลลูกค้าทั้งหมด
- [ ] ใช้ Import Excel ได้
- [ ] เพิ่ม Manual Order ได้
- [ ] มอบหมายผู้ดูแลได้
- [ ] แก้ User / Role ได้
- [ ] จัดการ Product Master ได้
- [ ] Export xlsx ได้
- [ ] ดู Dashboard report ทุกคนได้

### STAFF / พนักงาน

- [ ] Login ได้
- [ ] เห็นเมนูที่ได้รับอนุญาต
- [ ] เพิ่ม Manual Order ได้ตาม rule ปัจจุบัน
- [ ] ไม่เห็น Import Excel หรือใช้งานไม่ได้
- [ ] ไม่สามารถแก้ User / Role
- [ ] ไม่สามารถจัดการ Product Master
- [ ] ไม่สามารถ Export xlsx
- [ ] เห็น Follow-up ตาม owner/staff mapping ปัจจุบัน

## 13. Neon Connection

- [ ] `NEON_DATABASE_URL` ถูกตั้งใน Streamlit Secrets
- [ ] เว็บเชื่อม Neon ได้
- [ ] ถ้า Neon connection fail แสดงข้อความชัดเจน
- [ ] ห้าม print connection string
- [ ] Query หลักใช้ explicit columns เท่าที่จำเป็น
- [ ] Pagination/filter ทำฝั่ง server

## 14. No Supabase /rest/v1/*

- [ ] ค้นหาโค้ดแล้วไม่พบ `/rest/v1`
- [ ] ค้นหาโค้ดแล้วไม่พบ `supabase.table`
- [ ] ค้นหาโค้ดแล้วไม่พบ Supabase Storage call
- [ ] Supabase ใช้เฉพาะ `/auth/v1/*`
- [ ] GitHub Actions ไม่มี workflow ที่ sync ข้อมูลเข้า Supabase Database

คำสั่งตรวจแนะนำ:

```powershell
rg -n "/rest/v1|supabase\\.table|storage\\.|SUPABASE_SERVICE_ROLE|service_role" -S .
```

## 15. Streamlit Session / Form Reset

- [ ] Login session ไม่หลุดเมื่อเปลี่ยนหน้า
- [ ] Logout ล้าง session ถูกต้อง
- [ ] Manual Order save success แล้ว clear form
- [ ] Manual Order save fail แล้วไม่ clear form
- [ ] Product selector reset หลังเพิ่มสินค้า
- [ ] Multi SKU list reset หลัง save success
- [ ] Popup/Modal ปิดแล้วไม่เด้งเองจาก session state เก่า
- [ ] เปลี่ยน filter/search แล้วไม่เปิด popup เก่าค้าง
- [ ] ไม่พบ `StreamlitAPIException` จากการ set `st.session_state` หลัง widget render

## Pre-deploy Commands

รันอย่างน้อย 2 คำสั่งนี้ก่อน deploy/push:

```powershell
$files = rg --files -g "*.py" -g "!__pycache__/**" -g "!.venv/**"
.\.venv\Scripts\python.exe -m py_compile @files
git diff --check
```

## Manual Smoke Test Result

- วันที่ทดสอบ:
- Tester:
- Commit:
- Environment:
- ผลรวม: Pass / Fail
- รายการที่ fail:
- หมายเหตุ:
