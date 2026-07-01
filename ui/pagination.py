from collections.abc import Sequence

import streamlit as st


DEFAULT_PAGE_SIZE_OPTIONS = (10, 25, 50, 100)


def get_pagination_state(
    *,
    key_prefix: str,
    page_size_options: Sequence[int] | None = None,
    page_key: str | None = None,
    page_size_key: str | None = None,
) -> tuple[int, int]:
    """Return normalized pagination state without rendering widgets."""
    options = _normalize_page_size_options(page_size_options)
    resolved_page_key = page_key or f"{key_prefix}_page"
    resolved_page_size_key = page_size_key or f"{key_prefix}_page_size"

    try:
        page_size = int(st.session_state.get(resolved_page_size_key, options[0]))
    except (TypeError, ValueError):
        page_size = options[0]
    if page_size not in options:
        page_size = options[0]

    try:
        current_page = max(int(st.session_state.get(resolved_page_key, 1)), 1)
    except (TypeError, ValueError):
        current_page = 1

    st.session_state[resolved_page_size_key] = page_size
    st.session_state[resolved_page_key] = current_page
    return page_size, current_page


def render_pagination(
    *,
    total_rows: int,
    page_size: int,
    current_page: int,
    key_prefix: str,
    page_size_options: Sequence[int] | None = None,
    page_key: str | None = None,
    page_size_key: str | None = None,
) -> tuple[int, int]:
    """Render the shared compact pagination controls and return active state."""
    options = _normalize_page_size_options(page_size_options)
    resolved_page_key = page_key or f"{key_prefix}_page"
    resolved_page_size_key = page_size_key or f"{key_prefix}_page_size"
    safe_total = max(int(total_rows or 0), 0)
    page_size = page_size if page_size in options else options[0]
    total_pages = max((safe_total - 1) // page_size + 1, 1)
    current_page = min(max(int(current_page or 1), 1), total_pages)

    if st.session_state.get(resolved_page_key) != current_page:
        st.session_state[resolved_page_key] = current_page
        st.rerun()

    def reset_page() -> None:
        st.session_state[resolved_page_key] = 1

    def select_page(target_page: int) -> None:
        st.session_state[resolved_page_key] = min(max(target_page, 1), total_pages)

    info_col, size_col = st.columns([3, 1])
    info_col.caption(f"หน้า {current_page:,} / {total_pages:,} · ทั้งหมด {safe_total:,} รายการ")
    size_col.selectbox(
        "จำนวนแถวต่อหน้า",
        options,
        key=resolved_page_size_key,
        on_change=reset_page,
    )

    controls_key = f"{key_prefix}_pagination_controls"
    st.markdown(
        f"""
<style>
.st-key-{controls_key} {{
  align-items: center !important;
  justify-content: flex-end !important;
  flex-wrap: wrap !important;
  gap: 8px !important;
}}
.st-key-{controls_key} [data-testid="stButton"] {{
  flex: 0 0 auto !important;
  width: auto !important;
}}
.st-key-{controls_key} [data-testid="stButton"] > button {{
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  min-width: 44px !important;
  width: auto !important;
  min-height: 36px !important;
  height: 36px !important;
  padding: 0 12px !important;
  white-space: nowrap !important;
  line-height: 1 !important;
  font-size: 13px !important;
  box-sizing: border-box !important;
}}
.st-key-{controls_key} [data-testid="stButton"] > button p {{
  margin: 0 !important;
  white-space: nowrap !important;
  overflow-wrap: normal !important;
  word-break: keep-all !important;
  line-height: 1 !important;
}}
</style>
""",
        unsafe_allow_html=True,
    )
    tokens = _page_tokens(current_page, total_pages)
    with st.container(
        key=controls_key,
        horizontal=True,
        horizontal_alignment="right",
        vertical_alignment="center",
        gap="small",
    ):
        st.button(
            "<",
            key=f"{key_prefix}_pagination_previous",
            disabled=current_page <= 1,
            on_click=select_page,
            args=(current_page - 1,),
            help="หน้าก่อนหน้า",
        )

        for index, token in enumerate(tokens, start=1):
            if token is None:
                st.button(
                    "...",
                    key=f"{key_prefix}_pagination_gap_{index}",
                    disabled=True,
                )
                continue
            st.button(
                str(token),
                key=f"{key_prefix}_pagination_page_{token}",
                type="primary" if token == current_page else "secondary",
                on_click=select_page,
                args=(token,),
                help=f"ไปหน้า {token}",
            )

        st.button(
            ">",
            key=f"{key_prefix}_pagination_next",
            disabled=current_page >= total_pages,
            on_click=select_page,
            args=(current_page + 1,),
            help="หน้าถัดไป",
        )
    return page_size, current_page


def _normalize_page_size_options(page_size_options: Sequence[int] | None) -> list[int]:
    raw_options = page_size_options or DEFAULT_PAGE_SIZE_OPTIONS
    options = list(dict.fromkeys(int(value) for value in raw_options if int(value) > 0))
    return options or list(DEFAULT_PAGE_SIZE_OPTIONS)


def _page_tokens(current_page: int, total_pages: int) -> list[int | None]:
    if total_pages <= 7:
        return list(range(1, total_pages + 1))

    visible = {1, total_pages, current_page - 1, current_page, current_page + 1}
    if current_page <= 3:
        visible.update(range(1, 5))
    if current_page >= total_pages - 2:
        visible.update(range(total_pages - 3, total_pages + 1))

    pages = sorted(page for page in visible if 1 <= page <= total_pages)
    tokens: list[int | None] = []
    for page in pages:
        if tokens and page - int(tokens[-1]) > 1:
            tokens.append(None)
        tokens.append(page)
    return tokens
