from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json

SCHEMA_VERSION = "0.1.2"


@dataclass(frozen=True, slots=True)
class Point2D:
    x_mm: float
    y_mm: float

    @classmethod
    def from_list(cls, value: list[float] | tuple[float, float]) -> "Point2D":
        return cls(float(value[0]), float(value[1]))

    def to_list(self) -> list[float]:
        return [self.x_mm, self.y_mm]


@dataclass(slots=True)
class DimensionEvidence:
    text: str
    value_mm: float
    bbox_source: tuple[float, float, float, float]
    confidence: float = 0.5
    unit_interpretation: str = "unknown"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DimensionEvidence":
        return cls(
            text=str(data["text"]),
            value_mm=float(data["value_mm"]),
            bbox_source=tuple(float(v) for v in data["bbox_source"]),
            confidence=float(data.get("confidence", 0.5)),
            unit_interpretation=str(data.get("unit_interpretation", "unknown")),
        )


@dataclass(slots=True)
class SemanticEvidence:
    semantic_class: str = "UNKNOWN"
    confidence: float = 0.0
    source: str = "none"
    model: str = ""
    structural_boundary: bool | None = None
    rationale: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SemanticEvidence":
        data = data or {}
        boundary = data.get("structural_boundary")
        if boundary is not None:
            boundary = bool(boundary)
        return cls(
            semantic_class=str(data.get("class", data.get("semantic_class", "UNKNOWN"))).upper(),
            confidence=float(data.get("confidence", 0.0)),
            source=str(data.get("source", "none")),
            model=str(data.get("model", "")),
            structural_boundary=boundary,
            rationale=str(data.get("rationale", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "class": self.semantic_class,
            "confidence": self.confidence,
            "source": self.source,
            "model": self.model,
            "structural_boundary": self.structural_boundary,
            "rationale": self.rationale,
        }


@dataclass(slots=True)
class WallHypothesis:
    id: str
    start_source: tuple[float, float]
    end_source: tuple[float, float]
    start: Point2D
    end: Point2D
    thickness_mm: float
    geometry_confidence: float
    source: str = "unknown"
    evidence: list[str] = field(default_factory=list)
    semantic: SemanticEvidence = field(default_factory=SemanticEvidence)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WallHypothesis":
        return cls(
            id=str(data["id"]),
            start_source=tuple(float(v) for v in data.get("start_source", (0.0, 0.0))),
            end_source=tuple(float(v) for v in data.get("end_source", (0.0, 0.0))),
            start=Point2D.from_list(data["start_mm"]),
            end=Point2D.from_list(data["end_mm"]),
            thickness_mm=float(data["thickness_mm"]),
            geometry_confidence=float(data.get("geometry_confidence", data.get("confidence", 0.0))),
            source=str(data.get("source", "unknown")),
            evidence=[str(v) for v in data.get("evidence", [])],
            semantic=SemanticEvidence.from_dict(data.get("semantic")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "start_source": list(self.start_source),
            "end_source": list(self.end_source),
            "start_mm": self.start.to_list(),
            "end_mm": self.end.to_list(),
            "thickness_mm": self.thickness_mm,
            "geometry_confidence": self.geometry_confidence,
            "source": self.source,
            "evidence": self.evidence,
            "semantic": self.semantic.to_dict(),
        }


@dataclass(slots=True)
class WallCandidate:
    id: str
    start: Point2D
    end: Point2D
    thickness_mm: float
    confidence: float
    source: str = "unknown"
    evidence: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WallCandidate":
        return cls(
            id=str(data["id"]),
            start=Point2D.from_list(data["start_mm"]),
            end=Point2D.from_list(data["end_mm"]),
            thickness_mm=float(data["thickness_mm"]),
            confidence=float(data.get("confidence", data.get("geometry_confidence", 0.0))),
            source=str(data.get("source", "unknown")),
            evidence=[str(v) for v in data.get("evidence", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "start_mm": self.start.to_list(),
            "end_mm": self.end.to_list(),
            "thickness_mm": self.thickness_mm,
            "confidence": self.confidence,
            "source": self.source,
            "evidence": self.evidence,
        }


@dataclass(slots=True)
class Calibration:
    mm_per_source_unit: float | None = None
    confidence: float = 0.0
    method: str = "unresolved"
    evidence: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Calibration":
        value = data.get("mm_per_source_unit")
        return cls(
            mm_per_source_unit=None if value is None else float(value),
            confidence=float(data.get("confidence", 0.0)),
            method=str(data.get("method", "unresolved")),
            evidence=[str(v) for v in data.get("evidence", [])],
        )


@dataclass(slots=True)
class AnalysisResult:
    source_path: str
    page: int
    calibration: Calibration
    walls: list[WallCandidate] = field(default_factory=list)
    wall_hypotheses: list[WallHypothesis] = field(default_factory=list)
    dimensions: list[DimensionEvidence] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source_kind: str = "unknown"
    preview_path: str = ""
    analysis_preview_path: str = ""
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnalysisResult":
        return cls(
            source_path=str(data.get("source", {}).get("path", "")),
            page=int(data.get("source", {}).get("page", 1)),
            source_kind=str(data.get("source", {}).get("kind", "unknown")),
            calibration=Calibration.from_dict(data.get("calibration", {})),
            walls=[WallCandidate.from_dict(v) for v in data.get("walls", [])],
            wall_hypotheses=[WallHypothesis.from_dict(v) for v in data.get("wall_hypotheses", [])],
            dimensions=[DimensionEvidence.from_dict(v) for v in data.get("dimensions", [])],
            warnings=[str(v) for v in data.get("warnings", [])],
            preview_path=str(data.get("preview_path") or ""),
            analysis_preview_path=str(data.get("analysis_preview_path") or ""),
            schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
        )

    @classmethod
    def load(cls, path: str | Path) -> "AnalysisResult":
        with Path(path).open("r", encoding="utf-8") as handle:
            return cls.from_dict(json.load(handle))
