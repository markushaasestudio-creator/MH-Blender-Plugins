# MH Room Builder - Geometry Contract v0.1.3

## 1. Sources of truth

- Dimensioned floorplan evidence controls XY scale and measured geometry.
- Manually entered ceiling height controls Z until replaced by verified project data.
- Local AI output is semantic evidence only.
- Customer renderings are non-authoritative evidence only.
- Human acceptance is required before a geometric hypothesis becomes buildable wall data.

## 2. Wall primitive

A plain wall is generated from start point, end point, thickness and height as one rectangular prism:

- exactly 8 vertices,
- exactly 6 quad faces,
- no triangles,
- no n-gons,
- no boolean modifiers,
- no destructive remesh.

Each wall is an individual object with provenance metadata.

## 3. Review-state separation

`geometry_confidence`, `semantic_class`, `semantic_confidence`, `user_class` and `review_status` are different fields. They must not be collapsed into one confidence number.

AI evidence cannot set `review_status=ACCEPTED`.

## 4. Candidate editing

Human edits change candidate parameters (start/end/thickness). The generated mesh is regenerated from those values. Users should not need to repair arbitrary mesh topology.

## 5. Openings

Doors/windows are not yet generated in v0.1.3. When implemented, wall topology must be decomposed into explicit rectilinear components (piers, sill, header, reveals) instead of relying on arbitrary boolean cuts.

## 6. Future architectural graph

The long-term source model is a constrained 2D architectural graph. Corners are nodes; wall baselines/boundaries are edges; dimensions are constraints. Blender mesh objects remain generated representations of that graph.
