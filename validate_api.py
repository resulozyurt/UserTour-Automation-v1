"""Phase 0 smoke test: verify the token and discover project resources.

Run this first. It confirms the token works and prints the project id,
theme ids and environment ids you will need in .env and flow files.
"""
from __future__ import annotations

import sys

from src.client import UsertourClient, UsertourError
from src.config import Config


def main() -> int:
    try:
        cfg = Config.from_env()
    except SystemExit as exc:
        print(exc)
        return 1

    client = UsertourClient(cfg)
    try:
        me = client.me()
    except UsertourError as exc:
        print("Connection failed:")
        print(exc)
        return 1

    print(f"Token: {me.get('tokenName', '?')}")
    projects = me.get("projects", []) or []
    print(f"Projects ({len(projects)}):")
    for project in projects:
        print(f"  - {project.get('name')}  id={project.get('id')}")
        for env in project.get("environments", []) or []:
            print(f"      env: {env.get('name')}  id={env.get('id')}")

    try:
        project_id = client.resolve_project_id()
    except UsertourError as exc:
        print(exc)
        return 0

    print(f"\nUsing project: {project_id}")
    themes = client.list_themes(project_id)
    print(f"Themes ({len(themes)}):")
    for theme in themes:
        flag = " (default)" if theme.get("isDefault") else ""
        print(f"  - {theme.get('name')}  id={theme.get('id')}{flag}")

    flows = client.list_content(project_id, type="flow")
    print(f"Existing flows: {len(flows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
