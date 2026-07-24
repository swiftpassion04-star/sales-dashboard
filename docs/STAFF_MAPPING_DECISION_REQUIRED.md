# Staff Mapping Decision Required

เอกสารนี้ใช้เป็น decision gate ขั้นสุดท้ายก่อน normalize `staff_code` จริงใน Neon PostgreSQL

สถานะเอกสาร: `PENDING EXECUTIVE DECISION`

ผลจาก Stabilization Sprint Step 12:

- Ready For Real Update: `NO`
- เหตุผลหลัก:
  1. `JEEB` มี 3,087 records แต่ยังไม่มี email/user role ชัดเจน
  2. `owner` / `staff_code` ว่าง 730 rows
  3. `หนูนา` และ `อุ๊` มี user role แต่ไม่มี owner records ในข้อมูล import ปัจจุบัน

## Decision Required Table

| Issue | Records affected | Current value | Proposed action | Options | Recommended choice | Status |
|---|---:|---|---|---|---|---|
| JEEB owner ยังไม่มี email ที่ชัดเจน | 3,087 | owner = `กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)`, staff_code = `เจี๊ยบ` | merge เข้า `NOONA` และปิดการใช้งาน `JEEB` | 1. ผูกกับ email ที่มีอยู่ 2. สร้าง user ใหม่ 3. merge เข้า `NOONA` (**เลือก**) | merge ข้อมูลทั้งหมดของ `JEEB` เข้า `staff_code = NOONA` และปิดการใช้งาน `JEEB` ถาวร | **APPROVED (2026-07-23)** |
| owner/staff_code ว่าง | 730 | owner = NULL/ว่าง, staff_code = NULL/ว่าง | คง `staff_code = NULL` | 1. คง NULL 2. สร้าง bucket UNASSIGNED 3. assign ให้คนใดคนหนึ่ง | คง NULL และแสดงผลว่า “ยังไม่มอบหมาย” | NEED_CONFIRM |
| หนูนา มี user role แต่ไม่มี owner records | 0 current records | `swiftpassion.com19@gmail.com` / `พรนภา นันที (หนูนา)` | คง user active ถ้ายังเป็นพนักงาน | 1. คง active 2. inactive 3. map กับ owner อื่น | คง active แต่ไม่ map กับข้อมูลใดจนกว่าจะมี owner/import records | PENDING |
| อุ๊ มี user role แต่ไม่มี owner records | 0 current records | `swiftpassion.com22@gmail.com` / `ศิวพร ถีติปริวัตร (อุ๊)` | คง user active ถ้ายังเป็นพนักงาน | 1. คง active 2. inactive 3. map กับ owner อื่น | คง active แต่ไม่ map กับข้อมูลใดจนกว่าจะมี owner/import records | PENDING |
| Canonical staff_code หลัก | 17,369 | ใช้ทั้งชื่อเล่นและชื่อเต็มไทย | normalize เป็น code อังกฤษตัวใหญ่ | 1. ใช้ code อังกฤษ 2. ใช้ชื่อเต็มไทย 3. ใช้ชื่อเล่นไทย | ใช้ code อังกฤษตัวใหญ่ถาวร | PENDING |

## ประเด็น JEEB — APPROVED: Merge เข้า NOONA (2026-07-23)

**สถานะ: อนุมัติแล้ว** ผู้บริหารยืนยันผ่านการตรวจสอบ Owner Mapping (2026-07-23) ว่า:

> "APPROVE ให้ดำเนินการย้ายข้อมูลทั้งหมดจาก staff_code=JEEB ไปเป็น staff_code=NOONA และลบ JEEB ออกจากระบบได้"

ข้อมูลที่พบ (ก่อนอนุมัติ):

- owner: `กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)`
- records: 3,087
- current staff_code: `เจี๊ยบ`
- current matching user role: ยังไม่พบ email/user role ที่ match ชัดเจน

**ขอบเขตที่อนุมัติ:**

1. ย้ายข้อมูลของ `JEEB` ทั้งหมด 3,087 แถว รวมถึงข้อมูลที่เกี่ยวข้องทั้งหมด (`crm_data_imports`, `crm_lead_followups`, `crm_orders`) ให้เป็นของ `staff_code = NOONA`
2. เปลี่ยน Owner/Staff code/ชื่อผู้ดูแลให้สัมพันธ์กับ `NOONA` ตาม User/Role และ Owner Mapping
3. ลบหรือปิดการใช้งานบัญชี Login, Staff option, Alias และ Mapping ของ `JEEB` (`crm_user_roles`, `crm_staff_options`) เพื่อไม่ให้เลือกหรือเข้าใช้งานได้อีก
4. อัปเดต governance docs ทั้งสองไฟล์ให้ตรงกับสถานะใหม่ (เอกสารนี้)
5. ก่อนแก้ให้สำรองเฉพาะข้อมูลที่ได้รับผลกระทบ (ดูสคริปต์ migration)
6. ดำเนินการใน Transaction เดียว หากขั้นตอนใดผิดพลาดให้ Rollback ทั้งหมด
7. ตรวจยอดก่อน–หลัง โดยจำนวนข้อมูลต้องครบ ไม่มีข้อมูลสูญหาย ไม่มี `JEEB` ตกค้าง และ `NOONA` ต้องเห็นข้อมูลที่ย้ายมาครบ
8. ห้ามกระทบ Staff คนอื่น (SAIFON/TAEW/YING/LEK/CREAM/KO/AU/ผู้ดูแลว่าง)

**สถานะการดำเนินการ (ณ 2026-07-23): DECISION APPROVED — DATA MIGRATION ยังไม่ได้รัน**

เหตุผล: environment ที่ใช้พัฒนา branch `feature/owner-staff-mapping` ไม่มี `NEON_DATABASE_URL` จึงไม่สามารถเชื่อมต่อฐานข้อมูลจริงเพื่อตรวจยอดก่อน–หลังหรือรัน migration ได้ สคริปต์ migration แบบ transaction-safe พร้อม backup/rollback/verification ถูกจัดเตรียมไว้ที่ `neon/manual_sql/202607_jeeb_to_noona_merge.sql` — **ต้องรันโดยผู้ที่มีสิทธิ์เข้าถึงฐานข้อมูลจริงเท่านั้น หลังตรวจสอบยอดก่อน-หลังตามสคริปต์**

ไฟล์ `neon/manual_sql/202606_staff_code_normalization_plan.sql` เดิมมีการ map JEEB's records ไปเป็น `NOONA` เช่นกัน แต่ผูก `NOONA` เข้ากับ login ของหนูนาในลักษณะที่ขัดแย้งกับเอกสารนี้ (ไม่เคยถูก APPROVE) ไฟล์นั้น **ยังคงห้ามรัน** สำหรับส่วน `AU`/`อุ๊`/blank-730 — ใช้เฉพาะ `neon/manual_sql/202607_jeeb_to_noona_merge.sql` สำหรับการ merge JEEB→NOONA ที่ได้รับอนุมัติแล้วเท่านั้น

## ประเด็น owner ว่าง

ข้อมูลที่พบ:

- records: 730
- owner: ว่าง
- staff_code: ว่าง

กติกา:

- ห้าม auto assign ให้พนักงานคนใดคนหนึ่ง
- ห้ามเดาจากชื่อสินค้า/เบอร์/วันที่
- ควรคง `staff_code = NULL`
- ให้ระบบแสดงผลว่า “ยังไม่มอบหมาย”

Recommended choice:

- คง owner/staff_code เป็น NULL
- ให้ EDITOR มอบหมายภายหลังจากหน้าเว็บเมื่อมีข้อมูลชัดเจน

## ประเด็น หนูนา / อุ๊

### หนูนา

- email: `swiftpassion.com19@gmail.com`
- staff_name: `พรนภา นันที (หนูนา)`
- records ที่ match ใน `crm_data_imports`: 0

Recommendation:

- คง active ได้ ถ้ายังเป็นพนักงาน
- ไม่ต้อง map กับข้อมูลใดจนกว่าจะมี owner/import records
- ห้าม map ทับ owner ของคนอื่นเพื่อให้มีข้อมูลแสดง

### อุ๊

- email: `swiftpassion.com22@gmail.com`
- staff_name: `ศิวพร ถีติปริวัตร (อุ๊)`
- records ที่ match ใน `crm_data_imports`: 0

Recommendation:

- คง active ได้ ถ้ายังเป็นพนักงาน
- ไม่ต้อง map กับข้อมูลใดจนกว่าจะมี owner/import records
- ห้าม map ทับ owner ของคนอื่นเพื่อให้มีข้อมูลแสดง

## Canonical Staff Code ที่เสนอ

| owner_alias | proposed staff_code | สถานะ |
|---|---|---|
| สายฝน ราวิชัย (สายฝน) | `SAIFON` | PENDING |
| พรณกมล ดวงจันทร์ (แต้ว) | `TAEW` | PENDING |
| พรธนนันท์ กานต์รพีพร (หญิง) | `YING` | PENDING |
| กัญญพักฒ์ อิ่มยวง (เจี๊ยบ) | ~~`JEEB`~~ → merged into `NOONA` | **APPROVED — RETIRED (2026-07-23)** |
| ธัญญรัตน์ หอมระรื่น (เล็ก) | `LEK` | PENDING |
| จินดามณี คงมี (ครีม) | `CREAM` | PENDING |
| สุมนตรา ทัศน์ศรี (โก้) | `KO` | PENDING |

## Checklist ก่อนอนุมัติ Update จริง

| Checklist | Status |
|---|---|
| ยืนยัน email ที่ถูกต้องของ `JEEB` | N/A — `JEEB` retired, merged into `NOONA` (APPROVED 2026-07-23) |
| ยืนยันว่า owner ว่าง 730 rows ให้คง NULL | NEED_CONFIRM |
| ยืนยัน canonical staff_code ทั้งหมด | PENDING |
| ยืนยัน backup ก่อน update | PENDING |
| ยืนยัน update เฉพาะ normalized exact match | PENDING |
| ยืนยัน rollback plan | PENDING |
| ยืนยันให้ทดสอบ permission หลัง update | PENDING |

## Pseudo SQL ตัวอย่างเท่านั้น

ข้อความด้านล่างเป็น pseudo SQL เพื่ออธิบายแนวทางเท่านั้น

DO NOT RUN

```sql
-- DO NOT RUN
-- PSEUDO SQL ONLY
-- backup selected columns before any update
BACKUP crm_data_imports(id, owner, staff_code, customer_name, phone1, phone2, order_id, updated_at);

-- normalize only approved owner aliases by normalized exact match
FOR EACH approved_mapping:
  UPDATE crm_data_imports
  SET staff_code = approved_mapping.canonical_staff_code
  WHERE normalized(owner) = approved_mapping.owner_alias;

-- keep blank owner rows untouched
DO NOT UPDATE rows WHERE owner IS NULL OR owner = '';
```

## Final Decision

`JEEB` → `NOONA` merge: **APPROVED (2026-07-23)** — migration script prepared (`neon/manual_sql/202607_jeeb_to_noona_merge.sql`), execution pending real database access. See "ประเด็น JEEB" section above for full approved scope.

ส่วนที่เหลือยังไม่พร้อม update จริงจนกว่า:

1. owner ว่าง 730 rows ได้รับการยืนยันว่าจะคง NULL
2. ผู้บริหารอนุมัติ canonical staff_code ทั้งชุด (SAIFON/TAEW/YING/LEK/CREAM/KO — code-level canonical mapping ถูก implement แล้วใน `staff_identity.py` ตามคำสั่งงาน Owner Mapping 2026-07-23 แต่ยังไม่ได้ flip DB backfill/email-binding checklist ด้านล่างเป็น APPROVED)
3. มี backup และ rollback plan พร้อมใช้งานสำหรับส่วนที่เหลือ

