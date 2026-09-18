# AGENTS.md - MH Room Builder collaboration contract

This repository is the canonical shared development source for **MH Room Builder**.
Any ChatGPT/Codex worker or human contributor should read this file before changing code.

## Read first

1. `README.md`
2. `docs/PROJECT_STATE.md`
3. `docs/ARCHITECTURE.md`
4. `docs/WORKFLOW.md`
5. `docs/DATA_SCHEMA.md`
6. `docs/GEOMETRY_CONTRACT.md`
7. `docs/OLLAMA_LOCAL_AI.md`

## Non-negotiable product rules

- Dimensioned plan evidence is authoritative for measured XY geometry.
- Manual ceiling height is authoritative for Z until verified project data replaces it.
- AI is semantic evidence only; it must never create or auto-accept architectural geometry.
- A wall hypothesis becomes buildable only after explicit human acceptance.
- Plain walls must remain deterministic clean prisms: 8 vertices, 6 quad faces, no booleans, no remesh.
- Do not replace the source-of-truth architectural parameters with arbitrary mesh edits.
- Customer renderings may inform qualitative details but may not silently invent exact dimensions.
- Do not weaken conservative calibration/review gates just to make a demo appear successful.

## Privacy / data handling

- Do not commit customer PDFs, DWGs, renderings, analysis outputs, local datasets, or model caches unless the user explicitly approves a sanitized fixture.
- Ollama is local-first. Non-local model endpoints must remain opt-in.
- Training truth may come only from explicit human labels, never directly from AI guesses.

## Development workflow

- Work on a dedicated branch for non-trivial changes.
- Keep changes scoped; do not refactor unrelated modules while implementing a ticket.
- Run `python -m pytest -q` before opening a PR.
- Update `docs/PROJECT_STATE.md` whenever behavior, known limitations, test baseline, or the next milestone changes.
- Update the manifest version when producing a new installable Blender extension.
- Keep the extension package importable under Blender's extension namespace; root imports must remain relative.

## Branch convention

Examples:

- `feat/wall-review-overlay`
- `feat/ollama-semantic-review`
- `fix/extension-packaging`
- `test/raster-floorplan-regressions`

## Current priority

The next product-critical layer is the in-Blender floorplan review overlay and architectural graph/constraint workflow described in `docs/PROJECT_STATE.md` and `docs/ROADMAP.md`.
