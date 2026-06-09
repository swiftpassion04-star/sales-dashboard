# Project CRM Context

## สถานะปัจจุบัน

Project CRM คือเว็บ CRM ที่สร้างด้วย Streamlit สำหรับทีม Sales/CRM/Telesales ใช้ค้นหาลูกค้า เพิ่มคำสั่งซื้อ ติดตามลูกค้า ดูรายงาน และจัดการข้อมูลสินค้า/ผู้ใช้

Architecture ปัจจุบัน:
- Streamlit เป็น web application หลัก
- Neon PostgreSQL เป็น CRM database หลัก สำหรับข้อมูลลูกค้า ออเดอร์ สินค้า รายงาน และ follow-up
- Supabase ใช้เฉพาะ Auth/Login/session เท่านั้น
- ห้ามใช้ Supabase Database, Storage, หรือ REST Data API (`/rest/v1/*`) ใน runtime ของระบบ CRM

## Canonical Routes

ใช้ route/file ภาษาอังกฤษเป็นหลักเท่านั้น เพื่อเลี่ยงปัญหา encoding และลด logic ซ้ำ:

- `pages/dashboard.py`
- `pages/customers.py`
- `pages/followup.py`
- `pages/import_excel.py`
- `pages/products.py`
- `pages/users.py`
- `pages/system_status.py`
- `pages/settings.py`
- `pages/customer_detail.py` เป็น detail route เสริม ไม่อยู่ใน Sidebar หลัก

เมนูในเว็บสามารถแสดงภาษาไทยหรือ emoji ได้ แต่ไฟล์ route ต้องเป็นภาษาอังกฤษ

## Legacy Pages

ไฟล์ legacy ภาษาไทยยังอยู่ใน repo เพื่อ backward compatibility และอ้างอิง history เดิม แต่ไม่ใช่ canonical route และไม่ควรเพิ่ม logic ใหม่ในไฟล์เหล่านี้:

- `pages/1_รายงาน.py`
- `pages/2_KPI.py`
- `pages/3_sync_status.py`
- `pages/4_เพิ่มข้อมูลลูกค้า.py`
- `pages/5_ฐานข้อมูลลูกค้า.py`
- `pages/6_สินค้า.py`
- `pages/7_พนักงาน.py`
- `pages/8_ประวัติการซื้อ.py`
- `pages/9_ติดตามลูกค้า.py`
- `pages/10_System_Settings.py`

ถ้าต้องรองรับ URL เก่า ให้ใช้ redirect หรือเรียก logic กลางเท่านั้น ห้าม duplicate business logic สองชุด

## Data Flow

1. ผู้ใช้ login ผ่าน Supabase Auth
2. ระบบอ่าน role/permission จาก Neon ผ่าน `crm_user_roles`
3. ข้อมูล CRM หลักอ่าน/เขียนจาก Neon เท่านั้น
4. Import Excel และ Manual Order บันทึกเข้า Neon
5. Dashboard, Customers, Follow-up, Products, Users และ System Status อ่านข้อมูลจาก Neon ผ่าน helper กลาง
6. Supabase ไม่ใช้เป็น CRM database แล้ว

## Main Neon Tables

ตารางหลักของ CRM อยู่ใน Neon PostgreSQL:

- `crm_data_imports`: ข้อมูลลูกค้าและคำสั่งซื้อหลัก
- `crm_lead_followups`: สถานะ lead/follow-up และบันทึกการติดตาม
- `crm_user_roles`: user, role, staff mapping และ permission mapping
- `crm_product_options`: master data สินค้า/SKU
- `crm_orders`, `crm_order_items`: schema additive สำหรับ order/order item ต่อในอนาคต

## Helper Files

- `auth_utils.py`: Supabase Auth/Login/session only
- `permissions.py`: permission policy กลางของระบบ
- `neon_utils.py`: data helper หลักสำหรับ Neon PostgreSQL
- `nav_utils.py`: Sidebar/navigation ของ canonical routes
- `crm_theme.py`: global UI theme/CSS

## Supabase Rule

Supabase ใช้ได้เฉพาะ:

- Auth/Login
- Session restore/refresh ผ่าน `/auth/v1/*`

ห้ามใช้ใน runtime:

- Supabase Database
- Supabase Storage
- Supabase REST Data API `/rest/v1/*`
- `supabase.table(...)`
- `supabase.storage...`
- service role key ใน browser/client

ถ้าพบความจำเป็นต้องใช้ Supabase นอกเหนือจาก Auth ให้หยุดและขออนุมัติก่อนเสมอ

## Permission Policy

ใช้ `permissions.py` เป็น source of truth สำหรับ role/permission:

- `normalize_role(role)`
- `can_manage_all(user)`
- `can_edit_users(user)`
- `can_edit_products(user)`
- `can_import_excel(user)`
- `can_export_customers(user)`
- `is_staff_limited(user)`

ห้ามกระจาย permission rule ใหม่ใน page โดยไม่ใช้ helper กลาง

## Operational Rules

ห้ามแตะสิ่งเหล่านี้ถ้าไม่ได้รับอนุญาตชัดเจน:

- Import Excel workflow
- Supabase Auth/Login/session behavior
- Neon schema/migration
- permission policy
- business workflow ของ Manual Order, Customers, Follow-up, Product Master

ก่อนแก้ schema ให้สร้าง migration file ใน repo และสรุป SQL ให้ review ก่อนเสมอ ห้าม execute migration อัตโนมัติถ้ายังไม่ได้รับอนุญาต

## Workflow Files

- `.github/workflows/deploy-dashboard.yml`: ตรวจ dependency และ syntax
- `.github/workflows/cleanup.yml`: repository hygiene audit
- `.github/workflows/sync-data.yml`: legacy sync ถูก disable แล้ว
- `.github/workflows/sync-crm-customers.yml`: legacy sync ถูก disable แล้ว

Legacy Google Sheet/Supabase sync ไม่ใช่ workflow หลักอีกต่อไป

## Repository Safety

- ห้าม commit secrets, service account JSON, exports, logs, backups, local outputs
- ห้าม print secrets ลง log
- ห้ามลบไฟล์ production, workflow, schema หรือ deployment config โดยไม่ถาม
- ก่อน commit/push ต้องทดสอบตาม scope และสรุป diff ให้ตรวจถ้าผู้ใช้กำหนดไว้
