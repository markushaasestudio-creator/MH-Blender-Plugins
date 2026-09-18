from __future__ import annotations

from .geometry2d import P2


def serialize_wall_hypotheses(candidates: list[dict], mm_per_unit: float, prefix: str = "H") -> list[dict]:
    """Serialize geometric line-pair hypotheses without promoting them to walls.

    Source coordinates remain available for image crops. Millimetre coordinates use
    a conventional Blender-friendly XY orientation (source Y is inverted).
    """
    if not mm_per_unit or mm_per_unit <= 0:
        return []
    result: list[dict] = []
    for index, candidate in enumerate(candidates, start=1):
        start: P2 = candidate["start"]
        end: P2 = candidate["end"]
        result.append(
            {
                "id": f"{prefix}{index:04d}",
                "start_source": [float(start.x), float(start.y)],
                "end_source": [float(end.x), float(end.y)],
                "start_mm": [float(start.x * mm_per_unit), float(-start.y * mm_per_unit)],
                "end_mm": [float(end.x * mm_per_unit), float(-end.y * mm_per_unit)],
                "thickness_mm": float(candidate["thickness_mm"]),
                "geometry_confidence": float(candidate.get("confidence", 0.0)),
                "source": str(candidate.get("source", "unknown")),
                "evidence": [str(v) for v in candidate.get("evidence", [])],
                "semantic": {
                    "class": "UNKNOWN",
                    "confidence": 0.0,
                    "source": "none",
                    "model": "",
                    "structural_boundary": None,
                    "rationale": "",
                },
            }
        )
    return result
