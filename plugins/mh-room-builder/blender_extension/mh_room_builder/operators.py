from __future__ import annotations

from pathlib import Path
import json

import bpy
from bpy.types import Operator
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper

from .analyzer_runner import (
    check_ollama_model,
    export_training_label,
    list_ollama_models,
    load_json,
    load_summary,
    render_candidate_preview,
    run_analyzer,
    run_reference_review,
    run_semantic_review,
)
from .domain import AnalysisResult, Point2D, WallCandidate
from .geometry_builder import build_wall_object, clear_generated_walls


def _settings(context):
    return context.scene.mh_room_builder


def _set_warning_fields(settings, messages: list[str]) -> None:
    padded = (messages + ["", "", ""])[:3]
    settings.warning_1, settings.warning_2, settings.warning_3 = padded


def _resolve_user_path(value: str) -> str:
    if value.startswith("//"):
        return bpy.path.abspath(value)
    return str(Path(value).expanduser())


def _current_candidate(settings):
    if not settings.review_candidates:
        return None
    index = max(0, min(settings.review_index, len(settings.review_candidates) - 1))
    settings.review_index = index
    return settings.review_candidates[index]


def _update_review_counts(settings) -> None:
    settings.accepted_candidates = sum(1 for item in settings.review_candidates if item.review_status == "ACCEPTED")
    settings.rejected_candidates = sum(1 for item in settings.review_candidates if item.review_status == "REJECTED")
    settings.ai_reviewed_candidates = sum(1 for item in settings.review_candidates if item.semantic_source not in {"", "none"})
    settings.detected_walls = settings.accepted_candidates


def _existing_review_state(settings) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for item in settings.review_candidates:
        result[item.candidate_id] = {
            "start_x_mm": item.start_x_mm,
            "start_y_mm": item.start_y_mm,
            "end_x_mm": item.end_x_mm,
            "end_y_mm": item.end_y_mm,
            "thickness_mm": item.thickness_mm,
            "semantic_class": item.semantic_class,
            "semantic_confidence": item.semantic_confidence,
            "semantic_source": item.semantic_source,
            "semantic_model": item.semantic_model,
            "semantic_rationale": item.semantic_rationale,
            "structural_boundary": item.structural_boundary,
            "review_status": item.review_status,
            "user_class": item.user_class,
        }
    return result


def _populate_review_candidates(settings, analysis_path: str, preserve_existing: bool = False) -> int:
    data = load_json(analysis_path)
    hypotheses = list(data.get("wall_hypotheses", []))
    hypotheses.sort(key=lambda v: float(v.get("geometry_confidence", 0.0)), reverse=True)
    filtered = [item for item in hypotheses if float(item.get("geometry_confidence", 0.0)) >= float(settings.min_wall_confidence)][: int(settings.review_limit)]

    previous = _existing_review_state(settings) if preserve_existing else {}
    all_x = []
    all_y = []
    for raw in hypotheses:
        for point in (raw.get("start_mm", [0.0, 0.0]), raw.get("end_mm", [0.0, 0.0])):
            all_x.append(float(point[0]))
            all_y.append(float(point[1]))
    origin_x = min(all_x) if all_x else 0.0
    origin_y = max(all_y) if all_y else 0.0
    settings.plan_origin_x_mm = origin_x
    settings.plan_origin_y_mm = origin_y

    settings.review_candidates.clear()
    for raw in filtered:
        item = settings.review_candidates.add()
        item.candidate_id = str(raw.get("id", ""))
        item.source = str(raw.get("source", "unknown"))
        start = raw.get("start_mm", [0.0, 0.0])
        end = raw.get("end_mm", [0.0, 0.0])
        item.start_x_mm = float(start[0]) - origin_x
        item.start_y_mm = float(start[1]) - origin_y
        item.end_x_mm = float(end[0]) - origin_x
        item.end_y_mm = float(end[1]) - origin_y
        item.thickness_mm = float(raw.get("thickness_mm", settings.default_wall_thickness_mm))
        item.geometry_confidence = float(raw.get("geometry_confidence", 0.0))
        semantic = raw.get("semantic", {}) or {}
        semantic_class = str(semantic.get("class", "UNKNOWN")).upper()
        if semantic_class not in {"UNKNOWN", "WALL", "CABINET", "KITCHEN", "FURNITURE", "DOOR", "WINDOW", "COLUMN", "STAIRS", "SANITARY", "DIMENSION", "ANNOTATION"}:
            semantic_class = "UNKNOWN"
        item.semantic_class = semantic_class
        item.semantic_confidence = float(semantic.get("confidence", 0.0))
        item.semantic_source = str(semantic.get("source", "none"))
        item.semantic_model = str(semantic.get("model", ""))
        item.semantic_rationale = str(semantic.get("rationale", ""))[:1024]
        item.structural_boundary = bool(semantic.get("structural_boundary", False))

        old = previous.get(item.candidate_id)
        if old:
            for key, value in old.items():
                setattr(item, key, value)

    settings.review_index = 0
    _update_review_counts(settings)
    return len(filtered)


def _apply_semantic_results(settings, semantic_path: str) -> int:
    payload = load_json(semantic_path)
    by_id = {item.candidate_id: item for item in settings.review_candidates}
    updated = 0
    for raw in payload.get("results", []):
        cid = str(raw.get("candidate_id", ""))
        item = by_id.get(cid)
        if item is None:
            continue
        cls = str(raw.get("class", "UNKNOWN")).upper()
        if cls not in {"UNKNOWN", "WALL", "CABINET", "KITCHEN", "FURNITURE", "DOOR", "WINDOW", "COLUMN", "STAIRS", "SANITARY", "DIMENSION", "ANNOTATION"}:
            cls = "UNKNOWN"
        item.semantic_class = cls
        item.semantic_confidence = max(0.0, min(1.0, float(raw.get("confidence", 0.0))))
        item.semantic_source = "OLLAMA_LOCAL" if not settings.allow_remote_ollama else "OLLAMA"
        item.semantic_model = str(payload.get("model", settings.ollama_model))
        item.semantic_rationale = str(raw.get("rationale", ""))[:1024]
        item.structural_boundary = bool(raw.get("structural_boundary", False))
        updated += 1
    sheets = payload.get("contact_sheets", [])
    settings.semantic_preview_path = str(sheets[-1]) if sheets else ""
    settings.semantic_json_path = semantic_path
    _update_review_counts(settings)
    return updated


def _maybe_log_training(settings, candidate, label: str, operator: Operator) -> None:
    if not settings.log_training_examples or not settings.analysis_json_path or label == "UNKNOWN":
        return
    try:
        dataset = _resolve_user_path(settings.training_dataset_dir)
        export_training_label(
            settings.analyzer_python,
            bpy.path.abspath(settings.analysis_json_path),
            candidate.candidate_id,
            label,
            dataset,
        )
    except Exception as exc:
        operator.report({"WARNING"}, f"Review saved, but training example could not be logged: {exc}")


class MH_OT_analyze_floorplan(Operator):
    bl_idname = "mh_room.analyze_floorplan"
    bl_label = "Analyze Floorplan"
    bl_description = "Analyze drawing lines and dimension evidence without generating final geometry"

    def execute(self, context):
        settings = _settings(context)
        if not settings.floorplan_path:
            self.report({"ERROR"}, "Choose a floorplan first")
            return {"CANCELLED"}
        if not settings.analyzer_python:
            self.report({"ERROR"}, "Set the external Analyzer Python executable first")
            return {"CANCELLED"}

        settings.analysis_status = "Analyzing..."
        _set_warning_fields(settings, [])
        try:
            result_path = run_analyzer(
                settings.analyzer_python,
                bpy.path.abspath(settings.floorplan_path),
                settings.floorplan_page,
                settings.default_wall_thickness_mm,
            )
            summary = load_summary(result_path)
        except Exception as exc:
            settings.analysis_status = "Analysis failed"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        settings.analysis_json_path = str(result_path)
        settings.analysis_source_kind = summary["source_kind"]
        settings.calibration_method = summary["method"]
        settings.calibration_confidence = summary["confidence"]
        settings.calibration_mm_per_unit = summary["mm_per_unit"]
        settings.detected_dimensions = summary["dimensions"]
        settings.raw_wall_hypotheses = summary["raw_wall_hypotheses"]
        settings.raw_segments = summary["raw_segments"]
        settings.merged_segments = summary["merged_segments"]
        settings.warnings_count = summary["warnings"]
        settings.ocr_status = summary["ocr_status"]
        settings.analysis_preview_path = summary["analysis_preview_path"]
        settings.embedded_images = summary["embedded_images"]
        settings.pdf_text_chars = summary["pdf_text_chars"]
        settings.semantic_status = "Not run"
        settings.semantic_json_path = ""
        settings.semantic_preview_path = ""
        _set_warning_fields(settings, summary["warning_messages"])

        loaded = 0
        if summary["confidence"] >= 0.55 and summary["hypotheses"]:
            try:
                loaded = _populate_review_candidates(settings, str(result_path), preserve_existing=False)
            except Exception as exc:
                self.report({"WARNING"}, f"Analysis succeeded but review list could not be loaded: {exc}")

        if summary["confidence"] >= 0.55 and summary["hypotheses"]:
            settings.analysis_status = f"Analysis ready - {loaded} candidates loaded for review"
        elif summary["confidence"] < 0.55:
            settings.analysis_status = "Analysis ready - calibration unresolved"
        else:
            settings.analysis_status = "Analysis ready - no wall hypotheses"

        self.report(
            {"INFO"},
            f"Calibration {summary['confidence']:.0%}; {summary['dimensions']} dimensions; "
            f"{summary['hypotheses']} wall hypotheses; {loaded} loaded for review",
        )
        return {"FINISHED"}


class MH_OT_reload_review_candidates(Operator):
    bl_idname = "mh_room.reload_review_candidates"
    bl_label = "Reload Review Candidates"
    bl_description = "Re-filter hypotheses using the current geometry threshold and candidate limit while preserving review edits where possible"

    def execute(self, context):
        settings = _settings(context)
        if not settings.analysis_json_path:
            self.report({"ERROR"}, "Run analysis first")
            return {"CANCELLED"}
        try:
            count = _populate_review_candidates(settings, bpy.path.abspath(settings.analysis_json_path), preserve_existing=True)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Loaded {count} review candidates")
        return {"FINISHED"}


class MH_OT_open_analysis_preview(Operator):
    bl_idname = "mh_room.open_analysis_preview"
    bl_label = "Open Analysis Preview"
    bl_description = "Open the generated diagnostic overlay in the system viewer"

    def execute(self, context):
        path = Path(bpy.path.abspath(_settings(context).analysis_preview_path))
        if not path.exists():
            self.report({"ERROR"}, f"Preview not found: {path}")
            return {"CANCELLED"}
        bpy.ops.wm.path_open(filepath=str(path))
        return {"FINISHED"}


class MH_OT_detect_ollama_models(Operator):
    bl_idname = "mh_room.detect_ollama_models"
    bl_label = "Detect Ollama Models"
    bl_description = "Query local Ollama, inspect capabilities, and select a vision-capable Qwen model when possible"

    def execute(self, context):
        settings = _settings(context)
        try:
            payload = list_ollama_models(settings.analyzer_python, settings.ollama_endpoint, timeout=30)
        except Exception as exc:
            settings.ollama_status = "Ollama unavailable"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        models = payload.get("models", [])
        vision = [m for m in models if "vision" in [str(v).lower() for v in m.get("capabilities", [])]]
        qwen_vision = [m for m in vision if "qwen" in str(m.get("name", "")).lower()]
        if not settings.ollama_model:
            preferred = qwen_vision[0] if qwen_vision else (vision[0] if vision else None)
            if preferred:
                settings.ollama_model = str(preferred.get("name", ""))
        names = [str(m.get("name", "")) for m in vision[:4]]
        settings.ollama_status = f"Connected - {len(models)} model(s), {len(vision)} vision"
        settings.ollama_capabilities = "Vision models: " + (", ".join(names) if names else "none detected")
        self.report({"INFO"}, settings.ollama_status)
        return {"FINISHED"}


class MH_OT_test_ollama_model(Operator):
    bl_idname = "mh_room.test_ollama_model"
    bl_label = "Test Vision Model"
    bl_description = "Verify the configured Ollama model exists and advertises vision support"

    def execute(self, context):
        settings = _settings(context)
        if not settings.ollama_model:
            self.report({"ERROR"}, "Enter or detect an Ollama model first")
            return {"CANCELLED"}
        try:
            payload = check_ollama_model(settings.analyzer_python, settings.ollama_endpoint, settings.ollama_model, timeout=30)
        except Exception as exc:
            settings.ollama_status = "Model check failed"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        caps = [str(v) for v in payload.get("capabilities", [])]
        settings.ollama_capabilities = ", ".join(caps) if caps else "No capabilities reported"
        if payload.get("vision"):
            settings.ollama_status = "Ready - vision supported"
            self.report({"INFO"}, f"{settings.ollama_model}: vision supported")
            return {"FINISHED"}
        settings.ollama_status = "Model is not vision-capable"
        self.report({"ERROR"}, f"{settings.ollama_model} does not advertise the vision capability")
        return {"CANCELLED"}


class MH_OT_semantic_review_selected(Operator):
    bl_idname = "mh_room.semantic_review_selected"
    bl_label = "AI Review Selected"
    bl_description = "Classify the selected geometric candidate using the configured local Ollama vision model"

    def execute(self, context):
        settings = _settings(context)
        candidate = _current_candidate(settings)
        if candidate is None:
            self.report({"ERROR"}, "No review candidate selected")
            return {"CANCELLED"}
        return _run_ai_review(self, settings, [candidate.candidate_id])


class MH_OT_semantic_review_next(Operator):
    bl_idname = "mh_room.semantic_review_next"
    bl_label = "AI Review Next Batch"
    bl_description = "Classify the strongest unreviewed candidates that have not yet received an AI semantic class"

    def execute(self, context):
        settings = _settings(context)
        candidates = [
            item for item in settings.review_candidates
            if item.review_status == "UNREVIEWED" and item.semantic_source in {"", "none"}
        ]
        candidates.sort(key=lambda item: item.geometry_confidence, reverse=True)
        ids = [item.candidate_id for item in candidates[: settings.semantic_candidate_count]]
        if not ids:
            self.report({"INFO"}, "No unreviewed candidates are waiting for AI classification")
            return {"CANCELLED"}
        return _run_ai_review(self, settings, ids)


def _run_ai_review(operator: Operator, settings, candidate_ids: list[str]):
    if not settings.analysis_json_path:
        operator.report({"ERROR"}, "Run floorplan analysis first")
        return {"CANCELLED"}
    if not settings.ollama_model:
        operator.report({"ERROR"}, "Configure an Ollama vision model first")
        return {"CANCELLED"}
    settings.semantic_status = f"Running local AI review for {len(candidate_ids)} candidate(s)..."
    try:
        output = run_semantic_review(
            settings.analyzer_python,
            bpy.path.abspath(settings.analysis_json_path),
            settings.ollama_endpoint,
            settings.ollama_model,
            candidate_ids,
            batch_size=settings.semantic_contact_batch_size,
            timeout=settings.semantic_timeout_seconds,
            allow_remote=settings.allow_remote_ollama,
            include_overview=settings.semantic_include_overview,
        )
        updated = _apply_semantic_results(settings, str(output))
    except Exception as exc:
        settings.semantic_status = "AI review failed"
        operator.report({"ERROR"}, str(exc))
        return {"CANCELLED"}
    settings.semantic_status = f"AI review ready - {updated} candidate(s) classified"
    operator.report({"INFO"}, settings.semantic_status)
    return {"FINISHED"}


class MH_OT_open_semantic_preview(Operator):
    bl_idname = "mh_room.open_semantic_preview"
    bl_label = "Open Last AI Contact Sheet"

    def execute(self, context):
        path = Path(bpy.path.abspath(_settings(context).semantic_preview_path))
        if not path.exists():
            self.report({"ERROR"}, f"Semantic preview not found: {path}")
            return {"CANCELLED"}
        bpy.ops.wm.path_open(filepath=str(path))
        return {"FINISHED"}


class MH_OT_open_candidate_preview(Operator):
    bl_idname = "mh_room.open_candidate_preview"
    bl_label = "Open Selected Candidate Crop"
    bl_description = "Render and open a context crop for the selected wall hypothesis; no AI is required"

    def execute(self, context):
        settings = _settings(context)
        item = _current_candidate(settings)
        if item is None or not settings.analysis_json_path:
            self.report({"ERROR"}, "Select a review candidate first")
            return {"CANCELLED"}
        try:
            preview = render_candidate_preview(
                settings.analyzer_python,
                bpy.path.abspath(settings.analysis_json_path),
                item.candidate_id,
            )
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        settings.candidate_preview_path = str(preview)
        bpy.ops.wm.path_open(filepath=str(preview))
        return {"FINISHED"}


class MH_OT_accept_candidate(Operator):
    bl_idname = "mh_room.accept_candidate"
    bl_label = "Accept as Wall"
    bl_description = "Human-verifies the selected candidate as a buildable wall"

    def execute(self, context):
        settings = _settings(context)
        item = _current_candidate(settings)
        if item is None:
            return {"CANCELLED"}
        item.review_status = "ACCEPTED"
        item.user_class = "WALL"
        _update_review_counts(settings)
        _maybe_log_training(settings, item, "WALL", self)
        return {"FINISHED"}


class MH_OT_reject_candidate(Operator):
    bl_idname = "mh_room.reject_candidate"
    bl_label = "Reject as Wall"
    bl_description = "Human-rejects the selected candidate as wall geometry; optionally preserve a semantic class for training"

    def execute(self, context):
        settings = _settings(context)
        item = _current_candidate(settings)
        if item is None:
            return {"CANCELLED"}
        if item.user_class == "WALL":
            item.user_class = "UNKNOWN"
        if item.user_class == "UNKNOWN" and item.semantic_class not in {"UNKNOWN", "WALL"}:
            item.user_class = item.semantic_class
        item.review_status = "REJECTED"
        _update_review_counts(settings)
        _maybe_log_training(settings, item, item.user_class, self)
        return {"FINISHED"}


class MH_OT_apply_candidate_class(Operator):
    bl_idname = "mh_room.apply_candidate_class"
    bl_label = "Apply Human Class"
    bl_description = "Apply the selected human semantic class; WALL becomes accepted, all other known classes become rejected as wall geometry"

    def execute(self, context):
        settings = _settings(context)
        item = _current_candidate(settings)
        if item is None:
            return {"CANCELLED"}
        if item.user_class == "UNKNOWN":
            self.report({"WARNING"}, "Choose a human class first")
            return {"CANCELLED"}
        item.review_status = "ACCEPTED" if item.user_class == "WALL" else "REJECTED"
        _update_review_counts(settings)
        _maybe_log_training(settings, item, item.user_class, self)
        return {"FINISHED"}


class MH_OT_reset_candidate_review(Operator):
    bl_idname = "mh_room.reset_candidate_review"
    bl_label = "Reset Review"

    def execute(self, context):
        settings = _settings(context)
        item = _current_candidate(settings)
        if item is None:
            return {"CANCELLED"}
        item.review_status = "UNREVIEWED"
        item.user_class = "UNKNOWN"
        _update_review_counts(settings)
        return {"FINISHED"}


class MH_OT_build_walls(Operator):
    bl_idname = "mh_room.build_walls"
    bl_label = "Build Accepted Walls"
    bl_description = "Build only human-accepted wall candidates as clean quad prisms"

    def execute(self, context):
        settings = _settings(context)
        if not settings.analysis_json_path:
            self.report({"ERROR"}, "Run floorplan analysis first")
            return {"CANCELLED"}
        if settings.calibration_confidence < 0.55 or settings.calibration_mm_per_unit <= 0:
            self.report({"ERROR"}, "Calibration is unresolved or too weak; refusing to build geometry")
            return {"CANCELLED"}

        accepted = [item for item in settings.review_candidates if item.review_status == "ACCEPTED"]
        if not accepted:
            self.report({"WARNING"}, "No human-accepted wall candidates are available")
            return {"CANCELLED"}

        clear_generated_walls()
        try:
            for item in accepted:
                wall = WallCandidate(
                    id=f"W_{item.candidate_id}",
                    start=Point2D(item.start_x_mm, item.start_y_mm),
                    end=Point2D(item.end_x_mm, item.end_y_mm),
                    thickness_mm=item.thickness_mm,
                    confidence=item.geometry_confidence,
                    source=f"human_verified:{item.source}",
                    evidence=[
                        f"human review accepted {item.candidate_id}",
                        f"AI class {item.semantic_class} score {item.semantic_confidence:.3f}" if item.semantic_source not in {"", "none"} else "no AI semantic evidence",
                    ],
                )
                obj = build_wall_object(wall, settings.ceiling_height_mm)
                obj["mh_review_status"] = "ACCEPTED"
                obj["mh_human_class"] = item.user_class
                obj["mh_semantic_class"] = item.semantic_class
                obj["mh_semantic_score"] = float(item.semantic_confidence)
                obj["mh_semantic_source"] = item.semantic_source
                obj["mh_candidate_id"] = item.candidate_id
        except Exception as exc:
            clear_generated_walls()
            self.report({"ERROR"}, f"Geometry build aborted: {exc}")
            return {"CANCELLED"}

        context.scene.unit_settings.system = "METRIC"
        context.scene.unit_settings.length_unit = "MILLIMETERS"
        self.report({"INFO"}, f"Built {len(accepted)} human-verified clean wall objects")
        return {"FINISHED"}


class MH_OT_clear_walls(Operator):
    bl_idname = "mh_room.clear_walls"
    bl_label = "Clear Generated Walls"
    bl_description = "Remove generated wall objects; source analysis and reviews remain untouched"

    def execute(self, context):
        count = clear_generated_walls()
        self.report({"INFO"}, f"Removed {count} wall objects")
        return {"FINISHED"}


class MH_OT_add_reference(Operator, ImportHelper):
    bl_idname = "mh_room.add_reference"
    bl_label = "Add Reference Image"
    bl_description = "Register a customer rendering as non-authoritative architectural evidence"

    filter_glob: StringProperty(default="*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.webp", options={"HIDDEN"})

    def execute(self, context):
        item = _settings(context).references.add()
        item.path = self.filepath
        item.name = Path(self.filepath).name
        _settings(context).reference_index = len(_settings(context).references) - 1
        return {"FINISHED"}


class MH_OT_remove_reference(Operator):
    bl_idname = "mh_room.remove_reference"
    bl_label = "Remove Reference Image"

    def execute(self, context):
        settings = _settings(context)
        if not settings.references:
            return {"CANCELLED"}
        index = min(settings.reference_index, len(settings.references) - 1)
        settings.references.remove(index)
        settings.reference_index = max(0, min(index, len(settings.references) - 1))
        return {"FINISHED"}


class MH_OT_analyze_reference_ai(Operator):
    bl_idname = "mh_room.analyze_reference_ai"
    bl_label = "Analyze Reference with Local AI"
    bl_description = "Use the configured Ollama vision model for qualitative architectural observations only"

    def execute(self, context):
        settings = _settings(context)
        if not settings.references or settings.reference_index >= len(settings.references):
            self.report({"ERROR"}, "Select a reference rendering first")
            return {"CANCELLED"}
        if not settings.ollama_model:
            self.report({"ERROR"}, "Configure an Ollama vision model first")
            return {"CANCELLED"}
        item = settings.references[settings.reference_index]
        image_path = bpy.path.abspath(item.path)
        item.ai_status = "Analyzing..."
        try:
            output = run_reference_review(
                settings.analyzer_python,
                image_path,
                settings.ollama_endpoint,
                settings.ollama_model,
                timeout=settings.semantic_timeout_seconds,
                allow_remote=settings.allow_remote_ollama,
            )
            payload = json.loads(Path(output).read_text(encoding="utf-8"))
        except Exception as exc:
            item.ai_status = "AI analysis failed"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        item.ai_json_path = str(output)
        item.ai_model = settings.ollama_model
        item.ai_summary = str(payload.get("summary", ""))[:2048]
        item.ai_elements_count = len(payload.get("architectural_elements", []))
        item.ai_status = f"Ready - {item.ai_elements_count} element(s) observed"
        self.report({"INFO"}, item.ai_status)
        return {"FINISHED"}


class MH_OT_open_reference_ai_result(Operator):
    bl_idname = "mh_room.open_reference_ai_result"
    bl_label = "Open Reference AI Result"

    def execute(self, context):
        settings = _settings(context)
        if not settings.references or settings.reference_index >= len(settings.references):
            return {"CANCELLED"}
        path = Path(bpy.path.abspath(settings.references[settings.reference_index].ai_json_path))
        if not path.exists():
            self.report({"ERROR"}, "Reference AI result not found")
            return {"CANCELLED"}
        bpy.ops.wm.path_open(filepath=str(path))
        return {"FINISHED"}
