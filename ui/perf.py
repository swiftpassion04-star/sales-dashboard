import os
from contextlib import contextmanager
from time import perf_counter


_ENABLED_VALUES = {"1", "true", "yes", "on"}
_SAFE_META_KEYS = {"action", "count", "page", "page_size", "role", "sale_type"}


def perf_enabled() -> bool:
    return os.getenv("CRM_PERF_DEBUG", "").strip().lower() in _ENABLED_VALUES


def _safe_meta(meta: dict) -> dict:
    safe = {}
    for key, value in meta.items():
        if key not in _SAFE_META_KEYS or value is None:
            continue
        if isinstance(value, (bool, int, float)):
            safe[key] = value
        else:
            safe[key] = str(value)[:64]
    return safe


@contextmanager
def perf_trace(label: str, **meta):
    if not perf_enabled():
        yield
        return

    start = perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (perf_counter() - start) * 1000
        safe_meta = _safe_meta(meta)
        suffix = f" {safe_meta}" if safe_meta else ""
        print(f"[PERF] {label} {elapsed_ms:.1f}ms{suffix}", flush=True)
