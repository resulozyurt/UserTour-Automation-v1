"""Build one flow from an intermediate file and optionally upload it.

    python build_flow.py schema/flow.example.yaml --dry-run
    python build_flow.py schema/flow.example.yaml
    python build_flow.py schema/flow.example.yaml --publish env_xxx

A dry run only assembles the JSON into build/ so you can review it before
anything is sent to Usertour.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.client import UsertourClient, UsertourError
from src.config import Config
from src.flow_builder import build_flow

DEFAULT_SELECTORS = "schema/selectors.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build (and optionally upload) a Usertour flow."
    )
    parser.add_argument("flow", help="Path to the intermediate flow YAML")
    parser.add_argument(
        "--selectors", default=DEFAULT_SELECTORS, help="Selector dictionary YAML"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Assemble JSON only; do not call the API",
    )
    parser.add_argument(
        "--publish",
        metavar="ENV_ID",
        help="Publish to this environment after a clean validation",
    )
    args = parser.parse_args()

    cfg: Config | None = None
    default_theme_id: str | None = None
    try:
        cfg = Config.from_env()
        default_theme_id = cfg.default_theme_id
    except SystemExit as exc:
        if not args.dry_run:
            print(exc)
            return 1

    result = build_flow(args.flow, args.selectors, default_theme_id=default_theme_id)

    build_dir = Path("build")
    build_dir.mkdir(exist_ok=True)
    out_path = build_dir / (Path(args.flow).stem + ".steps.json")
    out_path.write_text(
        json.dumps(result.steps, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"Flow: {result.flow_name}")
    print(f"Steps: {len(result.steps)}  ->  {out_path}")
    if result.unresolved:
        print(
            f"Selectors to bind manually ({len(result.unresolved)}): "
            f"{', '.join(result.unresolved)}"
        )
    else:
        print("All step selectors resolved.")

    if args.dry_run:
        print("Dry run: nothing sent to the API.")
        return 0

    if not result.theme_id:
        print(
            "No theme_id. Set flow.theme_id or USERTOUR_DEFAULT_THEME_ID "
            "(run validate_api.py to list theme ids)."
        )
        return 1

    assert cfg is not None
    client = UsertourClient(cfg)
    try:
        project_id = client.resolve_project_id()
        content = client.create_flow(project_id, result.flow_name, result.theme_id)
        content_id = content["id"]
        version_id = content.get("editedVersionId") or (
            content.get("editedVersion") or {}
        ).get("id")
        if not version_id:
            print("Could not find the draft version id on the created flow.")
            return 1

        client.update_version(project_id, content_id, version_id, {"steps": result.steps})
        print(f"Created flow {content_id} (draft version {version_id}).")

        report = client.validate_version(project_id, content_id, version_id)
        real_errors = [
            e
            for e in (report.get("errors") or [])
            if "no target element" not in (e.get("message") or "").lower()
        ]
        if report.get("ok"):
            print("Validation: OK (publishable).")
        elif not real_errors:
            print(
                "Validation: draft OK. The steps listed above still need a "
                "selector before publishing (bind them in the panel)."
            )
        else:
            print("Validation errors (fix these):")
            for err in real_errors:
                print(f"  - {err.get('path')}: {err.get('message')}")

        if args.publish:
            if report.get("ok"):
                client.publish(project_id, content_id, version_id, args.publish)
                print(f"Published to environment {args.publish}.")
            else:
                print("Not published: fix the validation errors first.")
    except (UsertourError, KeyError) as exc:
        print("Upload failed:")
        print(exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
