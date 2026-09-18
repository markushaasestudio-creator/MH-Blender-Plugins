from __future__ import annotations

from pathlib import Path
import hashlib
import json
import subprocess
import tempfile
from typing import Any


def analyzer_script_path() -> Path:
    return Path(__file__).resolve().parent / "analyzer" / "analyze.py"


def semantic_script_path() -> Path:
    return Path(__file__).resolve().parent / "analyzer" / "semantic_review.py"


def analysis_output_path(floorplan_path: str, page: int) -> Path:
    source = Path(floorplan_path)
    digest = hashlib.sha1(f"{source.resolve()}::{page}".encode("utf-8")).hexdigest()[:10]
    root = Path(tempfile.gettempdir()) / "mh_room_builder"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{source.stem}_p{page}_{digest}.json"


def semantic_output_path(analysis_path: str | Path, model: str) -> Path:
    source = Path(analysis_path)
    safe_model = "".join(ch if ch.isalnum() else "_" for ch in model)[:42] or "model"
    return source.with_name(f"{source.stem}_semantic_{safe_model}.json")


def reference_output_path(image_path: str | Path, model: str) -> Path:
    source = Path(image_path)
    safe_model = "".join(ch if ch.isalnum() else "_" for ch in model)[:42] or "model"
    root = Path(tempfile.gettempdir()) / "mh_room_builder" / "references"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{source.stem}_semantic_{safe_model}.json"


def _validate_runtime(python_executable: str, script_path: Path) -> tuple[Path, Path]:
    python_path = Path(python_executable).expanduser()
    if not python_path.exists():
        raise FileNotFoundError(f"Analyzer Python not found: {python_path}")
    if not script_path.exists():
        raise FileNotFoundError(f"Analyzer script not found: {script_path}")
    return python_path, script_path


def _run(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "Unknown external analyzer error").strip()
        raise RuntimeError(stderr)
    return completed


def run_analyzer(python_executable: str, floorplan_path: str, page: int, default_wall_thickness_mm: float) -> Path:
    python_path, script_path = _validate_runtime(python_executable, analyzer_script_path())
    source_path = Path(floorplan_path).expanduser()
    if not source_path.exists():
        raise FileNotFoundError(f"Floorplan not found: {source_path}")
    output_path = analysis_output_path(str(source_path), page)
    command = [str(python_path), str(script_path), "--input", str(source_path), "--page", str(page), "--output", str(output_path), "--default-wall-thickness-mm", str(default_wall_thickness_mm)]
    _run(command, timeout=300)
    if not output_path.exists():
        raise RuntimeError("Analyzer completed without creating an analysis JSON file")
    return output_path


def _run_semantic_command(python_executable: str, args: list[str], timeout: int) -> dict[str, Any]:
    python_path, script_path = _validate_runtime(python_executable, semantic_script_path())
    completed = _run([str(python_path), str(script_path), *args], timeout=timeout)
    stdout = (completed.stdout or "").strip().splitlines()
    if not stdout:
        return {}
    try:
        return json.loads(stdout[-1])
    except json.JSONDecodeError:
        return {"message": stdout[-1]}


def list_ollama_models(python_executable: str, endpoint: str, timeout: int = 30) -> dict[str, Any]:
    return _run_semantic_command(python_executable, ["list", "--endpoint", endpoint, "--timeout", str(timeout)], timeout=max(40, timeout + 10))


def check_ollama_model(python_executable: str, endpoint: str, model: str, timeout: int = 30) -> dict[str, Any]:
    return _run_semantic_command(python_executable, ["check", "--endpoint", endpoint, "--model", model, "--timeout", str(timeout)], timeout=max(40, timeout + 10))


def run_semantic_review(python_executable: str, analysis_path: str, endpoint: str, model: str, candidate_ids: list[str], *, batch_size: int = 6, timeout: int = 240, allow_remote: bool = False, include_overview: bool = False) -> Path:
    if not candidate_ids:
        raise ValueError("No candidate IDs selected for semantic review")
    output = semantic_output_path(analysis_path, model)
    args = ["review", "--analysis", analysis_path, "--endpoint", endpoint, "--model", model, "--candidate-ids", ",".join(candidate_ids), "--output", str(output), "--batch-size", str(max(1, batch_size)), "--timeout", str(timeout)]
    if allow_remote:
        args.append("--allow-remote")
    if include_overview:
        args.append("--include-overview")
    _run_semantic_command(python_executable, args, timeout=max(timeout * max(1, (len(candidate_ids) + batch_size - 1) // batch_size) + 60, 300))
    if not output.exists():
        raise RuntimeError("Semantic reviewer completed without output JSON")
    return output


def run_reference_review(python_executable: str, image_path: str, endpoint: str, model: str, *, timeout: int = 240, allow_remote: bool = False) -> Path:
    output = reference_output_path(image_path, model)
    args = ["reference", "--image", image_path, "--endpoint", endpoint, "--model", model, "--output", str(output), "--timeout", str(timeout)]
    if allow_remote:
        args.append("--allow-remote")
    _run_semantic_command(python_executable, args, timeout=max(timeout + 60, 300))
    if not output.exists():
        raise RuntimeError("Reference semantic reviewer completed without output JSON")
    return output


def render_candidate_preview(python_executable: str, analysis_path: str, candidate_id: str) -> Path:
    root = Path(tempfile.gettempdir()) / "mh_room_builder" / "review"
    root.mkdir(parents=True, exist_ok=True)
    output = root / f"{Path(analysis_path).stem}_{candidate_id}_preview.png"
    _run_semantic_command(python_executable, ["preview", "--analysis", analysis_path, "--candidate-id", candidate_id, "--output", str(output)], timeout=90)
    if not output.exists():
        raise RuntimeError("Candidate preview was not created")
    return output


def export_training_label(python_executable: str, analysis_path: str, candidate_id: str, label: str, dataset_dir: str) -> dict[str, Any]:
    return _run_semantic_command(python_executable, ["export-label", "--analysis", analysis_path, "--candidate-id", candidate_id, "--label", label, "--dataset-dir", dataset_dir], timeout=90)


def load_summary(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    calibration = data.get("calibration", {}); stats = data.get("stats", {}); warnings = [str(v) for v in data.get("warnings", [])]; hypotheses = data.get("wall_hypotheses", [])
    return {"source_kind": str(data.get("source", {}).get("kind", "unknown")), "method": calibration.get("method", "unresolved"), "confidence": float(calibration.get("confidence", 0.0)), "mm_per_unit": float(calibration.get("mm_per_source_unit") or 0.0), "dimensions": len(data.get("dimensions", [])), "walls": len(data.get("walls", [])), "hypotheses": len(hypotheses), "warnings": len(warnings), "warning_messages": warnings, "raw_segments": int(stats.get("raw_segments", 0)), "merged_segments": int(stats.get("merged_segments", 0)), "raw_wall_hypotheses": int(stats.get("raw_wall_hypotheses", len(hypotheses))), "ocr_status": str(stats.get("ocr_status", "not used")), "analysis_preview_path": str(data.get("analysis_preview_path") or ""), "preview_path": str(data.get("preview_path") or ""), "embedded_images": int(stats.get("embedded_images", 0)), "pdf_text_chars": int(stats.get("pdf_text_chars", 0))}


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
