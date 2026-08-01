# Owner / Staff Mapping Approval

เอกสารนี้ใช้สำหรับให้ผู้บริหารตรวจและอนุมัติการ normalize `owner` -> canonical `staff_code` ก่อน update ข้อมูลจริงใน Neon PostgreSQL

สถานะเอกสาร: `PENDING REVIEW`

ข้อห้ามสำคัญ:

- ห้าม update ข้อมูลจริงจนกว่าแถว mapping จะเป็น `APPROVED`
- ห้าม auto assign rows ที่ owner ว่าง
- ห้ามใช้ชื่อไทยเป็น `staff_code` ถาวร
- ห้ามแก้ข้อมูล production โดยไม่มี backup ก่อน

## Mapping Proposal

| owner_alias | current records | current staff_code variants | proposed staff_code | proposed email | status |
|---|---:|---|---|---|---|
| สายฝน ราวิชัย (สายฝน) | 6,502 | `สายฝน`, `สายฝน ราวิชัย (สายฝน)` | `SAIFON` | `swiftpassion.com18@gmail.com` | PENDING |
| พรณกมล ดวงจันทร์ (แต้ว) | 4,669 | `แต้ว`, `พรณกมล ดวงจันทร์ (แต้ว)` | `TAEW` | `swiftpassion.com17@gmail.com` | PENDING |
| พรธนนันท์ กานต์รพีพร (หญิง) | 3,100 | `หญิง`, `พรธนนันท์ กานต์รพีพร (หญิง)` | `YING` | `swiftpassion.com21@gmail.com` | PENDING |
| กัญญพักฒ์ อิ่มยวง (เจี๊ยบ) | 3,087 | `เจี๊ยบ` | merge → `NOONA` (JEEB retired) | N/A — merge decision | **APPROVED (2026-07-23)** |
| ธัญญรัตน์ หอมระรื่น (เล็ก) | 9 | `ธัญญรัตน์ หอมระรื่น (เล็ก)` | `LEK` | `swiftpassion.com03@gmail.com` | PENDING |
| จินดามณี คงมี (ครีม) | 1 | `จินดามณี คงมี (ครีม)` | `CREAM` | `swiftpassion.com16@gmail.com` | PENDING |
| สุมนตรา ทัศน์ศรี (โก้) | 1 | `สุมนตรา ทัศน์ศรี (โก้)` | `KO` | `swiftpassion.com14@gmail.com` | PENDING |
| owner ว่าง | 730 | ว่าง | NULL | - | NEED_CONFIRM |

## ต้องยืนยันเป็นพิเศษ

รายการต่อไปนี้ยังไม่ควร update จนกว่าจะยืนยันเจ้าของข้อมูลชัดเจน:

| รายการ | เหตุผล | Action ที่ต้องการ |
|---|---|---|
| กัญญพักฒ์ อิ่มยวง (เจี๊ยบ) | **APPROVED (2026-07-23)** — merge ข้อมูล 3,087 records ทั้งหมดเข้า `staff_code = NOONA` และปิดการใช้งาน `JEEB` ถาวร | ดำเนินการผ่าน `neon/manual_sql/202607_jeeb_to_noona_merge.sql` (ยังไม่ได้รัน — รอสิทธิ์เข้าถึงฐานข้อมูลจริง) |
| `swiftpassion.com22@gmail.com` / ศิวพร ถีติปริวัตร (อุ๊) | มี user role แต่ยังไม่พบ owner/import records ที่ตรงกัน | ยืนยันว่าจะคงไว้เป็น user ว่าง หรือ map กับ owner อื่น |
| `swiftpassion.com19@gmail.com` / พรนภา นันที (หนูนา) | บัญชี login เดิมของหนูนา — **ยังคงเป็นเจ้าของ `staff_code = NOONA` ตามเดิม** ตอนนี้จะรวมถึงข้อมูล 3,087 records ที่ merge มาจาก JEEB ด้วย (ตาม decision ด้านบน) | ตรวจสอบสิทธิ์การมองเห็นข้อมูลของหนูนาอีกครั้งหลัง migration รันจริง |
| owner ว่าง 730 rows | ไม่สามารถระบุเจ้าของจากข้อมูลปัจจุบันได้ | คง `owner = NULL`, `staff_code = NULL` จนกว่าจะมีหลักฐาน |

## กติกามาตรฐาน

1. `staff_code` ใช้ภาษาอังกฤษตัวใหญ่เท่านั้น เช่น `SAIFON`, `TAEW`, `YING`
2. `staff_code` เป็น key ถาวรสำหรับ permission, report, assignment และ Schema V2
3. `owner` และ `staff_name` ใช้ชื่อไทยเพื่อแสดงผลบนหน้าจอเท่านั้น
4. `owner_alias` ใช้เก็บชื่อไทยที่ normalize แล้ว เพื่อช่วย match ข้อมูล import เดิม
5. owner ว่างให้คง `NULL` ไม่ auto assign
6. ห้าม update ข้อมูลจริงจนกว่า status เป็น `APPROVED`
7. การ update ต้องใช้ normalized exact match เท่านั้น:
   - trim ช่องว่างหัวท้าย
   - ลดช่องว่างซ้ำเหลือ 1 ช่อง
   - match ข้อความเต็มหลัง normalize

## SQL Draft ตัวอย่างเท่านั้น ห้าม Execute

ตัวอย่าง backup ก่อน update:

```sql
-- DRAFT ONLY - DO NOT EXECUTE WITHOUT APPROVAL
create table if not exists public.crm_owner_staff_backup_yyyymmdd as
select
  id,
  owner,
  staff_code,
  customer_name,
  phone1,
  phone2,
  order_id,
  updated_at
from public.crm_data_imports;
```

ตัวอย่าง update หลังได้รับ approval:

```sql
-- DRAFT ONLY - DO NOT EXECUTE WITHOUT APPROVAL
update public.crm_data_imports
set staff_code = 'SAIFON',
    updated_at = now()
where regexp_replace(btrim(owner), '\s+', ' ', 'g') = 'สายฝน ราวิชัย (สายฝน)';

update public.crm_user_roles
set staff_code = 'SAIFON',
    staff_name = 'สายฝน ราวิชัย (สายฝน)',
    owner_alias = 'สายฝน ราวิชัย (สายฝน)',
    updated_at = now()
where email = 'swiftpassion.com18@gmail.com';
```

ตัวอย่าง compare count ก่อน/หลัง:

```sql
-- DRAFT ONLY - READ-ONLY CHECK
select
  regexp_replace(btrim(owner), '\s+', ' ', 'g') as owner_norm,
  staff_code,
  count(*) as records
from public.crm_data_imports
group by 1, 2
order by records desc;
```

## Rollback Plan

1. Export/backup columns สำคัญก่อน update:
   - `id`
   - `owner`
   - `staff_code`
   - `customer_name`
   - `phone1`
   - `phone2`
   - `order_id`
   - `updated_at`
2. Update เฉพาะ owner ที่ normalize แล้ว match แบบ exact เท่านั้น
3. หลีกเลี่ยง update rows ที่ `owner` ว่าง
4. Compare count ก่อน/หลังทุก owner:
   - จำนวน records ต่อ owner ต้องเท่าเดิม
   - จำนวน records ต่อ canonical `staff_code` ต้องตรงกับ mapping ที่อนุมัติ
5. ถ้าพบ mapping ผิด ให้ restore เฉพาะ rows จาก backup ด้วย `id`
6. หลัง rollback ต้องตรวจ permission ของ STAFF/พนักงานในหน้า Customers และ Follow-up อีกครั้ง

## Approval Checklist

| Check | Status |
|---|---|
| ผู้บริหารยืนยัน `SAIFON` | PENDING |
| ผู้บริหารยืนยัน `TAEW` | PENDING |
| ผู้บริหารยืนยัน `YING` | PENDING |
| ผู้บริหารยืนยัน `JEEB` และ email ที่ถูกต้อง | N/A — `JEEB` retired, merged into `NOONA` (APPROVED 2026-07-23, see Owner Mapping review) |
| ผู้บริหารยืนยัน `LEK` | PENDING |
| ผู้บริหารยืนยัน `CREAM` | PENDING |
| ผู้บริหารยืนยัน `KO` | PENDING |
| ตัดสินใจ rows owner ว่าง 730 rows | NEED_CONFIRM |
| ยืนยัน backup plan ก่อน update | PENDING |
| ยืนยัน rollback plan ก่อน update | PENDING |

