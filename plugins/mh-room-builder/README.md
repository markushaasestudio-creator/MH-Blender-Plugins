# MH Room Builder v0.1.3

A conservative Blender extension foundation for reconstructing dimensioned customer floorplans into clean architectural geometry, with a local Ollama vision model as a **semantic reviewer** rather than a geometry generator.

## Product principle

The system deliberately separates four kinds of truth:

1. **Measured truth** - dimensions and calibrated drawing geometry.
2. **Geometric hypotheses** - line pairs that could represent walls.
3. **Semantic evidence** - local vision-AI classification such as wall, cabinet, kitchen or furniture.
4. **Human verification** - the only event that can promote a hypothesis into buildable wall geometry.

Qwen/Ollama is never allowed to create or authorize wall geometry by itself.

## Canonical studio working directory

Continue using the established local project path:

```text
E:\Cloud-Drive_markushaasestudio@gmail.com\Projects\Room_Builder_Blender_Add-On\MH_ROOM_BUILDER_v0.1_SOURCE\MH_ROOM_BUILDER_v0.1
```

The `.venv-analyzer` already created there remains valid. v0.1.3 adds no mandatory Python package beyond v0.1.1.

## Target

- Blender 5.2 LTS
- Windows-first workflow
- external Python 3.13 analyzer environment
- local Ollama REST API, default `http://127.0.0.1:11434`
- a vision-capable local model (Qwen preferred, but not hard-coded)

## What v0.1.3 adds

### Reviewable wall hypotheses

The analyzer now persists geometric wall hypotheses instead of discarding them after diagnostics. Every candidate stores:

- source-image endpoints,
- millimetre endpoints,
- detected thickness,
- geometry score,
- geometric evidence,
- semantic evidence fields.

For raster and vector plans alike, these hypotheses are **not buildable until a human accepts them**.

### Manual wall review

Blender receives a filtered review list. The selected candidate can be:

- inspected as a context crop,
- edited numerically (start/end XY and thickness),
- accepted as wall,
- rejected,
- manually classified as wall/cabinet/kitchen/furniture/etc.,
- reset to unreviewed.

Only human-accepted candidates can be built.

### Local Ollama semantic reviewer

The extension talks to Ollama through its local REST API. It can:

- discover installed models,
- inspect model capabilities,
- reject text-only models for image work,
- send candidate contact sheets to a vision model,
- require structured JSON output,
- assign semantic classes and evidence scores,
- keep those AI results separate from manual review state.

The model is configurable by exact Ollama tag, so the extension does not assume a particular Qwen package name.

### Privacy gate

The default endpoint is localhost. The semantic bridge refuses to send customer plans or renderings to a non-local endpoint unless `Allow non-local endpoint` is explicitly enabled in Blender.

### Dataset capture for a future MH-specific model

Manual labels can be stored locally as training examples. A training example contains:

- a clean, unannotated source crop,
- the manually assigned class,
- candidate geometry metadata,
- candidate line coordinates within the crop.

AI guesses are **not** recorded as training truth. Only explicit human classifications are.

### Reference-rendering semantic foundation

Registered customer renderings can be sent to the same local vision model for qualitative architectural observations:

- windows,
- doors,
- cabinetry,
- kitchen elements,
- wall/ceiling details,
- visible frame/division patterns,
- uncertainty notes.

No AI-derived millimetre dimension is applied automatically.

## Core workflow

```text
DIMENSIONED FLOORPLAN
        |
        v
PDF / raster analyzer
        |
        +--> dimension OCR / vector text
        +--> scale calibration
        +--> line detection
        +--> geometric wall hypotheses
        |
        v
LOCAL SEMANTIC REVIEW (optional)
Qwen vision via Ollama
        |
        +--> WALL / CABINET / KITCHEN / ...
        +--> AI evidence score
        +--> short rationale
        |
        v
HUMAN WALL REVIEW
        |
        +--> accept
        +--> reject / classify
        +--> edit endpoints / thickness
        |
        v
VERIFIED ARCHITECTURAL DATA
        |
        v
CLEAN BLENDER WALL GEOMETRY
8 verts / 6 quads / no booleans
```

## First test after installing v0.1.3

1. Install the v0.1.3 extension ZIP over the previous version.
2. Keep the existing `Analyzer Python` path unchanged.
3. Re-run `Analyze Floorplan` because v0.1.1 analysis JSON did not persist wall hypotheses.
4. In `Local semantic AI / Ollama`, leave the endpoint at `http://127.0.0.1:11434`.
5. Click `Detect Models`.
6. Confirm that the desired Qwen model is selected or type its exact Ollama model tag.
7. Click `Test Model`. The plugin requires the model to advertise Ollama's `vision` capability.
8. Click `AI Review Next Batch` for a small first batch.
9. Select candidates in the Wall Review list, inspect crops and accept/reject them manually.
10. Once at least one wall is accepted, `Build Accepted Walls` becomes available.

## Important limitation of this build

v0.1.3 implements the complete **data/review/AI foundation**, but the wall-review visualization is not yet an editable overlay drawn directly on top of the floorplan inside Blender. Human review is currently a candidate list plus per-candidate context crop and numeric geometry fields. A true in-viewport plan overlay is the next UI layer.

## Geometry contract

A plain accepted wall is generated as exactly:

- 8 vertices,
- 6 quad faces,
- no triangles,
- no n-gons,
- no boolean modifier,
- no remesh.

Openings remain a later stage and will use rectilinear wall decomposition rather than arbitrary boolean cutting.

## Tests

The project test suite covers:

- metric and imperial dimension parsing,
- conservative ambiguous-number handling,
- clean wall prism topology,
- wall-hypothesis serialization,
- local-endpoint privacy gating,
- candidate crop generation,
- a mocked Ollama vision + structured-output API request.

The real Living Room raster PDF used during development still resolves dimension calibration and hundreds of wall hypotheses, but v0.1.3 keeps those hypotheses non-buildable until manual acceptance.
