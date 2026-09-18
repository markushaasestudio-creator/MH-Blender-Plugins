# Data schema v0.1.3 - relevant wall hypothesis fields

```json
{
  "id": "R0001",
  "start_source": [100.0, 200.0],
  "end_source": [500.0, 200.0],
  "start_mm": [6343.4, -12686.8],
  "end_mm": [31717.0, -12686.8],
  "thickness_mm": 126.9,
  "geometry_confidence": 0.94,
  "source": "parallel_line_pair",
  "evidence": ["..."],
  "semantic": {
    "class": "UNKNOWN",
    "confidence": 0.0,
    "source": "none",
    "model": "",
    "structural_boundary": null,
    "rationale": ""
  }
}
```

Blender stores mutable review state separately:

- edited start/end/thickness,
- AI class/score/source/model/rationale,
- human class,
- human review status.

This separation keeps the original analysis reproducible while allowing a reviewed Blender project to evolve.
