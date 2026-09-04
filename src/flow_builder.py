"""Turn the intermediate flow format into a Usertour step payload.

The structure mirrors an existing, known-good FieldPie flow (Merch-M014):
- tooltips use Auto alignment (placement.alignType = "auto") with a backdrop,
- the tooltip body is a single text block wrapped in a columns block (no heading),
- each step gets a "Next -> " button and a matching onClick action that advance
  to the next step (goto_step by key),
- an optional closing "modal" step (ending) with a congrats message, a button,
  and a support block.

Colors come from the theme: bold markdown renders in the brand color, so no
color fields are set here (the API strips them anyway).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

NEXT_LABEL = "Next →"  # "Next ->"


@dataclass
class BuildResult:
    flow_name: str
    theme_id: str | None
    steps: list[dict]
    unresolved: list[str]  # step keys whose target selector is still empty


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #
def load_yaml(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_selectors(path: str | Path) -> dict[str, dict]:
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


# --------------------------------------------------------------------------- #
# block helpers (match Merch-M014 shapes)
# --------------------------------------------------------------------------- #
def _text_block(markdown: str) -> dict:
    return {"object": "block", "type": "text", "markdown": markdown}


def _text_columns(markdown: str, *, top: int = 0, bottom: int = 0,
                  align: str | None = None) -> dict:
    col: dict[str, Any] = {"width": {"unit": "fill"}, "blocks": [_text_block(markdown)]}
    pad: dict[str, Any] = {"enabled": True}
    if top:
        pad["top"] = top
    if bottom:
        pad["bottom"] = bottom
    if len(pad) > 1:
        col["padding"] = pad
    if align:
        col["align"] = align
    return {"object": "block", "type": "columns", "columns": [col]}


def _button_block(text: str, actions: list[dict], variant: str = "primary") -> dict:
    return {
        "object": "block",
        "type": "button",
        "text": text,
        "variant": variant,
        "actions": actions,
    }


def _button_columns(text: str, actions: list[dict], *, variant: str = "primary",
                    justify: str = "end", top: int = 12) -> dict:
    col = {
        "width": {"unit": "fill"},
        "justify": justify,
        "padding": {"enabled": True, "top": top},
        "blocks": [_button_block(text, actions, variant)],
    }
    return {"object": "block", "type": "columns", "columns": [col]}


def _support_block() -> dict:
    """Brand-generic 'need a hand?' footer, copied from the existing flows."""
    return {
        "object": "block",
        "type": "columns",
        "columns": [
            {
                "width": {"unit": "fill", "value": 8},
                "justify": "end",
                "align": "center",
                "padding": {"enabled": True, "top": 24, "bottom": 0},
                "blocks": [
                    {
                        "object": "block",
                        "type": "image",
                        "url": "https://assets.usertour.io/41831ce0-1449-4a3a-bc46-03978457fa88/support.png",
                        "width": {"unit": "pixels", "value": 40},
                    }
                ],
            },
            {
                "width": {"unit": "percent", "value": 72},
                "align": "center",
                "padding": {"enabled": True, "top": 24, "bottom": 0, "left": 16},
                "blocks": [
                    _text_block(
                        "**Need a hand getting started?** \n\nCall our team at [+1-877-494-1538]()"
                    )
                ],
            },
        ],
    }


def _tooltip_placement(side: str, align: str) -> dict:
    return {
        "side": side,
        "align": align,
        "sideOffset": 0,
        "alignOffset": 0,
        "alignType": "auto",
        "backdrop": True,
        "blockTarget": False,
    }


# --------------------------------------------------------------------------- #
# target resolution
# --------------------------------------------------------------------------- #
def _resolve_target(target: dict | None, selectors: dict[str, dict],
                    step_key: str, unresolved: list[str]) -> dict | None:
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
    out: dict[str, Any] = {"selector": selector, "nth": int(target.get("nth", 0))}
    if target.get("text"):
        out["text"] = target["text"]
    return out


# --------------------------------------------------------------------------- #
# finish modal
# --------------------------------------------------------------------------- #
def _build_finish(key: str, ending: dict) -> dict:
    content: list[dict] = []
    if ending.get("image"):
        content.append({
            "object": "block",
            "type": "image",
            "url": ending["image"],
            "width": {"unit": "percent", "value": ending.get("image_width", 74)},
        })
    title = (ending.get("title") or "You're all set.").strip()
    content.append(_text_columns(f"## {title}", top=24, bottom=12, align="center"))
    body = (ending.get("body") or "").strip()
    if body:
        content.append(_text_columns(body, bottom=16))

    button_cols: list[dict] = []
    if ending.get("home_url"):
        button_cols.append({
            "width": {"unit": "fill"},
            "justify": "start",
            "align": "center",
            "blocks": [
                _button_block(
                    ending.get("home_label", "Go back to home"),
                    [{"type": "navigate", "url": ending["home_url"]}, {"type": "dismiss"}],
                    variant="secondary",
                )
            ],
        })
    button_cols.append({
        "width": {"unit": "fill"},
        "justify": "end",
        "align": "center",
        "padding": {"enabled": True, "top": 16, "bottom": 16},
        "blocks": [
            _button_block(ending.get("button", "Finish"), [{"type": "dismiss"}], variant="primary")
        ],
    })
    content.append({"object": "block", "type": "columns", "columns": button_cols})

    if ending.get("support", True):
        content.append(_support_block())

    return {
        "key": key,
        "name": ending.get("name", "Finish"),
        "type": "modal",
        "placement": {"position": "center", "offsetX": 0, "offsetY": 0, "backdrop": True},
        "skippable": True,
        "explicitCompletionStep": True,
        "content": content,
    }


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def build_flow(flow_path: str | Path, selectors_path: str | Path | None = None,
               default_theme_id: str | None = None) -> BuildResult:
    doc = load_yaml(flow_path)
    flow = doc.get("flow", {})
    selectors: dict[str, dict] = {}
    if selectors_path and Path(selectors_path).exists():
        selectors = load_selectors(selectors_path)

    raw_steps = doc.get("steps", []) or []
    ending = flow.get("ending")
    keys = [s.get("key") or f"step-{i + 1}" for i, s in enumerate(raw_steps)]
    finish_key = "finish" if ending else None

    unresolved: list[str] = []
    steps_out: list[dict] = []
    total = len(raw_steps)

    for i, s in enumerate(raw_steps):
        key = keys[i]
        if i + 1 < total:
            next_key: str | None = keys[i + 1]
        else:
            next_key = finish_key  # last real step -> finish modal (or None)

        actions: list[dict] | None = None
        if next_key:
            actions = [{"type": "goto_step", "step": next_key}]
            if s.get("url"):
                actions.append({"type": "navigate", "url": s["url"]})

        body = (s.get("body") or "").strip()
        content: list[dict] = [_text_columns(body, bottom=12)]
        if actions:
            content.append(_button_columns(NEXT_LABEL, actions, top=12))

        step: dict[str, Any] = {
            "key": key,
            "name": s.get("name") or key,
            "type": s.get("type", "tooltip"),
            "placement": _tooltip_placement(s.get("side", "bottom"), s.get("align", "center")),
            "skippable": True,
            "explicitCompletionStep": False,
            "content": content,
        }
        target = _resolve_target(s.get("target"), selectors, key, unresolved)
        if target:
            step["target"] = target
        if actions:
            step["onClick"] = actions
        steps_out.append(step)

    if ending:
        steps_out.append(_build_finish(finish_key, ending))

    return BuildResult(
        flow_name=flow.get("name", "Untitled flow"),
        theme_id=flow.get("theme_id") or default_theme_id,
        steps=steps_out,
        unresolved=unresolved,
    )
