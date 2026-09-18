from __future__ import annotations

from pathlib import Path
import os
import shutil
import tempfile
from typing import Any

from .calibration import TextDimension, infer_raster_calibration_from_dimension_spans
from .dimensions import parse_dimension
from .geometry2d import P2, Segment, infer_wall_pairs, merge_collinear_segments
from .hypotheses import serialize_wall_hypotheses


def _imports():
    missing: list[str] = []
    try:
        import cv2  # type: ignore
    except ImportError:
        cv2 = None
        missing.append("opencv-python-headless")
    try:
        import pytesseract  # type: ignore
    except ImportError:
        pytesseract = None
        missing.append("pytesseract")
    if missing:
        raise RuntimeError("Raster analysis requires: " + ", ".join(missing))
    return cv2, pytesseract


def _configure_tesseract(pytesseract) -> tuple[bool, str]:
    candidates: list[str] = []
    env_cmd = os.environ.get("TESSERACT_CMD")
    if env_cmd:
        candidates.append(env_cmd)
    found = shutil.which("tesseract")
    if found:
        candidates.append(found)
    if os.name == "nt":
        candidates.extend([r"C:\Program Files\Tesseract-OCR\tesseract.exe", r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"])
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            pytesseract.pytesseract.tesseract_cmd = str(candidate)
            return True, str(candidate)
    return False, "Tesseract executable not found"


def _detect_lines(gray, cv2) -> list[Segment]:
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blur, 50, 160, apertureSize=3)
    h, w = gray.shape[:2]
    min_len = max(30, int(min(h, w) * 0.018))
    lines = cv2.HoughLinesP(edges, 1, 3.141592653589793 / 360.0, threshold=45, minLineLength=min_len, maxLineGap=max(6, int(min(h, w) * 0.004)))
    out: list[Segment] = []
    if lines is None:
        return out
    for raw in lines[:, 0, :]:
        x1, y1, x2, y2 = (float(v) for v in raw)
        out.append(Segment(P2(x1, y1), P2(x2, y2), "raster_hough"))
    return out


def _remove_long_lines(gray, cv2):
    bw = cv2.threshold(gray, 210, 255, cv2.THRESH_BINARY)[1]
    inv = 255 - bw
    h, w = gray.shape[:2]
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(55, int(w * 0.010)), 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(55, int(h * 0.010))))
    horizontal = cv2.morphologyEx(inv, cv2.MORPH_OPEN, horizontal_kernel)
    vertical = cv2.morphologyEx(inv, cv2.MORPH_OPEN, vertical_kernel)
    lines = cv2.max(horizontal, vertical)
    cleaned_inv = cv2.subtract(inv, lines)
    return 255 - cleaned_inv


def _bbox_from_rotated_ccw(bbox: tuple[float, float, float, float], original_width: int) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = bbox
    corners = [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]
    mapped = [(original_width - 1.0 - yr, xr) for xr, yr in corners]
    xs = [p[0] for p in mapped]; ys = [p[1] for p in mapped]
    return (min(xs), min(ys), max(xs), max(ys))


def _ocr_words(image, pytesseract) -> list[dict[str, Any]]:
    data = pytesseract.image_to_data(image, config="--psm 11", output_type=pytesseract.Output.DICT)
    words: list[dict[str, Any]] = []
    count = len(data.get("text", []))
    for i in range(count):
        text = str(data["text"][i]).strip()
        if not text:
            continue
        try:
            confidence = max(0.0, min(1.0, float(data.get("conf", [0] * count)[i]) / 100.0))
        except Exception:
            confidence = 0.0
        if confidence < 0.12:
            continue
        x = float(data["left"][i]); y = float(data["top"][i]); w = float(data["width"][i]); h = float(data["height"][i])
        words.append({"text": text, "confidence": confidence, "bbox": (x, y, x + w, y + h)})
    return words


def _phrase_candidates(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    phrases = list(words)
    sorted_words = sorted(words, key=lambda w: (((w["bbox"][1] + w["bbox"][3]) * 0.5), w["bbox"][0]))
    for i, first in enumerate(sorted_words):
        fbox = first["bbox"]; fcy = (fbox[1] + fbox[3]) * 0.5; fheight = max(1.0, fbox[3] - fbox[1])
        current = [first]; last_x = fbox[2]
        for second in sorted_words[i + 1 : i + 4]:
            sbox = second["bbox"]; scy = (sbox[1] + sbox[3]) * 0.5; sheight = max(1.0, sbox[3] - sbox[1]); gap = sbox[0] - last_x
            if abs(scy - fcy) > max(fheight, sheight) * 0.65 or gap < -5 or gap > max(140.0, fheight * 5.0):
                break
            current.append(second); last_x = sbox[2]
            if len(current) >= 2:
                bbox = (min(v["bbox"][0] for v in current), min(v["bbox"][1] for v in current), max(v["bbox"][2] for v in current), max(v["bbox"][3] for v in current))
                phrases.append({"text": " ".join(v["text"] for v in current), "confidence": sum(v["confidence"] for v in current) / len(current), "bbox": bbox})
    return phrases


def _extract_parsed_dimensions(image, pytesseract, direction: tuple[float, float], bbox_transform=None) -> list[TextDimension]:
    dimensions: list[TextDimension] = []
    words = _ocr_words(image, pytesseract)
    for item in _phrase_candidates(words):
        parsed = parse_dimension(item["text"])
        if parsed is None:
            continue
        bbox = item["bbox"]
        if bbox_transform is not None:
            bbox = bbox_transform(bbox)
        dimensions.append(TextDimension(text=item["text"], value_mm=parsed.value_mm, bbox=tuple(float(v) for v in bbox), confidence=float(item["confidence"]) * parsed.confidence, interpretation=parsed.interpretation, direction=direction))
    return dimensions


def _dedupe_dimensions(dimensions: list[TextDimension]) -> list[TextDimension]:
    kept: list[TextDimension] = []
    for dim in sorted(dimensions, key=lambda d: d.confidence, reverse=True):
        x0, y0, x1, y1 = dim.bbox; cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
        duplicate = False
        for existing in kept:
            if abs(existing.value_mm - dim.value_mm) > max(5.0, dim.value_mm * 0.002):
                continue
            ex0, ey0, ex1, ey1 = existing.bbox; ecx, ecy = (ex0 + ex1) * 0.5, (ey0 + ey1) * 0.5
            if (cx - ecx) ** 2 + (cy - ecy) ** 2 <= 90.0 ** 2:
                duplicate = True; break
        if not duplicate:
            kept.append(dim)
    return kept


def _ocr_dimensions(gray, cv2, pytesseract) -> tuple[list[TextDimension], list[str], str]:
    warnings: list[str] = []
    available, engine_status = _configure_tesseract(pytesseract)
    if not available:
        warnings.append("Raster OCR is unavailable because no Tesseract executable was found. Install Tesseract OCR or set TESSERACT_CMD.")
        return [], warnings, engine_status
    clean = _remove_long_lines(gray, cv2)
    dimensions: list[TextDimension] = []
    try:
        dimensions.extend(_extract_parsed_dimensions(clean, pytesseract, (1.0, 0.0)))
        rotated = cv2.rotate(clean, cv2.ROTATE_90_COUNTERCLOCKWISE)
        width = gray.shape[1]
        dimensions.extend(_extract_parsed_dimensions(rotated, pytesseract, (0.0, 1.0), bbox_transform=lambda bbox: _bbox_from_rotated_ccw(bbox, width)))
    except Exception as exc:
        warnings.append(f"OCR could not run: {exc}")
        return [], warnings, engine_status
    return _dedupe_dimensions(dimensions), warnings, engine_status


def _debug_preview(image, segments: list[Segment], dimensions: list[TextDimension], walls: list[dict], calibration, cv2, stem: str) -> str:
    canvas = image.copy(); h, w = canvas.shape[:2]; scale = min(1.0, 2600.0 / max(h, w))
    for seg in segments:
        if seg.length < max(h, w) * 0.012:
            continue
        cv2.line(canvas, (int(seg.a.x), int(seg.a.y)), (int(seg.b.x), int(seg.b.y)), (185, 185, 185), 1)
    for dim in dimensions:
        x0, y0, x1, y1 = (int(v) for v in dim.bbox)
        cv2.rectangle(canvas, (x0, y0), (x1, y1), (255, 120, 0), 2)
        cv2.putText(canvas, dim.text[:36], (x0, max(16, y0 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 120, 0), 1, cv2.LINE_AA)
    if calibration.mm_per_unit:
        for wall in walls:
            a = wall["start_px"]; b = wall["end_px"]
            cv2.line(canvas, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), (0, 190, 255), 3)
    status = (f"Calibration: {calibration.method} | {calibration.confidence:.0%} | {calibration.mm_per_unit:.4f} mm/px" if calibration.mm_per_unit else "Calibration: unresolved")
    cv2.rectangle(canvas, (16, 14), (min(w - 16, 980), 64), (255, 255, 255), -1)
    cv2.putText(canvas, status, (28, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (0, 0, 220) if not calibration.mm_per_unit else (0, 120, 0), 2, cv2.LINE_AA)
    if scale < 1.0:
        canvas = cv2.resize(canvas, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    out_dir = Path(tempfile.gettempdir()) / "mh_room_builder"; out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f"{stem}_analysis_preview.png"; cv2.imwrite(str(output), canvas)
    return str(output)


def analyze_raster(input_path: str, default_wall_thickness_mm: float) -> dict:
    cv2, pytesseract = _imports()
    path = Path(input_path)
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Could not open image: {path}")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    raw_segments = _detect_lines(gray, cv2)
    segments = merge_collinear_segments(raw_segments, angle_tol_deg=1.2, offset_tol=3.0, gap_tol=10.0)
    dimensions, warnings, ocr_status = _ocr_dimensions(gray, cv2, pytesseract)
    calibration = infer_raster_calibration_from_dimension_spans(dimensions, segments, min_cluster_size=3)
    if calibration.mm_per_unit is None:
        warnings.append("Raster plan has no trustworthy dimension-to-pixel calibration yet. The plan is kept as evidence, but no final walls are generated.")
        wall_candidates: list[dict] = []
    else:
        wall_candidates = infer_wall_pairs(segments, mm_per_unit=calibration.mm_per_unit, default_thickness_mm=default_wall_thickness_mm)
    walls: list[dict] = []
    wall_hypotheses = serialize_wall_hypotheses(wall_candidates, calibration.mm_per_unit or 0.0, prefix="R")
    debug_walls: list[dict] = []
    for candidate in wall_candidates:
        start: P2 = candidate["start"]; end: P2 = candidate["end"]
        debug_walls.append({"start_px": [start.x, start.y], "end_px": [end.x, end.y]})
    if wall_candidates:
        warnings.append(f"{len(wall_candidates)} geometric wall hypotheses were found. They remain review-only until manually accepted; local AI may rank/classify them but cannot authorize geometry.")
    debug_preview_path = _debug_preview(image, segments, dimensions, debug_walls, calibration, cv2, path.stem)
    return {
        "source_kind": "raster",
        "calibration": {"mm_per_source_unit": calibration.mm_per_unit, "confidence": calibration.confidence, "method": calibration.method, "evidence": list(calibration.evidence)},
        "dimensions": [{"text": item.text, "value_mm": item.value_mm, "bbox_source": list(item.bbox), "confidence": item.confidence, "unit_interpretation": item.interpretation, "direction": list(item.direction)} for item in dimensions],
        "walls": walls,
        "wall_hypotheses": wall_hypotheses,
        "warnings": warnings,
        "preview_path": str(path),
        "analysis_preview_path": debug_preview_path,
        "stats": {"image_width_px": int(image.shape[1]), "image_height_px": int(image.shape[0]), "preview_scale_from_source": 1.0, "raw_segments": len(raw_segments), "merged_segments": len(segments), "dimension_labels": len(dimensions), "wall_candidates": len(walls), "raw_wall_hypotheses": len(wall_candidates), "ocr_status": ocr_status},
    }
