# Contributing

MH Room Builder is developed as a conservative architecture-reconstruction tool, not as a generative mesh demo.

## Before coding

Read `AGENTS.md` and `docs/PROJECT_STATE.md`. If a proposed change conflicts with the geometry contract or AI/human-review separation, resolve that design issue before implementation.

## Pull requests

A PR should state:

- problem being solved,
- files/modules changed,
- behavior before/after,
- tests run,
- any new assumptions,
- effect on geometry invariants,
- effect on customer-data privacy,
- remaining known limitations.

Keep unrelated cleanup out of feature PRs.

## Test requirement

Run:

```bash
python -m pytest -q
```

The current baseline is recorded in `docs/PROJECT_STATE.md`.

## Real customer plans

Do not add unsanitized customer material to GitHub. Use local regression inputs or create synthetic/sanitized fixtures that reproduce the failure mode without customer-identifying content.
