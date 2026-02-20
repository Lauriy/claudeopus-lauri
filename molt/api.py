"""API layer — HTTP requests, verification handling."""

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

from molt import API_LOG, ENV_PATH, ROOT
from molt.solver import decode_obfuscated, solve_challenge
from molt.timing import now_iso

API = "https://www.moltbook.com/api/v1"


def _load_key() -> str:
    key = os.environ.get("MOLTBOOK_API_KEY")
    if key:
        return key
    if ENV_PATH.exists():
        for raw_line in ENV_PATH.read_text().splitlines():
            stripped = raw_line.strip()
            if stripped.startswith("MOLTBOOK_API_KEY="):
                return stripped.split("=", 1)[1].strip()
    print("ERROR: MOLTBOOK_API_KEY not found. Set it in .env or as an env var.")
    sys.exit(1)


KEY: str = _load_key()


def _log_api(method: str, path: str, status: int, body_json: dict[str, Any]) -> None:
    if method != "POST":
        return
    try:
        entry = {"ts": now_iso(), "method": method, "path": path, "status": status, "response": body_json}
        with open(API_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def req(method: str, path: str, body: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
    url = f"{API}{path}"
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Authorization", f"Bearer {KEY}")
    if data:
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            d = json.loads(resp.read())
            _log_api(method, path, resp.status, d)
            return d
    except urllib.error.HTTPError as e:
        try:
            d = json.loads(e.read())
            _log_api(method, path, e.code, d)
            if d.get("hint"):
                d["error"] = f"{d.get('error', '')} — {d['hint']}"
            return d
        except Exception:
            _log_api(method, path, e.code, {"raw_error": str(e)})
            return {"success": False, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _find_verification(d: dict[str, Any]) -> dict[str, Any] | None:
    """Search response for a verification challenge in all known locations."""
    if d.get("verification_required"):
        return d.get("verification", {})
    for key in ("comment", "post"):
        obj = d.get(key)
        if isinstance(obj, dict):
            v = obj.get("verification")
            if isinstance(v, dict) and (v.get("verification_code") or v.get("code")):
                return v
    return None


def handle_verification(response_data: dict[str, Any]) -> dict[str, Any]:
    v = _find_verification(response_data)
    if not v:
        return response_data
    code = v.get("code") or v.get("verification_code", "")
    challenge = v.get("challenge") or v.get("challenge_text", "")
    instructions = v.get("instructions", "")
    print("\n  *** VERIFICATION CHALLENGE ***")
    print(f"  Code: {code}")
    print(f"  Challenge: {challenge}")
    print(f"  Instructions: {instructions}")
    print(f"  Decoded: {decode_obfuscated(challenge)}")

    challenge_file = ROOT / "pending_challenge.json"
    challenge_file.write_text(json.dumps(v, indent=2))
    print(f"  Saved to: {challenge_file}")

    # DO NOT auto-submit — wrong answers burn the challenge permanently
    answer = solve_challenge(challenge, instructions)
    if answer is not None:
        print(f"\n  >>> PROPOSED answer: {answer:.2f}")
    print(f"  >>> Submit: python molt.py verify {code} <ANSWER>")
    return response_data


def _check_get(d: dict[str, Any]) -> bool:
    if d.get("statusCode"):
        print(f"Error: {d.get('error', d.get('message', '?'))}")
        return False
    if d.get("error"):
        print(f"Error: {d['error']}")
        if d.get("hint"):
            print(f"Hint: {d['hint']}")
        return False
    return True


def _check_post(d: dict[str, Any]) -> dict[str, Any] | None:
    """Handle verification challenge + success check for POST responses."""
    if _find_verification(d):
        d = handle_verification(d)
    if d.get("statusCode"):
        print(f"Error: {d.get('error', d.get('message', '?'))}")
        return None
    if not d.get("success"):
        print(f"Error: {d.get('error')}")
        if d.get("hint"):
            print(f"Hint: {d['hint']}")
        return None
    return d
