# Repository Architecture

## Goal

This repository hosts multiple Blender development plugins without coupling their release cycles or implementation details.

```text
MH-Blender-Plugins/
├─ AGENTS.md
├─ CONTRIBUTING.md
├─ README.md
├─ docs/
├─ plugins/
│  ├─ mh-room-builder/
│  └─ <future-plugin>/
└─ shared/                  # only when a real cross-plugin abstraction exists
```

## Plugin boundaries

Every directory below `plugins/` is an independent product boundary.

A plugin owns:
- its Blender extension manifest,
- its Python package,
- its tests,
- its documentation,
- its external/local service integrations,
- its release version.

A plugin must not import code directly from another plugin.

## Shared code

Do not create `shared/` pre-emptively. Code moves there only after at least two plugins require the same stable behavior and the abstraction has a clear owner and tests.

## Current plugin

`plugins/mh-room-builder/` contains MH Room Builder, currently based on v0.1.3.

The Room Builder uses a hybrid architecture:
- deterministic floorplan and dimension analysis,
- clean parametric geometry generation,
- optional local semantic review through Ollama/Qwen,
- explicit human review before geometry is accepted.

Its own contracts and current implementation state are documented inside that plugin directory.
