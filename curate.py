"""Curate raw guidde steps into a flow spec.

Default engine: OpenAI (uses your OPENAI_API_KEY). A deterministic fallback
(--no-llm / use_llm=False) maps the raw text straight through without rewriting.

The system prompt encodes the content rules so the "smart" step runs on your own
key, not in a Claude chat.
"""
from __future__ import annotations

import json
import os
import re

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Shared selector keys the model may reference (kept in sync with schema/selectors.yaml)
KNOWN_REFS = {
    "forms-menu": "Left navigation 'Forms' menu item",
    "customize-forms-icon": "'Customize Forms' icon, top-right of the Forms page",
    "custom-form-plus": "'+' to create a custom form (pencil to edit an existing one)",
    "pencil-icon": "Pencil (edit) icon on a form row",
    "save-button": "Save button",
}

DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

_REFS_TEXT = "\n".join(f'  - "{k}": {v}' for k, v in KNOWN_REFS.items())

SYSTEM_PROMPT = f"""You convert raw steps extracted from a guidde product tutorial for FieldPie
(a field-management app) into a Usertour onboarding flow specification.

Return ONLY a JSON object of this exact shape:
{{
  "title": string,                 // short Title Case flow name (NO "Merch-M" prefix), from the tutorial topic
  "ending": {{ "title": string, "body": string }},   // a short congratulatory finish screen
  "steps": [
    {{
      "key": string,               // short kebab-case id, unique in the flow
      "name": string,              // short Title Case step label
      "body": string,              // ONE short native American English sentence; wrap the key UI element the user acts on in **bold**
      "target_ref": string|null,   // one of the known selector keys below if this step targets that element, else null
      "target_note": string,       // short TURKISH note describing the target element (for manual binding); "" if none
      "type": "tooltip"|"modal"    // "tooltip" by default; "modal" only for a summary step
    }}
  ]
}}

Rules:
- Native American English for name/body/ending; basic level, concise, one sentence per body. No over-explaining.
- Be faithful and COMPLETE: every source frame that contains a user instruction becomes its own step; keep the original order. NEVER drop a frame that has an instruction — including optional ones (e.g. 'optional additional filters'). Only combine frames that set fields on the SAME row/screen, or collapse a group that repeats 3+ times into one summary step.
- SKIP the intro/overview frame (usually numbered 00): start at the first real action. Never produce a welcome modal.
- SKIP any frame whose description is empty or carries no user instruction.
- ALWAYS rename a step when its source title does not describe the action in the description. Guidde often uses filler titles like 'Proceed with Action', 'Enter Activation Value', 'Proceed To Next Step', 'Continue Workflow Setup' — replace these with a short name for what the user actually does.
- If several fields are set on the same row/screen, combine them into one step.
- If a group of steps repeats 3+ times, keep ONE representative example step, then collapse the rest into a SINGLE summary step with "type":"modal" (no target) that lists what to repeat.
- Use target_ref for elements that recur across flows. Known keys:
{_REFS_TEXT}
  Set target_ref ONLY when the step's target is EXACTLY that element. The left-menu 'Forms' item is forms-menu; any OTHER left-menu item (e.g. 'Bulk Operations', 'Tasks', 'Visits') must be target_ref=null with a Turkish target_note. Never map a different element onto a known ref.
- Never invent CSS selectors; a human binds them later.
- ending.title and ending.body: short, specific to this tutorial.
"""


def curate_llm(raw_steps: list[dict], source_name: str, model: str = DEFAULT_MODEL) -> dict:
    from openai import OpenAI

    client = OpenAI()  # reads OPENAI_API_KEY
    user = {"source": source_name, "raw_steps": raw_steps}
    resp = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ],
    )
    return json.loads(resp.choices[0].message.content)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "step").lower()).strip("-") or "step"


def curate_deterministic(raw_steps: list[dict], source_name: str) -> dict:
    steps = []
    for s in raw_steps:
        n = str(s.get("n", ""))
        if n in ("0", "00"):
            continue
        text = (s.get("text") or "").strip()
        if not text:
            continue
        steps.append({
            "key": _slug(s.get("title", "")),
            "name": (s.get("title") or "Step").strip(),
            "body": text,
            "target_ref": None,
            "target_note": "",
            "type": "tooltip",
        })
    title = re.sub(r"\.[Pp][Dd][Ff]$", "", source_name).replace("_", " ").strip() or "Flow"
    return {
        "title": title,
        "ending": {"title": "You're all set.", "body": "Nice work — you finished this tutorial."},
        "steps": steps,
    }


def curate(raw_steps: list[dict], source_name: str, use_llm: bool = True,
           model: str = DEFAULT_MODEL) -> dict:
    if use_llm:
        return curate_llm(raw_steps, source_name, model)
    return curate_deterministic(raw_steps, source_name)


def to_flow_doc(curated: dict, flow_name: str) -> dict:
    """Turn the curated JSON into the flow.yaml document our builder reads."""
    ending = curated.get("ending") or {}
    doc = {
        "flow": {
            "name": flow_name,
            "ending": {
                "name": "Finish Screen",
                "title": ending.get("title", "You're all set."),
                "body": ending.get("body", ""),
                "home_url": "https://app.fieldpie.com",
                "home_label": "Go back to home",
                "button": "Finish",
                "support": True,
            },
        },
        "steps": [],
    }
    for s in curated.get("steps", []):
        step: dict = {"key": s.get("key"), "name": s.get("name"), "body": s.get("body", "")}
        if s.get("type") == "modal":
            step["type"] = "modal"
        else:
            ref = s.get("target_ref")
            note = s.get("target_note") or ""
            if ref in KNOWN_REFS:
                step["target"] = {"ref": ref, "note": note}
            else:
                step["target"] = {"selector": "", "note": note}
        doc["steps"].append(step)
    return doc
