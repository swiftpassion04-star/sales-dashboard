"""Legacy CRM customers to Supabase sync.

Disabled intentionally. Customer data now lives in Neon crm_data_imports and is
managed through the Streamlit Excel import workflow.
"""


def main() -> None:
    print("Legacy CRM customers Supabase sync is disabled. Use Excel import to Neon.")


if __name__ == "__main__":
    main()
