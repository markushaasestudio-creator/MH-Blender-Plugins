# Architecture

## Design rule

MH Room Builder is a **constraint-driven reconstruction system**. Blender meshes are generated representations, not the primary source of truth.

## Main layers

```text
Customer input
  |
  +-- dimensioned floorplan
  +-- optional reference renderings
  |
  v
Source analyzer
  +-- PDF vector extraction
  +-- raster render / OCR
  +-- dimension parsing
  +-- scale calibration
  +-- line consolidation
  |
  v
Geometric hypothesis layer
  +-- candidate endpoints
  +-- candidate thickness
  +-- geometry confidence
  +-- provenance/evidence
  |
  +----------------------+
  |                      |
  v                      v
Local semantic AI       Human review
Ollama vision            accept/reject/edit/classify
  |                      |
  +----------+-----------+
             v
Verified architectural data
             |
             v
Deterministic Blender geometry
```

## Module map

### `blender_extension/mh_room_builder/domain/`
Pure architectural/domain data and geometry primitives. Keep Blender-specific state out when practical.

### `blender_extension/mh_room_builder/analyzer/`
External-analysis logic: dimensions, calibration, vector/raster extraction, hypotheses, Ollama client and semantic review helpers.

### `analyzer_runner.py`
Boundary between Blender and the external analyzer process.

### `props.py`
Blender properties and mutable review state.

### `operators.py`
User actions and orchestration.

### `ui.py`
Blender panel/UI presentation.

### `geometry_builder.py`
Conversion from verified architectural parameters to Blender mesh objects.

## Truth hierarchy

1. Verified/measured dimensions
2. Explicit project values (for example manual ceiling height)
3. Geometric constraints/hypotheses
4. Semantic AI evidence
5. Human review state

AI evidence is not promoted into measured truth.

## Geometry invariant

A plain wall remains a rectangular prism with exactly 8 vertices and 6 quad faces. Future openings should be modeled by rectilinear decomposition (piers, sill, header, reveals) rather than destructive booleans.

## Long-term model

Move toward a constrained 2D architectural graph:

- nodes = corners/intersections,
- edges = wall axes/boundaries,
- constraints = measured dimensions, orthogonality/parallelism, continuity,
- semantic evidence = labels on graph elements,
- Blender objects = generated outputs.
