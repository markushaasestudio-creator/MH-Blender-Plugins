from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

THIS_DIR = Path(__file__).resolve().parent
PACKAGE_DIR = THIS_DIR.parent
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))

from analyzer.pdf_vector import analyze_pdf_vector  # type: ignore  # noqa: E402
from analyzer.raster import analyze_raster  # type: ignore  # noqa: E402

SCHEMA_VERSION = "0.1.2"


def _merge_pdf_raster_diagnostics(vector_payload: dict, raster_payload: dict) -> dict:
    vector_kind = str(vector_payload.get("source_kind", ""))
    inherited = [] if vector_kind in {"pdf_raster_image", "pdf_raster_or_empty"} else list(vector_payload.get("warnings", []))
    raster_payload["source_kind"] = "pdf_raster_fallback"
    raster_payload["warnings"] = inherited + list(raster_payload.get("warnings", []))
    raster_payload.setdefault("stats", {})["pdf_vector_segments"] = int(vector_payload.get("stats", {}).get("raw_segments", 0))
    raster_payload["stats"]["pdf_text_chars"] = int(vector_payload.get("stats", {}).get("pdf_text_chars", 0))
    raster_payload["stats"]["embedded_images"] = int(vector_payload.get("stats", {}).get("embedded_images", 0))
    return raster_payload


def analyze(input_path: str, page: int, default_wall_thickness_mm: float) -> dict:
    path = Path(input_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        vector_payload = analyze_pdf_vector(str(path), page_number=page, default_wall_thickness_mm=default_wall_thickness_mm)
        payload = vector_payload
        preview_path = vector_payload.get("preview_path")
        vector_kind = str(vector_payload.get("source_kind", ""))
        if preview_path and (vector_kind in {"pdf_raster_image", "pdf_raster_or_empty"} or not vector_payload.get("wall_hypotheses")):
            try:
                raster_payload = analyze_raster(preview_path, default_wall_thickness_mm)
                vector_conf = float(vector_payload.get("calibration", {}).get("confidence", 0.0))
                raster_conf = float(raster_payload.get("calibration", {}).get("confidence", 0.0))
                if vector_kind in {"pdf_raster_image", "pdf_raster_or_empty"}:
                    payload = _merge_pdf_raster_diagnostics(vector_payload, raster_payload)
                elif raster_conf > vector_conf and (raster_payload.get("wall_hypotheses") or raster_payload.get("dimensions")):
                    payload = _merge_pdf_raster_diagnostics(vector_payload, raster_payload)
            except Exception as exc:
                payload.setdefault("warnings", []).append(f"Raster fallback unavailable: {exc}")
    elif suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
        payload = analyze_raster(str(path), default_wall_thickness_mm)
    else:
        raise ValueError(f"Unsupported floorplan format: {suffix}")
    return {"schema_version": SCHEMA_VERSION, "source": {"path": str(path), "page": page, "kind": payload.pop("source_kind", "unknown")}, **payload}


def main() -> int:
    parser = argparse.ArgumentParser(description="MH Room Builder floorplan analyzer")
    parser.add_argument("--input", required=True)
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--output", required=True)
    parser.add_argument("--default-wall-thickness-mm", type=float, default=120.0)
    args = parser.parse_args()
    try:
        result = analyze(args.input, args.page, args.default_wall_thickness_mm)
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(str(output))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
