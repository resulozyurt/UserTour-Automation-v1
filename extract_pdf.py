"""Extract raw steps from a guidde PDF tutorial into <pdf>.raw.yaml.

Deterministic first pass: it captures each step's number, title and description
as written in the PDF. A person (or Claude) then curates this into a final
flow.yaml (native English wording, fixing action-mismatched titles, skipping
intros, grouping, and adding the ending) before building.

    python extract_pdf.py "path/to/Some Tutorial.pdf"
"""
from __future__ import annotations

import os
import re
import sys

import yaml
import pdfplumber

HEADER = re.compile(r"^(\d{1,2})\s+(\S.*)$")
GOTO = re.compile(r"^Go to\s+((?:https?://)?[\w.-]+\.[\w.-]+)\s*$", re.IGNORECASE)


def extract(pdf_path: str) -> list[dict]:
    steps: list[dict] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
            num: str | None = None
            title: str | None = None
            url: str | None = None
            desc: list[str] = []
            for ln in lines:
                header = HEADER.match(ln)
                goto = GOTO.match(ln)
                if header and num is None:
                    num, title = header.group(1), header.group(2).strip()
                elif goto:
                    url = goto.group(1)
                elif num is not None:
                    desc.append(ln)
            if num is not None:
                step = {"n": num, "title": title, "text": " ".join(desc).strip()}
                if url:
                    step["goto_url"] = url
                steps.append(step)
    steps.sort(key=lambda s: int(s["n"]))
    return steps


def main() -> int:
    if len(sys.argv) < 2:
        print('Usage: python extract_pdf.py "path/to/tutorial.pdf"')
        return 1
    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(f"Not found: {pdf_path}")
        return 1

    steps = extract(pdf_path)
    out_path = os.path.splitext(pdf_path)[0] + ".raw.yaml"
    doc = {"source": os.path.basename(pdf_path), "steps": steps}
    with open(out_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(doc, fh, allow_unicode=True, sort_keys=False, width=1000)

    print(f"Extracted {len(steps)} steps -> {out_path}")
    for s in steps:
        print(f"  [{s['n']}] {s['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
