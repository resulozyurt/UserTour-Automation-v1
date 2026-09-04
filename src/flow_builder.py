"""Turn the intermediate flow format into a Usertour step payload.

The intermediate YAML is the human-reviewable source of truth. This module
resolves selectors (inline or via the shared dictionary) and assembles the
`steps[]` array the v2 API expects. Selectors that are still empty are
reported back so they can be bound manually in the panel.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class BuildResult:
    flow_name: str
    theme_id: str | None
    steps: list[dict]
    unresolved: list[str]  # step keys whose target selector is still empty


def load_yaml(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_selectors(path: str | Path) -> dict[str, dict]:
    """Accept either `key: "selector"` or `key: {selector, note}`."""
    data = load_yaml(path)
    out: dict[str, dict] = {}
    for key, val in data.items():
        if isinstance(val, str):
            out[key] = {"selector": val.strip(), "note": ""}
        elif isinstance(val, dict):
            out[key] = {
                "selector": (val.get("selector") or "").strip(),
                "note": val.get("note", ""),
            }
    return out


def _resolve_target(
    target: dict | None,
    selectors: dict[str, dict],
    step_key: str,
    unresolved: list[str],
) -> dict | None:
    if not target:
        unresolved.append(step_key)
        return None
    selector = (target.get("selector") or "").strip()
    ref = target.get("ref")
    if not selector and ref:
        selector = (selectors.get(ref, {}).get("selector") or "").strip()
    if not selector:
        unresolved.append(step_key)
        return None
    out: dict[str, Any] = {"selector": selector}
    if target.get("text"):
        out["text"] = target["text"]
    if target.get("nth") is not None:
        out["nth"] = int(target["nth"])
    return out


def _build_content(step: dict) -> list[dict]:
    title = (step.get("title") or "").strip()
    body = (step.get("body") or "").strip()
    if title and body:
        markdown = f"## {title}\n\n{body}"
    else:
        markdown = title or body
    content: list[dict] = []
    if markdown:
        content.append({"type": "text", "markdown": markdown})
    # Optional explicit buttons. Navigation semantics are confirmed in Phase 0;
    # by default we emit none and rely on the theme's built-in navigation.
    for btn in step.get("buttons", []) or []:
        block: dict[str, Any] = {
            "type": "button",
            "text": btn["text"],
            "variant": btn.get("variant", "primary"),
        }
        if btn.get("goto"):
            block["actions"] = [{"type": "goto_step", "step": btn["goto"]}]
        content.append(block)
    return content


def build_flow(
    flow_path: str | Path,
    selectors_path: str | Path | None = None,
    default_theme_id: str | None = None,
) -> BuildResult:
    doc = load_yaml(flow_path)
    flow = doc.get("flow", {})
    selectors: dict[str, dict] = {}
    if selectors_path and Path(selectors_path).exists():
        selectors = load_selectors(selectors_path)

    unresolved: list[str] = []
    steps_out: list[dict] = []
    for idx, step in enumerate(doc.get("steps", []) or []):
        key = step.get("key") or f"step-{idx + 1}"
        out: dict[str, Any] = {
            "key": key,
            "name": step.get("name") or key,
            "type": step.get("type", "tooltip"),
            "content": _build_content(step),
        }
        target = _resolve_target(step.get("target"), selectors, key, unresolved)
        if target:
            out["target"] = target
        if step.get("placement"):
            out["placement"] = step["placement"]
        if step.get("width") is not None:
            out["width"] = step["width"]
        steps_out.append(out)

    return BuildResult(
        flow_name=flow.get("name", "Untitled flow"),
        theme_id=flow.get("theme_id") or default_theme_id,
        steps=steps_out,
        unresolved=unresolved,
    )
