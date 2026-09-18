# AGENTS.md — MH Blender Plugins

This repository is a monorepo for independent Blender plugins developed for Markus Haase Studio.

## Source of truth

- The repository itself is the source of truth.
- Each plugin lives under `plugins/<plugin-slug>/`.
- Before changing a plugin, read:
  1. this file,
  2. the plugin's own `AGENTS.md`,
  3. the plugin `README.md`,
  4. `docs/PROJECT_STATE.md`,
  5. any contract documents referenced there.

## Scope discipline

- Do not modify another plugin while working on one plugin unless the task explicitly requires repository-wide infrastructure.
- Do not create hidden cross-plugin dependencies.
- Shared code belongs in `shared/` only after a recurring need has been demonstrated.
- Preserve existing behavior unless the task explicitly changes it.
- Do not silently rewrite architecture or geometry contracts.

## Branching

For non-trivial work:
- create a dedicated feature/fix branch,
- keep changes scoped to the assigned plugin,
- run the plugin's tests,
- open a PR to `main`,
- document assumptions and unresolved issues in the PR.

Do not merge unrelated work into the same PR.

## Customer-data safety

Never commit:
- customer floorplans,
- customer renderings,
- private project data,
- local model files,
- virtual environments,
- analyzer caches,
- generated semantic-training datasets from customer data,
- secrets or API keys.

Only synthetic or explicitly sanitized fixtures may be committed.

## Blender plugin quality

- Prefer deterministic, inspectable geometry over opaque mesh manipulation.
- Preserve clean topology contracts.
- Local AI may provide semantic evidence, but must not silently override authoritative dimensions or human review.
- New failure-prone behavior requires tests or a documented manual verification path.
