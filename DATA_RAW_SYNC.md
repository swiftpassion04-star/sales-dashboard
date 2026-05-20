# DATA_RAW Sync

ระบบนี้ใช้สำหรับซิงก์ Google Sheet `DATA_RAW` จากไฟล์ DATA 2565-2569 เข้า Supabase table `order_history`
แล้วให้หน้า Streamlit `customers` ค้นประวัติลูกค้า, ผู้ขาย, ที่อยู่จัดส่ง และรายการสินค้าได้จากฐานกลาง

## Data Sources

| ปี | Spreadsheet ID | Sheet |
| --- | --- | --- |
| 2565 | `1Q9CyZi5ezvthVABg-aw6LvrYtSp7qRHiEr4pVMGMKHg` | `DATA_RAW` |
| 2566 | `1Up4Vnx5fjxQMl6oEgFEpaJV9D8s4_pnEpIi0OS4LD08` | `DATA_RAW` |
| 2567 | `1U2CJ0HIcANRYNSlMSOun5_2RT4ElVFzoMaQMhZ4XD7s` | `DATA_RAW` |
| 2568 | `1FdHmaZ3eesHbF5WO5dZEDKSq9AmlNqKPD056Fa-yfuI` | `DATA_RAW` |
| 2569 | `1LewCpziyieVJ_hnV2KYzXW7ZE43Nj5Yg7Lp2lsIF5o4` | `DATA_RAW` |

## GitHub Actions Secrets

ตั้งค่าใน GitHub repo > Settings > Secrets and variables > Actions

- `CRM_SUPABASE_URL`
- `CRM_SUPABASE_SERVICE_KEY`
- `GOOGLE_SERVICE_ACCOUNT_JSON`

`GOOGLE_SERVICE_ACCOUNT_JSON` คือเนื้อหา JSON ทั้งไฟล์ของ Google service account
และ service account ต้องมีสิทธิ์อ่านทุกไฟล์ DATA 2565-2569

## Streamlit Secrets

ตั้งค่าใน Streamlit Cloud > App > Settings > Secrets

```toml
CRM_SUPABASE_URL = "https://hilncnvpmroslecwzsns.supabase.co"
CRM_SUPABASE_ANON_KEY = "..."
CRM_SUPABASE_SERVICE_KEY = "..."
CRM_SYNC_ADMIN_PASSWORD = "ตั้งรหัสสำหรับปุ่มหยุด/รันต่อ"
```

หน้า `DATA_RAW Sync` ใช้ `CRM_SYNC_ADMIN_PASSWORD` เพื่อป้องกันไม่ให้คนทั่วไปกดหยุดซิงก์

## วิธีรัน

- อัตโนมัติ: GitHub Actions จะรันทุก 30 นาที
- รันทันที: GitHub repo > Actions > Sync DATA_RAW to Supabase > Run workflow
- หยุดรอบถัดไป/หยุดเมื่อ worker ถึง checkpoint: เปิดหน้า `DATA_RAW Sync` ใน Streamlit แล้วกด `หยุดรัน DATA_RAW`
- รันต่อ: กด `รันต่อรอบถัดไป`

## การกันข้อมูลซ้ำ

ระบบใช้ `source_key = ปีไฟล์ + เลขคำสั่งซื้อ`
เช่น `2565_OD221201003167`

ถ้า import ซ้ำ ระบบจะ update record เดิม ไม่เพิ่มแถวซ้ำ
