# MH Room Builder - Target Workflow v0.1.3

## A. Project input

1. Select a dimensioned floorplan.
2. Select its PDF page where applicable.
3. Enter ceiling height manually in millimetres.
4. Optionally provide an expected wall thickness only as a detection hint.
5. Register customer renderings as non-authoritative references.

## B. Deterministic source analysis

The external analyzer classifies vector vs raster content, extracts linework and dimensions, and resolves drawing scale from multiple pieces of evidence. It does not call AI for scale or measured dimensions.

## C. Geometric hypothesis generation

Parallel line pairs are transformed into wall hypotheses containing source coordinates, millimetre coordinates, thickness and a geometry score. Hypotheses are not walls.

## D. Local semantic review (optional)

A vision-capable Ollama model receives contextual candidate crops. A highlighted centerline tells the model which geometric hypothesis to classify. Allowed semantic classes are deliberately small and architectural:

- WALL
- CABINET
- KITCHEN
- FURNITURE
- DOOR
- WINDOW
- COLUMN
- STAIRS
- SANITARY
- DIMENSION
- ANNOTATION
- UNKNOWN

The AI output is evidence only. It never changes human review state.

## E. Human review

The human can inspect, edit and label candidates. Only `ACCEPTED` candidates become buildable walls. Rejections may be labelled for future model training.

## F. Clean geometry generation

Accepted candidates are rebuilt deterministically from architectural parameters. Mesh vertices are an output, not the source of truth.

## G. Local learning loop

When enabled, explicit manual labels generate a local MH dataset. Raw source crops are stored without the AI review overlay to prevent the future model from learning the annotation marker rather than the underlying plan semantics.

## H. Reference renderings

The same local vision backend can extract qualitative observations from customer renderings. It is intentionally prevented from asserting exact dimensions or hidden geometry.

## Next layer

The next milestone is an in-Blender floorplan overlay with selectable candidate lines, endpoint handles and spatial accept/reject feedback. After that come the 2D architectural graph/constraint solver and doors/windows.
