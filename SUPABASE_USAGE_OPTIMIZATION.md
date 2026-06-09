# Supabase Usage Optimization Notes

## Current Policy

ระบบ CRM ปัจจุบันใช้ Supabase เฉพาะ Auth/Login เท่านั้น

CRM data ทั้งหมดต้องอยู่ใน Neon PostgreSQL ไม่ใช่ Supabase Database

อนุญาตให้ใช้ Supabase:
- Auth/Login
- Session refresh/restore ผ่าน `/auth/v1/*`

ไม่อนุญาตให้ใช้ใน runtime:
- Supabase Database
- Supabase Storage
- Supabase REST Data API `/rest/v1/*`
- `supabase.table(...)`
- `supabase.storage...`
- service role key ใน browser/client

## Why This Changed

ระบบเคยใช้ Supabase เป็น database สำหรับ `order_history`, `crm_customers`, staging/import และ sync jobs ทำให้เกิด egress/database usage สูง

แนวทางใหม่คือ:
- Neon PostgreSQL เป็น CRM database หลัก
- Supabase เหลือเฉพาะ Auth เพื่อลด egress และลดความเสี่ยงจาก Data API
- GitHub Actions sync เก่าถูก disable แล้ว
- Streamlit Excel/Manual Order ทำงานกับ Neon เท่านั้น

## Current Runtime Checkpoints

ควรตรวจเป็นระยะด้วยคำค้นเหล่านี้:

```powershell
rg -n --hidden -S "/rest/v1|supabase\.table|supabase\.storage|\.storage\.from|SUPABASE_SERVICE_ROLE_KEY|CRM_SUPABASE_SERVICE_KEY|CRM_SUPABASE_SERVICE_ROLE" .
```

Expected runtime result:
- ไม่พบ `/rest/v1`
- ไม่พบ `supabase.table`
- ไม่พบ `supabase.storage`
- ไม่พบ service role secret ใน runtime code

หมายเหตุ: อาจยังพบคำว่า `service_role` ใน legacy migration files ภายใต้ `supabase/migrations/` ซึ่งเป็นประวัติ schema เก่า ไม่ใช่ runtime call

## Active Data Location

ข้อมูล CRM หลักอยู่ใน Neon PostgreSQL:
- `crm_data_imports`
- `crm_lead_followups`
- `crm_user_roles`
- `crm_product_options`
- `crm_orders`
- `crm_order_items`

Runtime data access ควรผ่าน `neon_utils.py` และเลือก column เท่าที่จำเป็น ห้ามกลับไปใช้ Supabase REST

## Auth Error Handling

`auth_utils.py` ต้องจัดการ Supabase Auth error ให้ชัดเจน:
- login ผิด
- session หมดอายุ
- timeout
- project ถูกจำกัด usage/billing

Auth error ต้องไม่ทำให้หน้า CRM crash เป็น raw traceback ถ้าสามารถแสดงข้อความให้ผู้ใช้เข้าใจได้

## Operational Rules

- ห้ามเพิ่ม Supabase DB/Storage call ใหม่โดยไม่ขออนุมัติ
- ห้ามนำ service role key ไปไว้ฝั่ง browser/client
- ถ้าต้องแก้ Auth ให้แตะเฉพาะ `/auth/v1/*`
- ถ้าต้องเพิ่ม CRM data workflow ให้ใช้ Neon เท่านั้น
- ถ้าพบ legacy sync ที่ยิง Supabase ให้ disable ก่อน แล้วค่อยเสนอแผนลบ/clean up

## Legacy Notes

เอกสารหรือ migration เก่าที่พูดถึง `order_history`, `crm_customers`, `import_staging` บน Supabase เป็น historical context เท่านั้น

อย่าใช้เป็น source of truth สำหรับ architecture ปัจจุบัน
