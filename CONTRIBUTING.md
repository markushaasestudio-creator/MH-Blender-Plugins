# Contributing

MH Blender Plugins is organized as a monorepo of independent Blender extensions.

## Adding a plugin

Create a new directory:

```
plugins/<plugin-slug>/
```

A plugin should normally contain:
- `README.md`
- `AGENTS.md`
- `blender_extension/`
- `docs/`
- `tests/`
- build/setup scripts where needed

Do not place a new plugin directly in the repository root.

## Existing plugins

Changes to an existing plugin should stay inside its directory unless repository-wide tooling is intentionally being changed.

## Pull requests

A PR should state:
- target plugin,
- user-visible behavior changed,
- architecture/contracts affected,
- tests run,
- remaining uncertainty,
- whether customer data was used locally.

## Versioning

Each plugin versions independently. Repository-wide versioning is intentionally avoided.
