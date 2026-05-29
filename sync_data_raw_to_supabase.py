"""Legacy DATA_RAW to Supabase sync.

Disabled intentionally to reduce Supabase egress and database usage. CRM data
is now imported from Excel into Neon table crm_data_imports.
"""


def main() -> None:
    print("Legacy DATA_RAW Supabase sync is disabled. Use Excel import to Neon.")


if __name__ == "__main__":
    main()
