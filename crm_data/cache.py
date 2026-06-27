def clear_cached_data_functions(*functions) -> None:
    """Clear only the Streamlit cached functions passed in."""
    for function in functions:
        clear = getattr(function, "clear", None)
        if callable(clear):
            clear()
