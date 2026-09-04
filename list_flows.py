"""List flows with their published status - helps pick the next flow number.

Zero dependencies. Reads the token from USERTOUR_API_TOKEN, a local .env, or the
first argument. Run: python list_flows.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
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
    if len(sys.argv) > 1:
        return sys.argv[1].strip()
    sys.exit("No token. Set USERTOUR_API_TOKEN, add it to .env, or pass it as an argument.")


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
    status, me = call("/v2/me")
    if status != 200:
        print(f"[FAIL] /v2/me -> {status}: {me}")
        return 1
    projects = me.get("projects", []) or []
    if len(projects) != 1:
        print(f"Token spans {len(projects)} projects; not handled here.")
        return 1
    project_id = projects[0]["id"]

    path = f"/v2/projects/{project_id}/content?type=flow&limit=100"
    flows = []
    while path:
        status, data = call(path)
        if status != 200:
            print(f"[FAIL] list content -> {status}: {data}")
            return 1
        flows.extend(data.get("results", []))
        nxt = data.get("next")
        path = nxt[len(BASE):] if nxt and nxt.startswith(BASE) else nxt
        if path and path.startswith("http"):
            path = "/" + path.split("/", 3)[3]

    flows.sort(key=lambda f: f.get("createdAt") or "")
    print(f"{len(flows)} flows (published = live in an environment):\n")
    for f in flows:
        envs = f.get("environments") or []
        published = "PUBLISHED" if envs else "draft    "
        print(f"  [{published}] {f.get('name')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
