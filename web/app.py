"""Local web UI for the Usertour flow pipeline.

Run it by double-clicking start.bat (or: python web/app.py). It opens a browser
page where you drop a guidde PDF, review/edit the generated flow, and upload it
to Usertour as a draft — no terminal needed after launch.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import yaml
from flask import Flask, jsonify, render_template, request

from extract_pdf import extract
from curate import curate, to_flow_doc, KNOWN_REFS, DEFAULT_MODEL
from newflow import auto_number, slugify

UPLOADS = ROOT / "web" / "_uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, template_folder=str(ROOT / "web" / "templates"), static_folder=str(ROOT / "web" / "static"))


@app.route("/")
def index():
    return render_template("index.html", refs=list(KNOWN_REFS.keys()))


@app.post("/api/upload")
def api_upload():
    f = request.files.get("pdf")
    if not f:
        return jsonify({"error": "No PDF uploaded."}), 400
    token = uuid.uuid4().hex
    pdf_path = UPLOADS / f"{token}.pdf"
    f.save(pdf_path)
    use_llm = request.form.get("use_llm", "1") != "0"
    model = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
    try:
        raw = extract(str(pdf_path))
        if not raw:
            return jsonify({"error": "No steps found in this PDF."}), 400
        curated = curate(raw, f.filename, use_llm=use_llm, model=model)
    except Exception as exc:
        return jsonify({"error": f"{type(exc).__name__}: {exc}"}), 400
    number = auto_number()
    title = (curated.get("title") or Path(f.filename).stem).strip()
    return jsonify({
        "token": token,
        "number": number,
        "flow_name": f"Merch-M{number:03d}-{title}",
        "title": title,
        "ending": curated.get("ending", {}),
        "steps": curated.get("steps", []),
        "raw_count": len(raw),
        "refs": list(KNOWN_REFS.keys()),
    })


@app.post("/api/build")
def api_build():
    data = request.get_json(force=True)
    flow_name = (data.get("flow_name") or "").strip()
    m = re.match(r"Merch-M(\d+)-(.*)", flow_name)
    if m:
        num, title = int(m.group(1)), m.group(2)
        slug = f"M{num:03d}-{slugify(title)}"
    else:
        title, slug = flow_name, slugify(flow_name)

    folder = ROOT / "flows" / slug
    folder.mkdir(parents=True, exist_ok=True)
    curated = {"title": title, "ending": data.get("ending", {}), "steps": data.get("steps", [])}
    doc = to_flow_doc(curated, flow_name)
    (folder / "flow.yaml").write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8"
    )
    token = data.get("token")
    if token:
        src_pdf = UPLOADS / f"{token}.pdf"
        if src_pdf.exists():
            shutil.copy(src_pdf, folder / "source.pdf")

    if not data.get("build", True):
        return jsonify({"ok": True, "built": False, "slug": slug, "flow_yaml": str(folder / "flow.yaml")})

    res = subprocess.run(
        [sys.executable, "build_flow.py", str(folder / "flow.yaml")],
        capture_output=True, text=True,
    )
    return jsonify({
        "ok": res.returncode == 0,
        "built": True,
        "slug": slug,
        "flow_name": flow_name,
        "output": (res.stdout or "") + (res.stderr or ""),
    })


@app.get("/api/flows")
def api_flows():
    out = []
    for d in sorted((ROOT / "flows").glob("M*")):
        fp = d / "flow.yaml"
        if fp.exists():
            doc = yaml.safe_load(fp.read_text(encoding="utf-8")) or {}
            out.append({
                "slug": d.name,
                "name": (doc.get("flow") or {}).get("name"),
                "steps": len(doc.get("steps", []) or []),
                "has_pdf": (d / "source.pdf").exists(),
            })
    return jsonify(out)


@app.get("/api/flow/<slug>")
def api_flow(slug):
    fp = ROOT / "flows" / slug / "flow.yaml"
    if not fp.exists():
        return jsonify({"error": "not found"}), 404
    return jsonify(yaml.safe_load(fp.read_text(encoding="utf-8")))


def _update_env(key: str, val: str | None):
    if not val:
        return
    os.environ[key] = val
    envp = ROOT / ".env"
    lines, found = [], False
    if envp.exists():
        for ln in envp.read_text(encoding="utf-8").splitlines():
            if ln.startswith(key + "="):
                lines.append(f"{key}={val}"); found = True
            else:
                lines.append(ln)
    if not found:
        lines.append(f"{key}={val}")
    envp.write_text("\n".join(lines) + "\n", encoding="utf-8")


@app.get("/api/settings")
def get_settings():
    return jsonify({
        "model": os.environ.get("OPENAI_MODEL", DEFAULT_MODEL),
        "openai_set": bool(os.environ.get("OPENAI_API_KEY")),
        "usertour_set": bool(os.environ.get("USERTOUR_API_TOKEN")),
    })


@app.post("/api/settings")
def set_settings():
    data = request.get_json(force=True)
    _update_env("OPENAI_API_KEY", (data.get("openai_key") or "").strip() or None)
    _update_env("OPENAI_MODEL", (data.get("model") or "").strip() or None)
    return jsonify({"ok": True})


if __name__ == "__main__":
    import threading
    import webbrowser

    url = "http://127.0.0.1:5000"
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    print(f"\nUsertour flow builder running at {url}  (close this window to stop)\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
