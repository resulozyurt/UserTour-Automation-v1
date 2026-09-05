"""Create/refresh an 'auto-bold' copy of the default theme that renders bold
text in the brand color via custom CSS. Safe: never edits your existing theme,
it works on a duplicate. Prints the new theme id to put in .env.

    python set_bold_color.py
Requires the Usertour Growth plan (custom CSS is plan-gated); if your plan does
not allow it, the update is refused and this prints the error.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("USERTOUR_BASE_URL", "https://api.usertour.io").rstrip("/")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
BRAND = "#018478"
RULE = f"strong, b {{ color: {BRAND} !important; }}"


def load_token() -> str:
    tok = os.environ.get("USERTOUR_API_TOKEN", "").strip()
    if tok:
        return tok
    try:
        with open(".env", encoding="utf-8") as fh:
            for line in fh:
                if line.strip().startswith("USERTOUR_API_TOKEN="):
                    return line.split("=", 1)[1].strip()
    except FileNotFoundError:
        pass
    sys.exit("No token. Set USERTOUR_API_TOKEN or add it to .env.")


def load_env(key: str) -> str | None:
    val = os.environ.get(key, "").strip()
    if val:
        return val
    try:
        with open(".env", encoding="utf-8") as fh:
            for line in fh:
                if line.strip().startswith(f"{key}="):
                    return line.split("=", 1)[1].strip() or None
    except FileNotFoundError:
        pass
    return None


TOKEN = load_token()


def call(method: str, path: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("User-Agent", UA)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw


def main() -> int:
    status, me = call("GET", "/v2/me")
    if status != 200:
        print(f"[FAIL] /v2/me -> {status}: {me}")
        return 1
    pid = me["projects"][0]["id"]

    base_id = load_env("USERTOUR_DEFAULT_THEME_ID")
    if not base_id:
        print("Set USERTOUR_DEFAULT_THEME_ID in .env first.")
        return 1

    status, base = call("GET", f"/v2/projects/{pid}/themes/{base_id}?expand=settings")
    if status != 200:
        print(f"[FAIL] get base theme -> {status}: {base}")
        return 1
    target_name = f"{base.get('name', 'Theme')} (auto-bold)"

    # reuse an existing auto-bold theme if present, else duplicate the base
    status, listing = call("GET", f"/v2/projects/{pid}/themes?limit=100")
    existing = None
    for t in (listing or {}).get("results", []):
        if t.get("name") == target_name:
            existing = t
            break

    if existing:
        theme_id = existing["id"]
        print(f"Reusing theme '{target_name}' id={theme_id}")
    else:
        status, dup = call("POST", f"/v2/projects/{pid}/themes/{base_id}/duplicate")
        if status not in (200, 201):
            print(f"[FAIL] duplicate theme -> {status}: {dup}")
            return 1
        theme_id = dup["id"]
        print(f"Duplicated base theme -> new id={theme_id}")

    # read the (full) settings and add our CSS rule
    status, theme = call("GET", f"/v2/projects/{pid}/themes/{theme_id}?expand=settings")
    if status != 200:
        print(f"[FAIL] get theme -> {status}: {theme}")
        return 1
    settings = theme.get("settings") or {}
    css = settings.get("customCss") or ""
    if RULE not in css:
        css = (css + "\n" + RULE).strip()
    settings["customCss"] = css

    # send the FULL settings back so nothing is lost if PATCH replaces the object
    status, res = call(
        "PATCH",
        f"/v2/projects/{pid}/themes/{theme_id}",
        {"name": target_name, "settings": settings},
    )
    if status != 200:
        print(f"[FAIL] update theme -> {status}: {res}")
        print("If this is a plan error, custom CSS needs the Growth plan or above.")
        return 1

    # verify
    status, check = call("GET", f"/v2/projects/{pid}/themes/{theme_id}?expand=settings")
    s = (check or {}).get("settings") or {}
    ok_css = RULE in (s.get("customCss") or "")
    print(f"\nTheme '{target_name}'  id={theme_id}")
    print(f"custom CSS set: {'YES' if ok_css else 'NO'}   settings keys preserved: {len(s)}")
    print("\nNext: set this in .env  ->  USERTOUR_DEFAULT_THEME_ID=" + theme_id)
    print("Then rebuild the flow; bold text will render in the brand color.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
