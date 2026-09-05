# UserTour-Automation-v1

Semi-automated pipeline for turning FieldPie step-by-step tutorials into
[Usertour](https://usertour.io) onboarding flows.

## What it does

The manual process today is: read a guidde PDF tutorial, write a step name,
tooltip title and tooltip text for each step, then recreate the flow in the
Usertour panel and bind every step to a UI element with a CSS selector.

This tool automates the content-authoring part. You keep an intermediate,
human-reviewable flow file; the tool pushes it to Usertour through the
official **v2 REST API** (deterministic, no brittle browser automation).
Binding selectors stays a deliberate manual step, except for elements that
repeat across flows (Forms menu, pencil icon, Save button, ...), which are
resolved automatically from a shared selector dictionary.

## Scope

In scope: structured step data, step content generation, creating and
updating flows/versions through the API, an intermediate format, and a
reusable selector dictionary.

Out of scope: clicking through the Usertour panel with browser automation,
scraping selectors from the screen, and any change to FieldPie's frontend.

## Status

Phase 1 scaffold. See `docs/roadmap.md`.

## Setup

    python3 -m venv .venv
    source .venv/bin/activate        # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    cp .env.example .env             # then fill in your token

Get a token from the Usertour dashboard: Settings -> Personal API keys.
Required scopes: content:read, content:create, content:update,
content:publish, theme:read.

## Usage

Verify the connection and discover your project, themes and environments:

    python validate_api.py

Build a flow from an intermediate file. A dry run assembles the JSON into
`build/` without touching the API:

    python build_flow.py schema/flow.example.yaml --dry-run
    python build_flow.py schema/flow.example.yaml

## Layout

    schema/flow.example.yaml   Example intermediate flow
    schema/selectors.yaml      Shared selector dictionary (repeated elements)
    src/config.py              Environment configuration
    src/client.py              Thin Usertour v2 REST client
    src/flow_builder.py        Intermediate format -> Usertour step payload
    validate_api.py            Connectivity / discovery smoke test
    build_flow.py              Build (and optionally upload) one flow

## Creating a flow from a PDF

1. Drop the guidde PDF in the project (e.g. under `flows/<slug>/source.pdf`).
2. Extract the raw steps:

       python extract_pdf.py "flows/<slug>/source.pdf"

   This writes `source.raw.yaml` (step number, title, description) next to it.
3. Curate `raw.yaml` into a final `flow.yaml`: native English wording, fix
   titles that do not match the action, skip intro/empty frames, reference
   repeated elements from `schema/selectors.yaml`, and add the `ending` modal.
4. Build the draft and bind selectors in the panel:

       python build_flow.py flows/<slug>/flow.yaml

## Helper scripts

    validate_api.py       Connectivity / discovery smoke test
    faz0_probe.py         One-off API behavior probe
    list_flows.py         List flows with publish status (for numbering)
    dump_flow.py          Dump an existing flow's JSON (to copy its structure)
    extract_pdf.py        guidde PDF -> raw step YAML
    build_flow.py         Build (and optionally publish) a flow
    set_bold_color.py     Brand-color bold via theme CSS (needs Growth plan)
