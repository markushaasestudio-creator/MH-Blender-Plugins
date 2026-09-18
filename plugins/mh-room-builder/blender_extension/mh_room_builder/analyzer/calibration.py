from __future__ import annotations

from dataclasses import dataclass
from math import pi
from statistics import median

from .geometry2d import Segment


@dataclass(frozen=True, slots=True)
class TextDimension:
    text: str
    value_mm: float
    bbox: tuple[float, float, float, float]
    confidence: float
    interpretation: str
    direction: tuple[float, float] = (1.0, 0.0)


@dataclass(frozen=True, slots=True)
class CalibrationResult:
    mm_per_unit: float | None
    confidence: float
    method: str
    evidence: tuple[str, ...]


def calibration_from_print_scale(denominator: int) -> CalibrationResult:
    mm_per_point = 25.4 / 72.0 * denominator
    return CalibrationResult(mm_per_unit=mm_per_point, confidence=0.82, method="printed_pdf_scale", evidence=(f"printed scale 1:{denominator}",))


def infer_calibration_from_dimensions(dimensions: list[TextDimension], segments: list[Segment], max_text_line_distance: float = 80.0, min_cluster_size: int = 1, min_line_to_text_ratio: float = 1.0) -> CalibrationResult:
    ratios: list[tuple[float, str]] = []
    for dim in dimensions:
        x0, y0, x1, y1 = dim.bbox
        cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
        horizontal_text = abs(dim.direction[0]) >= abs(dim.direction[1])
        text_axis_size = max((x1 - x0) if horizontal_text else (y1 - y0), 1.0)
        best: tuple[float, Segment] | None = None
        for seg in segments:
            if seg.length <= 1e-6 or seg.length < text_axis_size * min_line_to_text_ratio:
                continue
            angle = seg.angle
            horizontal_line = min(angle, abs(pi - angle)) < (8.0 * pi / 180.0)
            vertical_line = abs(angle - pi * 0.5) < (8.0 * pi / 180.0)
            if horizontal_text and not horizontal_line:
                continue
            if not horizontal_text and not vertical_line:
                continue
            min_x, max_x = sorted((seg.a.x, seg.b.x))
            min_y, max_y = sorted((seg.a.y, seg.b.y))
            if horizontal_line:
                if not (min_x - 8 <= cx <= max_x + 8):
                    continue
                distance = min(abs(cy - seg.a.y), abs(cy - seg.b.y))
            else:
                if not (min_y - 8 <= cy <= max_y + 8):
                    continue
                distance = min(abs(cx - seg.a.x), abs(cx - seg.b.x))
            if distance > max_text_line_distance:
                continue
            if best is None or distance < best[0]:
                best = (distance, seg)
        if best is not None:
            _, line = best
            ratio = dim.value_mm / line.length
            if 0.02 <= ratio <= 500.0:
                ratios.append((ratio, f"{dim.text} / line {line.length:.2f}"))
    if not ratios:
        return CalibrationResult(None, 0.0, "unresolved", ("no dimension-line scale evidence",))
    return _cluster_ratios(ratios, min_cluster_size=min_cluster_size, method="dimension_consensus")


def _axis_kind(seg: Segment, angle_tol_deg: float = 2.0) -> str | None:
    tol = angle_tol_deg * pi / 180.0
    angle = seg.angle
    if min(angle, abs(pi - angle)) <= tol:
        return "H"
    if abs(angle - pi * 0.5) <= tol:
        return "V"
    return None


def _cluster_ratios(ratios: list[tuple[float, str]], min_cluster_size: int, method: str, relative_tolerance: float = 0.045) -> CalibrationResult:
    if not ratios:
        return CalibrationResult(None, 0.0, "unresolved", ("no scale candidates",))
    best_cluster: list[tuple[float, str]] = []
    for ratio, _ in ratios:
        cluster = [item for item in ratios if abs(item[0] - ratio) / max(ratio, 1e-9) <= relative_tolerance]
        if len(cluster) > len(best_cluster):
            best_cluster = cluster
    if len(best_cluster) < min_cluster_size:
        return CalibrationResult(None, 0.0, "unresolved", (f"only {len(best_cluster)} consistent scale sample(s); need {min_cluster_size}",))
    values = [item[0] for item in best_cluster]
    mm_per_unit = median(values)
    cluster_fraction = len(best_cluster) / max(len(ratios), 1)
    confidence = min(0.94, 0.46 + 0.055 * len(best_cluster) + 0.24 * min(cluster_fraction * 3.0, 1.0))
    evidence = tuple(item[1] for item in best_cluster[:12])
    return CalibrationResult(mm_per_unit, confidence, method, evidence)


def infer_raster_calibration_from_dimension_spans(dimensions: list[TextDimension], segments: list[Segment], min_cluster_size: int = 3) -> CalibrationResult:
    horizontal_segments = [s for s in segments if _axis_kind(s) == "H"]
    vertical_segments = [s for s in segments if _axis_kind(s) == "V"]
    candidates: list[tuple[float, str, str]] = []
    for dim in dimensions:
        if dim.confidence < 0.25:
            continue
        x0, y0, x1, y1 = dim.bbox
        cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
        horizontal_text = abs(dim.direction[0]) >= abs(dim.direction[1])
        label_key = f"{round(cx)}:{round(cy)}:{round(dim.value_mm)}"
        parallel = horizontal_segments if horizontal_text else vertical_segments
        perpendicular = vertical_segments if horizontal_text else horizontal_segments
        line_coords: list[tuple[float, float]] = []
        for seg in parallel:
            if seg.length < 60.0:
                continue
            if horizontal_text:
                coord = (seg.a.y + seg.b.y) * 0.5
                axis_min, axis_max = sorted((seg.a.x, seg.b.x))
                distance = abs(coord - cy)
                axis_gap = 0.0 if axis_min - 250 <= cx <= axis_max + 250 else min(abs(cx - axis_min), abs(cx - axis_max))
            else:
                coord = (seg.a.x + seg.b.x) * 0.5
                axis_min, axis_max = sorted((seg.a.y, seg.b.y))
                distance = abs(coord - cx)
                axis_gap = 0.0 if axis_min - 250 <= cy <= axis_max + 250 else min(abs(cy - axis_min), abs(cy - axis_max))
            score = distance + 0.35 * axis_gap
            if distance <= 180.0 and axis_gap <= 600.0:
                line_coords.append((score, coord))
        if not line_coords:
            line_coords = [(180.0, cy if horizontal_text else cx)]
        unique_line_coords: list[tuple[float, float]] = []
        for score, coord in sorted(line_coords):
            if all(abs(coord - existing[1]) > 10.0 for existing in unique_line_coords):
                unique_line_coords.append((score, coord))
            if len(unique_line_coords) >= 3:
                break
        for _, line_coord in unique_line_coords:
            crossings: list[float] = []
            for seg in perpendicular:
                if seg.length < 45.0:
                    continue
                if horizontal_text:
                    x = (seg.a.x + seg.b.x) * 0.5
                    y_min, y_max = sorted((seg.a.y, seg.b.y))
                    if y_min - 45 <= line_coord <= y_max + 45:
                        crossings.append(x)
                else:
                    y = (seg.a.y + seg.b.y) * 0.5
                    x_min, x_max = sorted((seg.a.x, seg.b.x))
                    if x_min - 45 <= line_coord <= x_max + 45:
                        crossings.append(y)
            if len(crossings) < 2:
                continue
            crossings = sorted(_dedupe_scalars(crossings, tol=8.0))
            axis_center = cx if horizontal_text else cy
            below = [v for v in crossings if v < axis_center - 8]
            above = [v for v in crossings if v > axis_center + 8]
            if not below or not above:
                continue
            left = sorted(below, reverse=True)[:4]
            right = sorted(above)[:4]
            for lo in left:
                for hi in right:
                    span = hi - lo
                    if span < 35.0:
                        continue
                    ratio = dim.value_mm / span
                    if 0.05 <= ratio <= 1000.0:
                        proximity = abs(axis_center - lo) + abs(hi - axis_center)
                        candidates.append((ratio, f"{dim.text} / raster span {span:.1f}px (proximity {proximity:.0f})", label_key))
    if not candidates:
        return CalibrationResult(None, 0.0, "unresolved", ("no raster dimension-span scale evidence",))
    tolerance = 0.035
    best_selected: list[tuple[float, str, str]] = []
    for anchor, _, _ in candidates:
        cluster = [c for c in candidates if abs(c[0] - anchor) / max(anchor, 1e-9) <= tolerance]
        by_label: dict[str, tuple[float, str, str]] = {}
        for item in cluster:
            current = by_label.get(item[2])
            if current is None or abs(item[0] - anchor) < abs(current[0] - anchor):
                by_label[item[2]] = item
        selected = list(by_label.values())
        if len(selected) > len(best_selected):
            best_selected = selected
    if len(best_selected) < min_cluster_size:
        return CalibrationResult(None, 0.0, "unresolved", (f"only {len(best_selected)} independent dimension labels agree; need {min_cluster_size}",))
    values = [v[0] for v in best_selected]
    mm_per_unit = median(values)
    spread = max(values) / max(min(values), 1e-9) - 1.0
    confidence = min(0.94, 0.55 + 0.055 * len(best_selected) + max(0.0, 0.16 - spread * 2.0))
    evidence = tuple(v[1] for v in sorted(best_selected, key=lambda x: abs(x[0] - mm_per_unit))[:12])
    return CalibrationResult(mm_per_unit, confidence, "raster_dimension_span_consensus", evidence)


def _dedupe_scalars(values: list[float], tol: float) -> list[float]:
    out: list[float] = []
    for value in sorted(values):
        if not out or abs(value - out[-1]) > tol:
            out.append(value)
        else:
            out[-1] = (out[-1] + value) * 0.5
    return out
