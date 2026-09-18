# Project State - MH Room Builder

**Canonical code version:** v0.1.3  
**Last consolidated:** 2026-09-18  
**Target:** Blender 5.2 LTS, Windows-first, external analyzer Python, local Ollama vision model

## Current working state

The project currently has a functioning conservative foundation for:

- Blender extension installation and MH Room Builder UI,
- dimensioned PDF/raster input,
- manual authoritative ceiling height,
- vector/raster plan classification,
- metric and imperial dimension parsing,
- raster dimension OCR/calibration,
- line detection and geometric wall hypotheses,
- persistence of wall hypotheses for manual review,
- manual candidate accept/reject/classification/edit fields,
- deterministic clean wall generation,
- local Ollama model discovery/capability checks,
- local vision semantic review plumbing,
- local-only privacy gate,
- optional manual-label dataset capture,
- qualitative reference-rendering AI analysis foundation.

## Verified test baseline

`python -m pytest -q`

Current result:

```text
10 passed
```

Coverage includes dimension parsing, wall topology, hypothesis serialization, local-endpoint safety, semantic crop generation, and mocked Ollama structured vision requests.

## Real-plan development finding

The first real Living Room customer PDF was an image/raster PDF rather than a usable CAD-vector PDF. The raster pipeline successfully reached approximately:

- 94% calibration confidence,
- low-twenties recognized dimension labels,
- roughly 1.3k-1.4k merged line segments,
- several hundred raw wall hypotheses.

Those values are diagnostic only and can vary by OCR/runtime version. No raw raster hypothesis is buildable without manual review.

The real customer PDF is intentionally **not** stored in this repository.

## Known limitations

1. Wall review is list/crop/numeric-field based; there is no direct interactive floorplan overlay yet.
2. The raw hypothesis generator still over-generates many furniture/cabinet/annotation line pairs on complex plans.
3. Ollama integration depends on an installed vision-capable model and has not been validated here against the studio's exact live Qwen tag.
4. Doors/windows are not yet reconstructed as architectural opening graphs.
5. Reference renderings are evidence-only; no automatic metric geometry is derived from them.
6. No DWG/DXF direct import path yet.
7. Blender runtime validation must still be performed on the studio workstation for every packaged release.

## Packaging incident already fixed

v0.1.2 contained an invalid top-level absolute import:

```python
from mh_room_builder import register, unregister
```

Under Blender's extension namespace this caused `No module named "mh_room_builder"`.

v0.1.3 fixed it to the required relative import:

```python
from .mh_room_builder import register, unregister
```

Do not regress this.

## Next milestone

### v0.1.4 - Interactive Wall Review Overlay

Priority goals:

- draw the source floorplan inside Blender in a review workspace,
- overlay wall hypotheses spatially,
- candidate selection by clicking the plan,
- visible geometry-score / semantic-class state,
- accept / reject / reset in spatial context,
- endpoint handles or constrained numeric editing,
- group/merge collinear segments,
- explicit missing-wall manual creation,
- clear distinction between raw, AI-reviewed, human-accepted and rejected states.

Do **not** add automatic doors/windows before this review layer is reliable.

## Following milestones

See `docs/ROADMAP.md`.
