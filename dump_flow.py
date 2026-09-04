"""Dump an existing flow's version JSON (with steps) to build/dump-<slug>.json.

Use it to copy the exact structure of a known-good flow (buttons, colors,
navigation actions, placement). Zero dependencies.

    python dump_flow.py Merch-M014
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("USERTOUR_BASE_URL", "https://api.usertour.io").rstrip("/")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


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
    if len(sys.argv) > 2:
        return sys.argv[2].strip()
    sys.exit("No token. Set USERTOUR_API_TOKEN or add it to .env.")


TOKEN = load_token()


def call(path: str):
    req = urllib.request.Request(BASE + path, method="GET")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else "Merch-M014"
    status, me = call("/v2/me")
    if status != 200:
        print(f"[FAIL] /v2/me -> {status}: {me}")
        return 1
    project_id = me["projects"][0]["id"]

    q = urllib.parse.quote(name)
    status, data = call(f"/v2/projects/{project_id}/content?type=flow&name={q}&limit=100")
    if status != 200:
        print(f"[FAIL] list content -> {status}: {data}")
        return 1
    results = data.get("results", [])
    if not results:
        print(f"No flow matched '{name}'.")
        return 1
    item = results[0]
    content_id = item["id"]
    version_id = item.get("editedVersionId") or (item.get("editedVersion") or {}).get("id")
    print(f"Match: {item.get('name')}  content={content_id}  version={version_id}")

    status, version = call(
        f"/v2/projects/{project_id}/content/{content_id}/versions/{version_id}?expand=steps"
    )
    if status != 200:
        print(f"[FAIL] get version -> {status}: {version}")
        return 1

    os.makedirs("build", exist_ok=True)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-")
    out = os.path.join("build", f"dump-{slug}.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(version, fh, indent=2, ensure_ascii=False)
    steps = version.get("steps") or []
    print(f"Wrote {out}  ({len(steps)} steps).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
