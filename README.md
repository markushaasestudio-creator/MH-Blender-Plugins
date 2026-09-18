# MH Blender Plugins

Monorepo for Blender tools developed for Markus Haase Studio.

## Repository layout

```text
MH-Blender-Plugins/
├─ AGENTS.md
├─ CONTRIBUTING.md
├─ docs/
│  └─ REPOSITORY_ARCHITECTURE.md
├─ plugins/
│  └─ mh-room-builder/
│     ├─ AGENTS.md
│     ├─ README.md
│     ├─ blender_extension/
│     ├─ docs/
│     ├─ tests/
│     └─ ...
└─ .github/
```

Each Blender plugin lives independently under `plugins/<plugin-slug>/`. Plugins must not depend on another plugin's private implementation. Shared code may be introduced later under a deliberate `shared/` package only when there is a real recurring need.

## Current plugins

### MH Room Builder

Status: active development. Current baseline: v0.1.3.

Purpose: reconstruct clean, dimension-driven Blender room geometry from dimensioned floorplans, with local semantic assistance through Ollama/Qwen and an explicit human-review gate before geometry is built.

See `plugins/mh-room-builder/docs/PROJECT_STATE.md` before changing the Room Builder.

## Collaboration rule

Any worker or ChatGPT thread that modifies this repository should:

1. Read this README and the root `AGENTS.md`.
2. Read the target plugin's `AGENTS.md`, `README.md`, and `docs/PROJECT_STATE.md`.
3. Work only inside the target plugin unless the task explicitly concerns repository-wide infrastructure.
4. Preserve the target plugin's contracts and tests.
5. Use a feature branch for non-trivial work and open a PR rather than silently changing unrelated plugins.

## Data policy

Do not commit customer floorplans, customer renderings, private project data, locally generated training datasets, virtual environments, analyzer caches, or Ollama model files.

Synthetic test fixtures are allowed when they contain no customer information.
