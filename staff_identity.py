"""Central staff identity resolution: staff_code as the durable key.

Two layers, kept deliberately separate:

1. CANONICAL_STAFF -- the six staff_codes explicitly confirmed by the
   business owner (2026-07-23 Owner Mapping review), each with a canonical
   full display name and the Thai nicknames/full-name variants that resolve
   to it. This is the only place aliases are hardcoded.
2. The live staff directory (crm_user_roles / crm_staff_options via
   neon_utils.fetch_owner_user_options) remains the source of truth for
   *which* staff_codes actually exist and are selectable -- this module
   never invents a dropdown entry that isn't backed by a real row. For the
   six canonical codes, the canonical full name overrides whatever is in the
   live row (fixing whitespace/formatting drift); for every other code
   (e.g. NOONA, or anyone added later), the live staff_name is used as-is.

This keeps identity decisions about specific individuals (who a code
belongs to) anchored to the database, while giving the six agreed codes a
robust, whitespace-proof alias resolver.
"""

import re
from typing import Optional

# Approved 2026-07-23 (Owner Mapping review). Do not add codes here without a
# similar explicit confirmation -- everyone else resolves through the live
# staff directory instead (see build_master_staff_directory below).
CANONICAL_STAFF = {
    "KO": {
        "full_name": "สุมนตรา ทัศน์ศรี (โก้)",
        "aliases": {"โก้", "สุมนตรา", "สุมนตรา ทัศน์ศรี", "สุมนตรา ทัศน์ศรี (โก้)"},
    },
    "CREAM": {
        "full_name": "จินดามณี คงมี (ครีม)",
        "aliases": {"ครีม", "จินดามณี", "จินดามณี คงมี", "จินดามณี คงมี (ครีม)"},
    },
    "LEK": {
        "full_name": "ธัญญรัตน์ หอมระรื่น (เล็ก)",
        "aliases": {"เล็ก", "ธัญญรัตน์", "ธัญญรัตน์ หอมระรื่น", "ธัญญรัตน์ หอมระรื่น (เล็ก)"},
    },
    "TAEW": {
        "full_name": "พรณกมล ดวงจันทร์ (แต้ว)",
        "aliases": {"แต้ว", "พรณกมล", "พรณกมล ดวงจันทร์", "พรณกมล ดวงจันทร์ (แต้ว)"},
    },
    "YING": {
        "full_name": "พรธนนันท์ กานต์รพีพร (หญิง)",
        "aliases": {"หญิง", "พรธนนันท์", "พรธนนันท์ กานต์รพีพร", "พรธนนันท์ กานต์รพีพร (หญิง)"},
    },
    "SAIFON": {
        "full_name": "สายฝน ราวิชัย (สายฝน)",
        "aliases": {"สายฝน", "สายฝน ราวิชัย", "สายฝน ราวิชัย (สายฝน)"},
    },
}

_WHITESPACE_RUN_RE = re.compile(r"\s+")


def _normalize(value) -> str:
    # Trim + collapse internal whitespace. Kept local (rather than importing
    # crm_data.common.collapse_whitespace) so this module has no import-order
    # coupling with the rest of the app and stays trivially unit-testable.
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return text
    return _WHITESPACE_RUN_RE.sub(" ", text)


def _build_alias_index() -> dict:
    index: dict = {}
    for code, entry in CANONICAL_STAFF.items():
        index[code] = code
        index[_normalize(entry["full_name"])] = code
        for alias in entry["aliases"]:
            index[_normalize(alias)] = code
    return index


_ALIAS_TO_CODE = _build_alias_index()


def resolve_canonical_staff_code(value) -> Optional[str]:
    """Resolve a Thai nickname, full name, or staff_code spelling variant to
    its canonical staff_code -- for the six explicitly-approved codes only.

    Returns None if `value` isn't a recognized alias. Callers must treat None
    as "not one of the six confirmed codes", not as "invalid" -- fall back to
    the live staff directory (build_master_staff_directory) for everyone else
    (e.g. NOONA, or staff added after this list was written).
    """
    text = _normalize(value)
    if not text:
        return None
    return _ALIAS_TO_CODE.get(text) or _ALIAS_TO_CODE.get(text.upper())


def build_master_staff_directory(rows: list) -> dict:
    """Build a staff_code -> canonical display name directory.

    `rows` is the live staff directory (as returned by
    neon_utils.fetch_owner_user_options -- dicts with staff_code/staff_name).
    Dedup key is always staff_code, never display name, so two different
    staff_codes that happen to render the same name can never collide or
    overwrite each other. For the six canonical codes the confirmed full
    name always wins over whatever the live row currently holds.
    """
    directory: dict = {}
    for row in rows:
        staff_code = _normalize((row or {}).get("staff_code")).upper()
        if not staff_code:
            continue
        if staff_code in CANONICAL_STAFF:
            directory[staff_code] = CANONICAL_STAFF[staff_code]["full_name"]
        else:
            staff_name = _normalize((row or {}).get("staff_name"))
            if staff_name:
                directory[staff_code] = staff_name
    return directory


def build_staff_directory_choices(rows: list) -> list:
    """Build deduped (staff_code, display_name) pairs for a dropdown, in the
    order staff_codes first appear in `rows`. Always keyed by staff_code --
    see build_master_staff_directory for why that matters.
    """
    directory = build_master_staff_directory(rows)
    ordered_codes: list = []
    seen = set()
    for row in rows:
        code = _normalize((row or {}).get("staff_code")).upper()
        if code and code not in seen and code in directory:
            ordered_codes.append(code)
            seen.add(code)
    return [(code, directory[code]) for code in ordered_codes]


def validate_canonical_pairing(staff_code, staff_name) -> Optional[str]:
    """Guard used by the User/Role admin page when creating or editing a
    crm_user_roles entry: for the six explicitly-approved codes only, catch a
    staff_code paired with the wrong person's name (e.g. a typo pairing
    TAEW's code with a different name). Returns None -- no objection -- for
    every staff_code outside the canonical six, since this page is exactly
    where genuinely new staff members get created and must not be blocked.
    """
    code = _normalize(staff_code).upper()
    if code not in CANONICAL_STAFF:
        return None
    name = _normalize(staff_name)
    if not name:
        return None
    expected = CANONICAL_STAFF[code]["full_name"]
    if name == expected or resolve_canonical_staff_code(name) == code:
        return None
    return f"Staff code '{code}' ควรใช้คู่กับชื่อ '{expected}' กรุณาตรวจสอบอีกครั้ง"


def validate_owner_staff_code(owner, staff_code, directory: dict) -> Optional[str]:
    """Validate a save payload's (owner, staff_code) pair against the master
    directory before it is persisted.

    Returns None when valid. Returns a short, user-safe Thai explanation
    (no internal identifiers, no secrets) when invalid:
      - staff_code missing
      - staff_code not present in the master directory
      - owner text present but does not correspond to that staff_code
    """
    code = _normalize(staff_code).upper()
    if not code:
        return "กรุณาระบุ Staff code ก่อนบันทึก"
    expected_name = directory.get(code)
    if expected_name is None:
        return "ไม่พบ Staff code นี้ในระบบ กรุณาเลือกจากรายชื่อที่มีอยู่"
    owner_norm = _normalize(owner)
    if not owner_norm:
        return None
    if owner_norm == expected_name:
        return None
    if resolve_canonical_staff_code(owner_norm) == code:
        return None
    return "ชื่อผู้ดูแลไม่ตรงกับ Staff code ที่เลือก กรุณาตรวจสอบอีกครั้ง"
