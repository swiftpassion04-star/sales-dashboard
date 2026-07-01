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

    tokens = _page_tokens(current_page, total_pages)
    columns = st.columns([4, *([0.7] * (len(tokens) + 2)), 4])
    controls = columns[1:-1]
    controls[0].button(
        "<",
        key=f"{key_prefix}_pagination_previous",
        disabled=current_page <= 1,
        on_click=select_page,
        args=(current_page - 1,),
        use_container_width=True,
        help="หน้าก่อนหน้า",
    )

    for index, token in enumerate(tokens, start=1):
        if token is None:
            controls[index].button(
                "...",
                key=f"{key_prefix}_pagination_gap_{index}",
                disabled=True,
                use_container_width=True,
            )
            continue
        controls[index].button(
            str(token),
            key=f"{key_prefix}_pagination_page_{token}",
            type="primary" if token == current_page else "secondary",
            on_click=select_page,
            args=(token,),
            use_container_width=True,
            help=f"ไปหน้า {token}",
        )

    controls[-1].button(
        ">",
        key=f"{key_prefix}_pagination_next",
        disabled=current_page >= total_pages,
        on_click=select_page,
        args=(current_page + 1,),
        use_container_width=True,
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
