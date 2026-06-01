from datetime import date
from io import BytesIO

import pandas as pd
import streamlit as st

import neon_utils as neon
from auth_utils import ROLE_TELESELL_ALIASES, can_manage_all, current_user, require_login
from nav_utils import render_sidebar_nav


BATCH_SIZE = 500
PREVIEW_ROWS = 100

CRM_FIELD_LABELS = {
    "order_date": "วันที่สั่งซื้อ",
    "order_id": "เลขคำสั่งซื้อ",
    "sales_channel": "ช่องทางขาย",
    "sku": "SKU",
    "product_name": "สินค้า",
    "quantity": "จำนวน",
    "total_amount": "ราคา",
    "payment_method": "วิธีการชำระ",
    "carrier": "ขนส่ง",
    "tracking_no": "หมายเลขพัสดุ",
    "url": "URL",
    "customer_name": "ชื่อลูกค้า",
    "phone1": "เบอร์โทร",
    "phone2": "เบอร์สำรอง",
    "shipping_address": "ที่อยู่จัดส่ง",
    "subdistrict": "ตำบล",
    "city": "อำเภอ",
    "province": "จังหวัด",
    "postal_code": "รหัสไปรษณีย์",
    "billing_staff": "พนักงานเปิดบิล",
    "upsell_staff": "พนักงานอัพเซลล์",
    "owner": "พนักงานดูแล",
    "order_status": "สถานะคำสั่งซื้อ",
}

CRM_FIELD_SYNONYMS = {
    "order_date": ["วันที่สั่งซื้อ", "วันที่", "date", "order_date"],
    "order_id": ["เลขคำสั่งซื้อ", "เลขออเดอร์", "order_id"],
    "sales_channel": ["ช่องทางขาย", "ช่องทาง", "channel"],
    "sku": ["SKU", "sku"],
    "product_name": ["สินค้า", "ชื่อสินค้า", "product", "product_name"],
    "quantity": ["จำนวน", "qty", "quantity"],
    "total_amount": ["ราคา", "ยอดขาย", "ยอดขายรวม", "total_amount", "price"],
    "payment_method": ["วิธีการชำระ", "วิธีชำระ", "payment_method"],
    "carrier": ["ขนส่ง", "บริษัทขนส่ง", "carrier", "shipping"],
    "tracking_no": ["หมายเลขพัสดุ", "เลขพัสดุ", "tracking_no"],
    "url": ["URL", "url", "ลิงก์"],
    "customer_name": ["ชื่อลูกค้า", "ลูกค้า", "customer_name", "customer"],
    "phone1": ["เบอร์โทร", "เบอร์โทรติดต่อ", "phone1", "phone"],
    "phone2": ["เบอร์สำรอง", "เบอร์โทรสำรอง", "phone2"],
    "shipping_address": ["ที่อยู่จัดส่ง", "ที่อยู่", "address"],
    "subdistrict": ["ตำบล", "แขวง", "subdistrict"],
    "city": ["อำเภอ", "เขต", "เมือง", "city", "district"],
    "province": ["จังหวัด", "province"],
    "postal_code": ["รหัสไปรษณีย์", "postcode", "postal_code"],
    "billing_staff": ["พนักงานเปิดบิล", "ผู้ขาย", "billing_staff"],
    "upsell_staff": ["พนักงานอัพเซลล์", "พนักงาน UPSELL", "upsell_staff"],
    "owner": ["พนักงานดูแล", "ผู้ดูแล", "owner", "care_staff"],
    "order_status": ["สถานะคำสั่งซื้อ", "สถานะ", "order_status"],
}


st.set_page_config(page_title="นำเข้าข้อมูลลูกค้า", layout="wide")


def main() -> None:
    inject_css()
    render_sidebar_nav()
    st.title("นำเข้าข้อมูลลูกค้า")
    st.caption("อัปโหลด Excel .xlsx เข้า Neon table crm_data_imports พร้อม preview, mapping, validation และ import history")

    auth_user = require_login()
    user = current_user() or auth_user
    is_editor = can_manage_all(user)
    is_telesell = neon.clean(user.get("role")) in ROLE_TELESELL_ALIASES
    if not is_editor and not is_telesell:
        st.warning("หน้านี้ใช้ได้เฉพาะ EDITOR และพนักงานที่มีสิทธิเพิ่มคำสั่งซื้อ")
        st.stop()

    neon.require_neon_config()
    neon.ensure_crm_data_imports_schema()
    render_manual_order_form(user, is_editor)
    if is_editor:
        render_excel_import(user)
        render_import_history()
    else:
        st.info("บัญชีพนักงานเพิ่มคำสั่งซื้อได้ แต่ไม่มีสิทธินำเข้า Excel หรือจัดการ import history")


def inject_css() -> None:
    st.markdown(
        """
<style>
:root {
  --crm-bg:#fff8f1;
  --crm-panel:#ffffff;
  --crm-border:#fed7aa;
  --crm-border-strong:#fb923c;
  --crm-text:#111827;
  --crm-muted:#64748b;
  --crm-accent:#f97316;
  --crm-accent-dark:#ea580c;
  --crm-shadow:0 18px 44px rgba(124,45,18,.08);
}
.stApp { background:var(--crm-bg); color:var(--crm-text); }
.block-container { max-width:1180px; padding-top:2.4rem; padding-bottom:3rem; }
h1 {
  color:var(--crm-text) !important;
  border-left:6px solid var(--crm-accent);
  padding-left:14px;
  letter-spacing:0;
}
h2, h3, p, label, span, div[data-testid="stMarkdownContainer"] { color:var(--crm-text); }
[data-testid="stCaptionContainer"] { color:var(--crm-muted) !important; }
[data-testid="stForm"],
[data-testid="stExpander"] {
  background:linear-gradient(180deg,#ffffff 0%,#fffaf5 100%) !important;
  border:1px solid var(--crm-border) !important;
  border-radius:12px !important;
  box-shadow:var(--crm-shadow);
}
.stTextInput label, .stTextArea label, .stSelectbox label, .stNumberInput label, .stFileUploader label, .stCheckbox label {
  color:#7c2d12 !important;
  font-weight:750 !important;
}
div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
textarea,
input {
  background:#ffffff !important;
  color:var(--crm-text) !important;
  -webkit-text-fill-color:var(--crm-text) !important;
  border:1px solid var(--crm-border-strong) !important;
  border-radius:10px !important;
}
div[data-baseweb="input"] > div:focus-within,
div[data-baseweb="select"] > div:focus-within,
textarea:focus,
input:focus {
  border-color:var(--crm-accent-dark) !important;
  box-shadow:0 0 0 3px rgba(249,115,22,.16) !important;
  outline:none !important;
}
div.stButton > button,
div.stDownloadButton > button,
div.stFormSubmitButton > button {
  background:var(--crm-accent) !important;
  color:#ffffff !important;
  border:1px solid var(--crm-accent-dark) !important;
  border-radius:10px !important;
  font-weight:800 !important;
}
[data-testid="stAlert"] {
  border-radius:10px !important;
  color:#111827 !important;
}
[data-testid="stAlert"] * { color:#111827 !important; }
[data-testid="stExpander"] details,
[data-testid="stExpander"] details summary,
[data-testid="stExpander"] details summary *,
[data-testid="stFileUploader"] section,
[data-testid="stFileUploader"] section *,
div[data-baseweb="base-input"],
div[data-baseweb="textarea"] {
  background:#ffffff !important;
  color:var(--crm-text) !important;
  -webkit-text-fill-color:var(--crm-text) !important;
}
[data-testid="stFileUploader"] section {
  border:1px dashed var(--crm-border-strong) !important;
  border-radius:12px !important;
}
[data-testid="stExpander"] details summary {
  border:1px solid var(--crm-border) !important;
  border-radius:12px !important;
}
.crm-manual-card {
  background:#ffffff;
  border:1px solid var(--crm-border);
  border-radius:14px;
  padding:18px;
  box-shadow:var(--crm-shadow);
  margin-bottom:22px;
}
.crm-manual-meta {
  color:var(--crm-muted);
  font-size:14px;
  margin-bottom:12px;
}
</style>
""",
        unsafe_allow_html=True,
    )


def render_manual_order_form(user: dict, is_editor: bool) -> None:
    st.subheader("เพิ่มคำสั่งซื้อ")
    st.markdown(
        '<div class="crm-manual-meta">พนักงานเพิ่มคำสั่งซื้อได้ทีละรายการ ส่วนการนำเข้า Excel ใช้ได้เฉพาะ EDITOR</div>',
        unsafe_allow_html=True,
    )
    staff_options = []
    if is_editor:
        try:
            staff_options = neon.fetch_staff_options(active_only=True)
        except Exception as exc:
            st.warning(f"โหลดรายชื่อพนักงานไม่สำเร็จ: {exc}")

    with st.form("manual_order_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        order_id = col1.text_input("หมายเลขคำสั่งซื้อ")
        customer_name = col2.text_input("ชื่อลูกค้า")
        phone_col1, phone_col2 = st.columns(2)
        phone1 = phone_col1.text_input("เบอร์โทร")
        phone2 = phone_col2.text_input("เบอร์สำรอง")
        product_name = st.text_input("ชื่อสินค้า")
        url = st.text_input("URL")
        order_date = date.today().isoformat()
        st.caption(f"วันที่สร้างคำสั่งซื้อ: {order_date}")

        owner = neon.clean(user.get("staff_name"))
        staff_code = neon.clean(user.get("staff_code"))
        if is_editor:
            labels = [staff_label(row) for row in staff_options]
            if labels:
                selected_label = st.selectbox("ผู้ดูแล", labels, index=0, placeholder="เลือกผู้ดูแล")
                selected_staff = staff_options[labels.index(selected_label)] if selected_label in labels else {}
                owner = neon.clean(selected_staff.get("staff_name"))
                staff_code = neon.clean(selected_staff.get("staff_code")) or neon.owner_to_staff_code(owner)
            else:
                owner = st.text_input("ผู้ดูแล")
                staff_code = neon.owner_to_staff_code(owner)
        else:
            owner = owner or staff_code
            st.text_input("ผู้ดูแล", value=owner or "-", disabled=True)

        submitted = st.form_submit_button("บันทึกคำสั่งซื้อ", use_container_width=True)

    if not submitted:
        return

    errors = []
    if not neon.clean(order_id):
        errors.append("กรุณากรอกหมายเลขคำสั่งซื้อ")
    if not neon.clean(customer_name):
        errors.append("กรุณากรอกชื่อลูกค้า")
    if not neon.normalize_phone(phone1):
        errors.append("กรุณากรอกเบอร์โทร")
    if not neon.clean(product_name):
        errors.append("กรุณากรอกชื่อสินค้า")
    if not owner:
        errors.append("กรุณาระบุผู้ดูแล")
    if errors:
        st.error(" / ".join(errors))
        return

    try:
        result = neon.upsert_manual_order(
            {
                "order_id": order_id,
                "customer_name": customer_name,
                "phone1": phone1,
                "phone2": phone2,
                "product_name": product_name,
                "url": url,
                "order_date": order_date,
                "owner": owner,
                "staff_code": staff_code,
                "uploaded_by": neon.clean(user.get("email")),
            }
        )
    except Exception as exc:
        st.error(f"บันทึกคำสั่งซื้อไม่สำเร็จ: {exc}")
        return

    action_text = "อัปเดตข้อมูลเดิม" if result.get("action") == "updated" else "สร้างประวัติคำสั่งซื้อใหม่"
    st.cache_data.clear()
    st.success(f"บันทึกสำเร็จ: {action_text}")


def staff_label(row: dict) -> str:
    name = neon.clean(row.get("staff_name"))
    code = neon.clean(row.get("staff_code"))
    return f"{name} ({code})" if code and code != name else name


def render_excel_import(auth_user: dict) -> None:
    headers = list(CRM_FIELD_LABELS.values())
    st.download_button(
        "ดาวน์โหลดฟอร์ม Excel (.xlsx)",
        data=build_xlsx_template(headers, "crm_data_imports"),
        file_name="crm_data_imports_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    uploaded = st.file_uploader("อัปโหลดไฟล์ .xlsx", type=["xlsx"], key="neon_crm_upload")
    if not uploaded:
        st.info("อัปโหลดไฟล์ .xlsx แล้วระบบจะให้เลือก worksheet, mapping column และ preview ก่อน import")
        return

    try:
        excel = pd.ExcelFile(uploaded)
    except Exception as exc:
        st.error(f"อ่านไฟล์ Excel ไม่สำเร็จ: {exc}")
        return

    sheet_name = st.selectbox("Worksheet", excel.sheet_names, key="neon_import_sheet")
    header_row = st.number_input("แถวหัวตาราง", min_value=1, value=1, step=1, key="neon_import_header_row")
    try:
        df = pd.read_excel(excel, sheet_name=sheet_name, header=int(header_row) - 1, dtype=str).fillna("")
    except Exception as exc:
        st.error(f"อ่าน worksheet ไม่สำเร็จ: {exc}")
        return

    df = df[df.apply(lambda row: any(neon.clean(value) for value in row), axis=1)].reset_index(drop=True)
    if df.empty:
        st.warning("ไม่พบข้อมูลหลังแถวหัวตารางที่เลือก")
        return

    missing_headers = [label for label in headers if label not in df.columns]
    if missing_headers:
        st.warning("หัวตารางไม่ครบตามฟอร์มมาตรฐาน: " + ", ".join(missing_headers))

    st.subheader("Mapping Columns")
    mapping = render_mapping(df.columns)
    mapping_error = validate_mapping(mapping)
    if mapping_error:
        st.error(mapping_error)
        return

    batch_id = st.session_state.setdefault("neon_current_import_batch_id", neon.new_batch_id())
    records = [
        neon.build_record_from_mapping(
            row.to_dict(),
            mapping,
            batch_id,
            uploaded.name,
            sheet_name,
            int(index) + int(header_row) + 1,
            neon.clean(auth_user.get("email")),
        )
        for index, row in df.iterrows()
    ]

    duplicate_count = count_duplicate_records(records)
    invalid_count = sum(1 for record in records if record["import_status"] == "invalid")
    try:
        import_plan = neon.analyze_import_records(records)
    except Exception as exc:
        st.error(f"ตรวจข้อมูลซ้ำจาก Neon ไม่สำเร็จ: {exc}")
        return

    st.subheader("Preview")
    summary = import_plan["summary"]
    metric_cols = st.columns(4)
    metric_cols[0].metric("ทั้งหมด", f"{len(records):,}")
    metric_cols[1].metric("จะนำเข้า", f"{summary['insert']:,}")
    metric_cols[2].metric("จะไม่นำเข้า", f"{summary['skip']:,}")
    metric_cols[3].metric("เบอร์ซ้ำที่ merge", f"{summary['phone_duplicate']:,}")
    st.caption(f"invalid {invalid_count:,} แถว / ซ้ำในไฟล์ {duplicate_count:,} แถว")

    skipped_df = pd.DataFrame(import_plan["skipped_records"])
    if skipped_df.empty:
        st.success("ไม่พบข้อมูลที่จะถูกกันออกจาก import")
    else:
        st.warning("รายการด้านล่างจะไม่นำเข้า กรุณาแก้ไฟล์แล้ว import ใหม่หากต้องการนำเข้ารายการเหล่านี้")
        st.dataframe(skipped_df.head(PREVIEW_ROWS), use_container_width=True)

    phone_dup_df = pd.DataFrame(import_plan["phone_duplicate_records"])
    if not phone_dup_df.empty:
        with st.expander(f"เบอร์ซ้ำในฐานข้อมูลที่จะ merge url/owner {len(phone_dup_df):,} รายการ", expanded=False):
            st.dataframe(phone_dup_df.head(PREVIEW_ROWS), use_container_width=True)

    display_columns = [
        "customer_name",
        "phone1",
        "phone2",
        "product_name",
        "sku",
        "order_date",
        "province",
        "city",
        "postal_code",
        "tracking_no",
        "carrier",
        "order_status",
        "total_amount",
        "owner",
        "import_status",
        "validation_error",
    ]
    with st.expander("ดูตัวอย่างข้อมูลทั้งหมดก่อน import", expanded=False):
        st.dataframe(pd.DataFrame(records).head(PREVIEW_ROWS)[display_columns], use_container_width=True)
    st.caption(f"ทั้งหมด {len(records):,} แถว / invalid {invalid_count:,} แถว / ซ้ำในไฟล์ {duplicate_count:,} แถว")
    if duplicate_count:
        st.warning("พบข้อมูลซ้ำในไฟล์เดียวกันตาม key เลขคำสั่งซื้อ + เบอร์โทร + เบอร์สำรอง + หมายเลขพัสดุ")

    same_file = [
        row for row in neon.fetch_import_history()
        if neon.clean(row.get("source_file_name")) == neon.clean(uploaded.name)
        and neon.clean(row.get("sheet_name")) == neon.clean(sheet_name)
    ]
    if same_file:
        st.warning("เคย import ไฟล์และ worksheet ชื่อนี้แล้ว ถ้าต้องการ import ซ้ำให้ยืนยันเพิ่ม")
    confirm_same_file = True
    if same_file:
        confirm_same_file = st.checkbox("ยืนยัน import ซ้ำไฟล์/worksheet เดิม", key="confirm_same_file_import")
    confirm_import = st.checkbox("ยืนยัน import เข้า Neon crm_data_imports", key="confirm_neon_import")

    if st.button("Import เข้า Neon", disabled=not confirm_import or not confirm_same_file, use_container_width=True):
        progress = st.progress(0)
        try:
            import_count = max(summary["insert"], 1)
            for current in range(0, summary["insert"], BATCH_SIZE):
                progress.progress(min(current / import_count, 1.0))
            neon.insert_import_records(records, batch_size=BATCH_SIZE)
            progress.progress(1.0)
        except Exception as exc:
            st.error(f"Import ไม่สำเร็จ และ rollback batch นี้แล้ว: {exc}")
            return
        st.info(f"สรุป import: นำเข้า {summary['insert']:,} แถว / merge เบอร์ซ้ำ {summary['phone_duplicate']:,} รายการ / กันออก {summary['skip']:,} แถว")
        st.session_state.neon_current_import_batch_id = neon.new_batch_id()
        st.success(f"Import สำเร็จ {len(records):,} แถว เข้า batch {batch_id}")
        st.cache_data.clear()
        st.rerun()


def render_mapping(columns) -> dict[str, str]:
    options = [""] + [str(column) for column in columns]
    mapping: dict[str, str] = {}
    cols = st.columns(3)
    for index, (field, label) in enumerate(CRM_FIELD_LABELS.items()):
        default = auto_match_field(field, columns)
        mapping[field] = cols[index % 3].selectbox(
            label,
            options,
            index=options.index(default) if default in options else 0,
            key=f"neon_map_{field}",
        )
    return mapping


def auto_match_field(field: str, columns) -> str:
    lower_map = {neon.clean(column).lower(): str(column) for column in columns}
    for candidate in CRM_FIELD_SYNONYMS.get(field, [field]):
        matched = lower_map.get(neon.clean(candidate).lower())
        if matched:
            return matched
    return ""


def validate_mapping(mapping: dict[str, str]) -> str:
    if not mapping.get("customer_name"):
        return "ต้องเลือก mapping สำหรับ customer_name / ชื่อลูกค้า"
    if not mapping.get("phone1") and not mapping.get("phone2"):
        return "ต้องเลือก mapping สำหรับ phone1 หรือ phone2 อย่างน้อยหนึ่งช่อง"
    return ""


def count_duplicate_records(records: list[dict]) -> int:
    seen = set()
    duplicate_count = 0
    for record in records:
        key = record.get("dedupe_key")
        if key in seen:
            duplicate_count += 1
        seen.add(key)
    return duplicate_count


def render_import_history() -> None:
    st.subheader("Import History")
    try:
        rows = neon.fetch_import_history()
    except Exception as exc:
        st.warning(f"ยังอ่าน import history ไม่ได้: {exc}")
        return
    if not rows:
        st.info("ยังไม่มีประวัติการ import")
        return

    history_df = pd.DataFrame(rows)
    st.dataframe(history_df, use_container_width=True)

    batch_options = [neon.clean(row.get("import_batch_id")) for row in rows if neon.clean(row.get("import_batch_id"))]
    selected_batch = st.selectbox("เลือก batch ที่ต้องการล้าง", [""] + batch_options, key="delete_batch_select")
    confirm_delete = st.checkbox("ยืนยันล้าง batch นี้", key="confirm_delete_neon_batch")
    if st.button("ล้าง batch ที่ import ผิด", disabled=not selected_batch or not confirm_delete, use_container_width=True):
        try:
            deleted = neon.delete_import_batch(selected_batch)
        except Exception as exc:
            st.error(f"ล้าง batch ไม่สำเร็จ: {exc}")
            return
        st.success(f"ล้าง batch สำเร็จ {deleted:,} แถว")
        st.cache_data.clear()
        st.rerun()


def build_xlsx_template(headers: list[str], sheet_name: str) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(columns=headers).to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()


if __name__ == "__main__":
    main()
