# UAT Result Template: Staff Code Permission Model

เอกสารนี้ใช้กรอกผล UAT ระหว่างทดสอบระบบ permission ที่ใช้ `staff_code` เป็น key หลัก

ขอบเขตการทดสอบ:
- ทดสอบบน environment ที่ deploy ล่าสุด
- CRM data อ่าน/เขียนจาก Neon PostgreSQL
- Supabase ใช้เฉพาะ Auth/Login
- ไม่ทดสอบ migration หรือ schema change ในรอบนี้

วันที่ทดสอบ: `YYYY-MM-DD`

ผู้ประสานงาน UAT: `ระบุชื่อ`

Environment / URL: `ระบุ URL`

## 1. UAT Summary

| Test Case | Tester | Result (PASS/FAIL) | Notes |
|---|---|---|---|
| EDITOR: Customers Owner Assignment |  |  |  |
| EDITOR: Export Customers XLSX |  |  |  |
| EDITOR: Update Customer URL |  |  |  |
| STAFF: Dashboard Own Data Only |  |  |  |
| STAFF: Follow-up Own Data Only |  |  |  |
| STAFF: Customer Detail Own Record |  |  |  |
| STAFF: Customer Detail Other Record Denied |  |  |  |
| Manual Order: STAFF Owner Lock |  |  |  |
| Manual Order: Multi SKU |  |  |  |
| Follow-up: STAFF Save Own Follow-up |  |  |  |
| Follow-up: STAFF Cannot Edit Other Owner |  |  |  |
| Supabase Auth Login / Logout |  |  |  |

## 2. Defect Log

| ID | Severity | Screen | Steps | Expected | Actual | Owner | Status |
|---|---|---|---|---|---|---|---|
| UAT-001 | High / Medium / Low |  |  |  |  |  | Open |
| UAT-002 | High / Medium / Low |  |  |  |  |  | Open |
| UAT-003 | High / Medium / Low |  |  |  |  |  | Open |

Severity guideline:
- High: ทำให้ permission ผิด, เห็นข้อมูลคนอื่น, บันทึกไม่ได้, หรือ workflow หลักพัง
- Medium: ใช้งานได้แต่มีผลต่อความถูกต้อง/ความเร็ว/ความสับสน
- Low: UI/ข้อความ/ความสวยงาม ที่ไม่กระทบ workflow หลัก

## 3. Blocking Issues

| Issue | Impact | Required Fix Before SQL Normalize? (Yes/No) | Notes |
|---|---|---|---|
|  |  |  |  |
|  |  |  |  |

## 4. Final Sign-off

เลือกสถานะหลังจบ UAT:

- [ ] Ready for SQL Normalize
- [ ] Not Ready
- [ ] Blocking Issues Found

Sign-off checklist:

- [ ] EDITOR เห็นและจัดการข้อมูลได้ตามสิทธิ์
- [ ] STAFF เห็นเฉพาะข้อมูลตาม `staff_code` ของตัวเองในหน้าที่จำกัดสิทธิ์
- [ ] Customers list ยังใช้ตรวจสอบลูกค้าทั้งหมดได้ตาม requirement ล่าสุด
- [ ] Action สำคัญ เช่น Export, Update URL, Assign Owner จำกัดเฉพาะ EDITOR
- [ ] Manual Order บันทึก `owner` และ `staff_code` ถูกต้อง
- [ ] Follow-up บันทึกได้เฉพาะ record ที่มีสิทธิ์
- [ ] ไม่พบการเรียก Supabase Database/REST ใน flow CRM data
- [ ] ไม่มี defect ระดับ High ค้างอยู่

ผู้อนุมัติ: `ระบุชื่อ`

วันที่อนุมัติ: `YYYY-MM-DD`

หมายเหตุเพิ่มเติม:

```text
กรอกข้อสังเกตหรือเงื่อนไขก่อนเริ่ม SQL Normalize จริง
```
