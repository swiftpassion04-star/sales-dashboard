ROLE_ADMIN = "ADMIN"
ROLE_EDITOR = "EDITOR"
ROLE_STAFF = "พนักงาน"
ROLE_VIEWER = "ทั่วไป"
ROLE_TELESELL = ROLE_STAFF
ROLE_STAFF_READONLY = ROLE_VIEWER

ROLE_TELESELL_ALIASES = {ROLE_TELESELL, "TELESELL"}
ROLE_STAFF_ALIASES = {ROLE_STAFF_READONLY, "STAFF"}
ROLE_USER_ALIASES = {"USER"}
SYSTEM_VIEW_ROLES = {ROLE_EDITOR}
ORDER_DELETE_ROLES = {ROLE_EDITOR, ROLE_STAFF, "STAFF"}


def clean(value) -> str:
    return str(value or "").strip()


def normalize_role(role) -> str:
    value = clean(role)
    upper_value = value.upper()
    if upper_value in {"ADMIN", "EDITOR", "TELESELL", "STAFF", "USER"}:
        return upper_value
    return value


def user_role(user: dict | None) -> str:
    return normalize_role((user or {}).get("role"))


def _normalized_roles(roles: set[str]) -> set[str]:
    return {normalize_role(role) for role in roles}


def is_telesell(user: dict | None) -> bool:
    return user_role(user) in _normalized_roles(ROLE_TELESELL_ALIASES)


def is_staff_limited(user: dict | None) -> bool:
    return user_role(user) in _normalized_roles(
        ROLE_TELESELL_ALIASES | ROLE_STAFF_ALIASES | ROLE_USER_ALIASES
    )


def can_manage_all(user: dict | None) -> bool:
    return user_role(user) in {ROLE_ADMIN, ROLE_EDITOR}


def can_edit_users(user: dict | None) -> bool:
    return can_manage_all(user)


def can_edit_products(user: dict | None) -> bool:
    return can_manage_all(user)


def can_import_excel(user: dict | None) -> bool:
    return can_manage_all(user)


def can_add_manual_order(user: dict | None) -> bool:
    return can_manage_all(user) or is_telesell(user)


def can_export_customers(user: dict | None) -> bool:
    return user_role(user) == ROLE_EDITOR


def can_assign_customer_owner(user: dict | None) -> bool:
    return user_role(user) == ROLE_EDITOR


def can_manage_customer_records(user: dict | None) -> bool:
    return user_role(user) == ROLE_EDITOR


def can_delete_order(user: dict | None) -> bool:
    return user_role(user) in _normalized_roles(ORDER_DELETE_ROLES)


def can_view_system_page(user: dict | None) -> bool:
    return user_role(user) in _normalized_roles(SYSTEM_VIEW_ROLES)


def can_manage_system_page(user: dict | None) -> bool:
    return can_manage_all(user)


def can_view_followup(user: dict | None) -> bool:
    return user_role(user) == ROLE_EDITOR or is_staff_limited(user)


def can_view_followup_owner_filter(user: dict | None) -> bool:
    return user_role(user) == ROLE_EDITOR


def can_edit_customer_lead(user: dict | None, customer) -> bool:
    if not user:
        return False
    if user_role(user) == ROLE_EDITOR:
        return True
    if not is_telesell(user):
        return False

    staff_code = clean(user.get("staff_code"))
    if not staff_code:
        return False

    customer_staff_code = ""
    for key in ("staff_code",):
        try:
            value = customer.get(key)
        except AttributeError:
            value = ""
        if clean(value):
            customer_staff_code = clean(value)

    return bool(customer_staff_code and customer_staff_code == staff_code)
