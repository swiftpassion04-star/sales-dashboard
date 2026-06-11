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
| JEEB owner ยังไม่มี email ที่ชัดเจน | 3,087 | owner = `กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)`, staff_code = `เจี๊ยบ` | map เป็น canonical `JEEB` หลังยืนยัน email | 1. ผูกกับ email ที่มีอยู่ 2. สร้าง user ใหม่ 3. คงไว้ก่อน | ให้ผู้บริหารระบุ email ที่ถูกต้องก่อน update | NEED_CONFIRM |
| owner/staff_code ว่าง | 730 | owner = NULL/ว่าง, staff_code = NULL/ว่าง | คง `staff_code = NULL` | 1. คง NULL 2. สร้าง bucket UNASSIGNED 3. assign ให้คนใดคนหนึ่ง | คง NULL และแสดงผลว่า “ยังไม่มอบหมาย” | NEED_CONFIRM |
| หนูนา มี user role แต่ไม่มี owner records | 0 current records | `swiftpassion.com19@gmail.com` / `พรนภา นันที (หนูนา)` | คง user active ถ้ายังเป็นพนักงาน | 1. คง active 2. inactive 3. map กับ owner อื่น | คง active แต่ไม่ map กับข้อมูลใดจนกว่าจะมี owner/import records | PENDING |
| อุ๊ มี user role แต่ไม่มี owner records | 0 current records | `swiftpassion.com22@gmail.com` / `ศิวพร ถีติปริวัตร (อุ๊)` | คง user active ถ้ายังเป็นพนักงาน | 1. คง active 2. inactive 3. map กับ owner อื่น | คง active แต่ไม่ map กับข้อมูลใดจนกว่าจะมี owner/import records | PENDING |
| Canonical staff_code หลัก | 17,369 | ใช้ทั้งชื่อเล่นและชื่อเต็มไทย | normalize เป็น code อังกฤษตัวใหญ่ | 1. ใช้ code อังกฤษ 2. ใช้ชื่อเต็มไทย 3. ใช้ชื่อเล่นไทย | ใช้ code อังกฤษตัวใหญ่ถาวร | PENDING |

## ประเด็น JEEB

ข้อมูลที่พบ:

- owner: `กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)`
- records: 3,087
- current staff_code: `เจี๊ยบ`
- proposed canonical staff_code: `JEEB`
- current matching user role: ยังไม่พบ email/user role ที่ match ชัดเจน

สิ่งที่ต้องตัดสินใจ:

1. ผู้บริหารต้องระบุ email ที่ถูกต้องสำหรับ `JEEB`
2. ถ้ามี user อยู่แล้ว ให้เพิ่ม/แก้ row ใน `crm_user_roles` ให้ใช้:
   - `staff_code = JEEB`
   - `staff_name = กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)`
3. ถ้ายังไม่มี user ให้สร้าง user ใน Supabase Auth ก่อน แล้วเพิ่ม mapping ใน `crm_user_roles`

Recommended choice:

- รอผู้บริหารยืนยัน email ก่อน
- ห้าม normalize records 3,087 แถวนี้จนกว่าจะมี owner ของ login ที่ชัดเจน

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
| กัญญพักฒ์ อิ่มยวง (เจี๊ยบ) | `JEEB` | NEED_CONFIRM |
| ธัญญรัตน์ หอมระรื่น (เล็ก) | `LEK` | PENDING |
| จินดามณี คงมี (ครีม) | `CREAM` | PENDING |
| สุมนตรา ทัศน์ศรี (โก้) | `KO` | PENDING |

## Checklist ก่อนอนุมัติ Update จริง

| Checklist | Status |
|---|---|
| ยืนยัน email ที่ถูกต้องของ `JEEB` | NEED_CONFIRM |
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

ยังไม่พร้อม update จริงจนกว่า:

1. `JEEB` มี email ที่ยืนยันแล้ว
2. owner ว่าง 730 rows ได้รับการยืนยันว่าจะคง NULL
3. ผู้บริหารอนุมัติ canonical staff_code ทั้งชุด
4. มี backup และ rollback plan พร้อมใช้งาน

