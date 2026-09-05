"""One command: guidde PDF -> extract -> curate -> build a Usertour draft.

    python newflow.py "path/to/tutorial.pdf"
    python newflow.py "file.pdf" --no-llm        # deterministic curation (no API cost)
    python newflow.py "file.pdf" --no-build      # write the flow.yaml only
    python newflow.py "file.pdf" --model gpt-4o  # override the OpenAI model
    python newflow.py "file.pdf" --number 20     # set the Merch-M number manually

Numbering is automatic (next Merch-M### from your Usertour project) when the
Usertour token/network are available; otherwise pass --number.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from extract_pdf import extract
from curate import curate, to_flow_doc, DEFAULT_MODEL


def title_from_filename(name: str) -> str:
    """Flow title comes from the PDF filename (your backlog topic name)."""
    t = Path(name).stem.replace("_", " ").strip()
    t = re.sub(r"\s*\(\d+\)\s*$", "", t)   # strip a trailing '(1)'
    return re.sub(r"\s+", " ", t).strip()


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "flow").lower()).strip("-") or "flow"


def _local_max() -> int:
    biggest = 0
    for d in Path("flows").glob("M*"):
        m = re.match(r"M(\d+)", d.name)
        if m:
            biggest = max(biggest, int(m.group(1)))
    return biggest


def auto_number() -> int:
    """Next Merch-M###, taking the max of local flows/ folders and Usertour."""
    biggest = _local_max()
    try:
        from src.config import Config
        from src.client import UsertourClient

        client = UsertourClient(Config.from_env())
        pid = client.resolve_project_id()
        for flow in client.list_content(pid, type="flow"):
            m = re.match(r"Merch-M(\d+)", flow.get("name") or "")
            if m:
                biggest = max(biggest, int(m.group(1)))
    except Exception as exc:
        print(f"(Usertour auto-numbering unavailable, using local folders: {exc})")
    return biggest + 1


def main() -> int:
    ap = argparse.ArgumentParser(description="PDF -> curated flow -> Usertour draft.")
    ap.add_argument("pdf", help="Path to the guidde PDF")
    ap.add_argument("--no-llm", action="store_true", help="Deterministic curation (no API cost)")
    ap.add_argument("--no-build", action="store_true", help="Write flow.yaml only; do not upload")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="OpenAI model for curation")
    ap.add_argument("--number", type=int, help="Merch-M number (skip auto-numbering)")
    args = ap.parse_args()

    if not os.path.exists(args.pdf):
        print(f"Not found: {args.pdf}")
        return 1

    raw = extract(args.pdf)
    if not raw:
        print("No steps found in the PDF.")
        return 1
    print(f"Extracted {len(raw)} raw steps.")

    number = args.number if args.number is not None else auto_number()
    if number is None:
        print("Could not determine the flow number. Re-run with --number N.")
        return 1

    curated = curate(raw, os.path.basename(args.pdf), use_llm=not args.no_llm, model=args.model)
    title = title_from_filename(args.pdf) or (curated.get("title") or "Flow").strip()
    flow_name = f"Merch-M{number:03d}-{title}"
    slug = f"M{number:03d}-{slugify(title)}"

    folder = Path("flows") / slug
    folder.mkdir(parents=True, exist_ok=True)
    doc = to_flow_doc(curated, flow_name)
    flow_path = folder / "flow.yaml"
    with open(flow_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(doc, fh, sort_keys=False, allow_unicode=True, width=1000)

    dst = folder / "source.pdf"
    if os.path.abspath(args.pdf) != os.path.abspath(dst):
        shutil.copy(args.pdf, dst)

    print(f"\n{flow_name}")
    print(f"{len(doc['steps'])} steps -> {flow_path}")
    print("Review the flow.yaml, then it will be uploaded as a draft.")

    if args.no_build:
        print("--no-build: not uploaded.")
        return 0

    return subprocess.run([sys.executable, "build_flow.py", str(flow_path)]).returncode


if __name__ == "__main__":
    sys.exit(main())
