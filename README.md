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
