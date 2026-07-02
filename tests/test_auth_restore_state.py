import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auth_utils import classify_browser_session_payload


def bridge_value(session_payload):
    return json.dumps(
        {
            "bridge_ready": True,
            "session_payload": (
                None if session_payload is None else json.dumps(session_payload)
            ),
        }
    )


assert classify_browser_session_payload(None) == "pending"
assert classify_browser_session_payload(None) != "empty"
assert classify_browser_session_payload({}) == "empty"
assert classify_browser_session_payload(
    {"access_token": "access", "refresh_token": "refresh"}
) == "has_session"
assert classify_browser_session_payload("not-json") == "invalid"
assert classify_browser_session_payload({"access_token": "access"}) == "invalid"

assert classify_browser_session_payload(bridge_value(None)) == "empty"
assert classify_browser_session_payload(
    bridge_value({"access_token": "access", "refresh_token": "refresh"})
) == "has_session"

print("auth restore state characterization OK")
