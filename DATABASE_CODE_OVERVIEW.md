# Database Code Overview

ไฟล์นี้สรุปภาพรวมโค้ด database ของโปรเจค CRM นี้ เพื่อใช้เป็น reference เวลาตรวจ workflow, วาง patch, หรือ onboard งานต่อ

## ภาพรวมสถาปัตยกรรม

โปรเจคนี้เป็น Streamlit CRM app โดยใช้ฐานข้อมูลหลักเป็น Neon PostgreSQL

- Neon PostgreSQL ใช้เก็บข้อมูล CRM runtime ทั้งหมด เช่น lead, follow-up, order, product, user role
- Supabase ใช้เฉพาะ Auth/Login/session เท่านั้น
- Runtime CRM data ไม่ควรใช้ Supabase Database/Storage/REST
- โค้ด database หลักอยู่ใน `neon_utils.py` และโมดูลย่อยใน `crm_data/`

## ไฟล์ Database หลัก

### `neon_utils.py`

เป็นศูนย์กลาง database helper เดิมของระบบ มีทั้ง connection, schema guard, read/write functions, cache helpers และ utility ที่หลายหน้าเรียกใช้ร่วมกัน

กลุ่มหน้าที่หลัก:

- Neon connection/config
- schema/table/column guard
- import Excel read/write
- manual order write
- follow-up write
- customer/customer 360 query
- product options query/write
- user role query/write
- owner assignment
- cache clear helper

### `crm_data/dashboard.py`

โค้ด query สำหรับ Dashboard เช่น:

- KPI cards
- sales report
- sales report rows
- owner options สำหรับ filter

### `crm_data/products.py`

โค้ด query/write สำหรับ Product Master และ product options เช่น:

- product list
- product option create/update/delete
- product image URL
- active / archived filtering

### `crm_data/team_sales.py`

โค้ด query สำหรับ Team Sales เช่น:

- team totals
- team sales report
- sale type filtering

### `crm_data/common.py` และ `crm_data/cache.py`

helper กลางสำหรับ query/cache/shared utilities

### `auth_utils.py`

ใช้กับ Supabase Auth/Login/session ไม่ใช่ CRM database runtime หลัก

### `permissions.py`

ใช้กำหนด permission policy, role checking และ owner scope

## ตารางหลักใน Neon

ตารางที่ระบบใช้งานบ่อย:

```text
crm_data_imports        ข้อมูลนำเข้าจาก Excel / lead/customer records
crm_lead_followups      ข้อมูลสถานะติดตามลูกค้า
crm_user_roles          user / role / active status
crm_product_options     product master / SKU / image_url
crm_orders              order header
crm_order_items         order line items
crm_owner_assignments   owner assignment ตามเบอร์ลูกค้า
crm_staff_options       staff/employee options
```

## Connection และ Schema Guard

function กลุ่ม connection/schema guard สำคัญใน `neon_utils.py`:

```text
get_neon_database_url()
require_neon_config()
neon_connection()
neon_table_exists()
neon_column_exists()
ensure_crm_data_imports_schema()
```

ข้อควรระวัง:

- `ensure_crm_data_imports_schema()` อาจ mutate schema ตอน runtime ถ้าพบ table/column ขาด
- งาน patch ทั่วไปไม่ควรแตะ schema guard ถ้า requirement ไม่ได้ระบุชัด
- ถ้าต้องแก้ schema/migration ควรแยกเป็น phase เฉพาะ

## Read Flow สำคัญ

### Dashboard

```text
fetch_dashboard_kpis()
fetch_sales_report()
fetch_sales_report_rows()
fetch_sales_report_owner_options()
```

### Customers / Customer 360

```text
fetch_customer_page()
fetch_customer_export_rows()
fetch_customer_360_base()
fetch_customer_360_orders()
fetch_customer_360_products()
fetch_orders_by_phones()
```

### Follow-up

```text
fetch_followup_page()
fetch_followup_filter_options()
```

### Products

```text
fetch_product_options()
fetch_order_product_options()
```

### Users / Owner Options

```text
fetch_user_roles()
fetch_crm_owner_options()
fetch_owner_user_options()
```

### Import Excel

```text
fetch_import_history()
fetch_filter_options()
```

## Write Flow สำคัญ

### Import Excel

```text
insert_import_records()
delete_import_batch()
```

ข้อควรระวัง:

- ห้ามแก้ mapping/write flow ถ้า task ไม่ได้ระบุชัด
- cache clear หลัง import/delete ควรใช้ targeted clear เท่าที่ dependency ชัด

### Manual Order

```text
upsert_manual_order()
upsert_manual_order_items()
```

ข้อควรระวัง:

- `upsert_manual_order_items()` เป็นจุดสำคัญของ save transaction
- ห้ามแตะถ้า requirement ไม่ได้บอกตรง ๆ
- UI/product selector patch ควร preserve payload เดิม เช่น sku, product_name, qty, amount, image_url

### Follow-up

```text
upsert_lead_followup()
```

ข้อควรระวัง:

- follow-up order save ต้อง update status หลัง order save สำเร็จเท่านั้น
- ห้าม update follow-up/customer status ถ้า order save fail

### Product Master

```text
upsert_product_options()
insert_product_options()
update_product_option()
delete_product_option()
```

ข้อควรระวัง:

- active / archived filter สำคัญกับ order dropdown/product selector
- image_url อยู่ใน `crm_product_options`
- Product Master cache clear ควร targeted เพื่อให้ Manual Order / Follow-up เห็นข้อมูลใหม่

### Users / Roles

```text
upsert_user_role()
set_user_role_active()
```

ข้อควรระวัง:

- เกี่ยวข้องกับ permission และ owner scope
- cache clear ต้องระวังไม่ให้สิทธิ์เก่าค้าง

### Owner / URL Assignment

```text
assign_owner_to_phones()
assign_owner_to_order_record()
assign_url_to_phones()
```

## Cache Overview

ระบบใช้ `st.cache_data` หลายจุดเพื่อช่วยลด query ซ้ำ

ตัวอย่าง cache ที่พบ:

```text
fetch_user_role()
neon_table_exists()
neon_column_exists()
fetch_sales_report_owner_options()
fetch_filter_options()
fetch_import_history()
fetch_followup_filter_options()
fetch_product_options()
fetch_order_product_options()
fetch_crm_owner_options()
fetch_owner_user_options()
```

แนวทางปัจจุบัน:

- หลีกเลี่ยง `st.cache_data.clear()` แบบ global ถ้าไม่จำเป็น
- ใช้ `clear_cached_data_functions(...)` เพื่อล้าง cache เฉพาะ function ที่เกี่ยวข้อง
- Dashboard auto refresh ถูกปรับให้เป็น opt-in เพื่อลดโหลด DB
- Customer order history ถูกจำกัดการ render เพื่อลด HTML/render cost

## จุดที่ควรระวังมาก

ห้ามแก้โดยไม่ audit ก่อน:

```text
upsert_manual_order_items()
owner scope / permission scope
duplicate phone lock
Dashboard totals/query
Team Sales query
Import Excel mapping/write
Product Master active/archived filter
Follow-up save logic
Customer 360 phone matching
DB schema / migration
```

## แนวทางเวลาทำ Patch Database

1. อ่าน `PROJECT_CONTEXT.md` และ `CRM_WORKFLOW_LOGIC_AUDIT.md` ก่อน
2. ตรวจ `git status` ให้แน่ใจว่า repo clean ถ้าเป็นงาน audit/patch ที่ระบุไว้
3. หา call site ก่อนแก้ function กลาง
4. ถ้าแก้ query ต้องระบุว่าไม่กระทบ owner scope/filter/totals
5. ถ้าแก้ write flow ต้องแยกชัดว่าไม่แตะ final save function
6. ถ้าแก้ cache ให้ใช้ targeted clear ก่อน global clear
7. รัน validation อย่างน้อย:

```text
git diff --check
python -m py_compile <ไฟล์ที่แก้>
python tests/<test ที่เกี่ยวข้อง>.py
```

## สรุปสั้น

โครงสร้าง database ของโปรเจคนี้มี `neon_utils.py` เป็นแกนกลาง และเริ่มแยก domain query ไปไว้ใน `crm_data/` มากขึ้น ฐานข้อมูลหลักคือ Neon PostgreSQL ส่วน Supabase ใช้เฉพาะ Auth/Login/session เท่านั้น จุดที่ต้องระวังที่สุดคือ save transaction, owner/permission scope, cache invalidation และ query ที่กระทบ Dashboard/Team Sales totals
