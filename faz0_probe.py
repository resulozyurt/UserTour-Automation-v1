"""Phase 0 probe - run this once on a machine with internet access to Usertour.

Zero dependencies (Python standard library only), so no `pip install` is needed.
It discovers your project / theme / environment ids and answers the open
question from the roadmap: can a tooltip step be saved in a DRAFT without a
target selector? It creates one disposable flow named "__api_probe__ ..." and
deletes it again at the end.

Usage (from the project folder):
    python faz0_probe.py
It reads the token from USERTOUR_API_TOKEN, or from a local .env file, or as the
first command-line argument.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("USERTOUR_BASE_URL", "https://api.usertour.io").rstrip("/")


def load_token() -> str:
    tok = os.environ.get("USERTOUR_API_TOKEN", "").strip()
    if tok:
        return tok
    try:
        with open(".env", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("USERTOUR_API_TOKEN="):
                    return line.split("=", 1)[1].strip()
    except FileNotFoundError:
        pass
    if len(sys.argv) > 1:
        return sys.argv[1].strip()
    sys.exit("No token. Set USERTOUR_API_TOKEN, add it to .env, or pass it as an argument.")


TOKEN = load_token()


def call(method: str, path: str, body: dict | None = None):
    """Return (status_code, parsed_body). status_code is None on transport error."""
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = raw
        return exc.code, parsed
    except Exception as exc:  # transport / TLS / network
        return None, f"{type(exc).__name__}: {exc}"


def short(obj, limit: int = 400) -> str:
    text = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + " ..."


def main() -> int:
    print(f"Base URL: {BASE}\n")

    # 1) Identity / discovery -------------------------------------------------
    status, me = call("GET", "/v2/me")
    if status != 200:
        print(f"[FAIL] GET /v2/me -> {status}: {short(me)}")
        print("Check the token and network access to Usertour, then retry.")
        return 1
    print(f"[OK] Token: {me.get('tokenName', '?')}")
    projects = me.get("projects", []) or []
    for p in projects:
        print(f"  project: {p.get('name')}  id={p.get('id')}")
        for env in p.get("environments", []) or []:
            print(f"    env: {env.get('name')}  id={env.get('id')}")
    if len(projects) != 1:
        print(f"\n[STOP] Token can access {len(projects)} projects; pin one before the write test.")
        return 0
    project_id = projects[0]["id"]

    # 2) Themes ---------------------------------------------------------------
    status, themes = call("GET", f"/v2/projects/{project_id}/themes?limit=100")
    theme_list = (themes or {}).get("results", []) if status == 200 else []
    print(f"\n[{'OK' if status == 200 else 'FAIL'}] Themes ({len(theme_list)}):")
    default_theme_id = None
    for t in theme_list:
        flag = " (default)" if t.get("isDefault") else ""
        print(f"  theme: {t.get('name')}  id={t.get('id')}{flag}")
        if t.get("isDefault") and not default_theme_id:
            default_theme_id = t.get("id")
    if not default_theme_id and theme_list:
        default_theme_id = theme_list[0].get("id")

    # 3) Existing flows -------------------------------------------------------
    status, content = call("GET", f"/v2/projects/{project_id}/content?type=flow&limit=100")
    flows = (content or {}).get("results", []) if status == 200 else []
    print(f"\n[{'OK' if status == 200 else 'FAIL'}] Existing flows: {len(flows)}")

    if not default_theme_id:
        print("\n[STOP] No theme available; cannot run the write test.")
        return 0

    # 4) Write test: draft with a tooltip step that has NO target -------------
    print("\n=== WRITE TEST (open question) ===")
    probe_name = f"__api_probe__ safe to delete {int(time.time())}"
    status, created = call(
        "POST",
        f"/v2/projects/{project_id}/content",
        {"type": "flow", "name": probe_name, "themeId": default_theme_id},
    )
    if status not in (200, 201):
        print(f"[FAIL] create flow -> {status}: {short(created)}")
        return 1
    content_id = created.get("id")
    version_id = created.get("editedVersionId") or (created.get("editedVersion") or {}).get("id")
    print(f"[OK] created flow id={content_id}  draft version={version_id}")

    step_no_target = {
        "key": "probe-1",
        "name": "Probe step (no target)",
        "type": "tooltip",
        "content": [{"type": "text", "markdown": "## Probe\n\nDraft without a target."}],
    }
    step_with_target = dict(step_no_target)
    step_with_target["target"] = {"selector": "[data-probe='x']"}

    try:
        # 4a) save draft WITHOUT target
        s1, r1 = call(
            "PATCH",
            f"/v2/projects/{project_id}/content/{content_id}/versions/{version_id}",
            {"steps": [step_no_target]},
        )
        print(f"\nA) PATCH steps WITHOUT target -> {s1}")
        print(f"   {short(r1)}")
        sv, rv = call(
            "GET",
            f"/v2/projects/{project_id}/content/{content_id}/versions/{version_id}/validate",
        )
        ok = rv.get("ok") if isinstance(rv, dict) else None
        print(f"   validate -> {sv}  ok={ok}")
        if isinstance(rv, dict) and rv.get("errors"):
            for e in rv["errors"]:
                print(f"     error: {e.get('path')}: {e.get('message')}")

        # 4b) save draft WITH target
        s2, r2 = call(
            "PATCH",
            f"/v2/projects/{project_id}/content/{content_id}/versions/{version_id}",
            {"steps": [step_with_target]},
        )
        print(f"\nB) PATCH steps WITH target -> {s2}")
        print(f"   {short(r2)}")
        sv2, rv2 = call(
            "GET",
            f"/v2/projects/{project_id}/content/{content_id}/versions/{version_id}/validate",
        )
        ok2 = rv2.get("ok") if isinstance(rv2, dict) else None
        print(f"   validate -> {sv2}  ok={ok2}")
        if isinstance(rv2, dict) and rv2.get("errors"):
            for e in rv2["errors"]:
                print(f"     error: {e.get('path')}: {e.get('message')}")

        # summary
        print("\n=== ANSWER ===")
        draft_no_target_ok = s1 in (200, 201)
        print(f"Draft saved WITHOUT target?  {'YES' if draft_no_target_ok else 'NO'} (HTTP {s1})")
        print(f"Publishable WITHOUT target?  {'YES' if ok else 'NO'}")
        print(f"Publishable WITH target?     {'YES' if ok2 else 'NO'}")
        print("Interpretation:")
        if draft_no_target_ok and not ok:
            print("  -> Keep target off in the draft; fill selectors manually before publish.")
        elif draft_no_target_ok and ok:
            print("  -> Target is optional even for publish (unexpected; double-check in the panel).")
        else:
            print("  -> Draft rejects an empty target; use a placeholder selector strategy instead.")
    finally:
        # 5) cleanup
        sd, rd = call("DELETE", f"/v2/projects/{project_id}/content/{content_id}")
        if sd in (200, 204):
            print(f"\n[cleanup] deleted probe flow {content_id}")
        else:
            print(f"\n[cleanup] could NOT delete probe flow {content_id} -> {sd}: {short(rd)}")
            print(f"          delete it manually in the panel (name: {probe_name}).")

    print("\nCopy this whole output back into the chat.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
