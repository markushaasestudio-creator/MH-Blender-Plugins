from __future__ import annotations

import bpy
from bpy.types import Panel, UIList


_SOURCE_LABELS = {
    "pdf_vector": "Vector PDF",
    "pdf_raster_fallback": "Raster / image PDF",
    "pdf_raster_image": "Raster / image PDF",
    "raster": "Raster image",
    "unknown": "Unknown",
}

_STATUS_ICONS = {
    "ACCEPTED": "CHECKMARK",
    "REJECTED": "X",
    "UNREVIEWED": "QUESTION",
}


class MH_UL_references(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text=item.name or "Reference", icon="IMAGE_DATA")
        row.label(text=item.kind.replace("_", " ").title())


class MH_UL_wall_review(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text=item.candidate_id, icon=_STATUS_ICONS.get(item.review_status, "QUESTION"))
        row.label(text=f"G {item.geometry_confidence:.2f}")
        if item.semantic_source not in {"", "none"}:
            row.label(text=f"AI {item.semantic_class} {item.semantic_confidence:.2f}")
        else:
            row.label(text="AI -")


class MH_PT_room_builder(Panel):
    bl_label = "MH Room Builder v0.1.2"
    bl_idname = "MH_PT_room_builder"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MH Room"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.mh_room_builder

        input_box = layout.box()
        input_box.label(text="1. Floorplan", icon="DOCUMENTS")
        input_box.prop(settings, "floorplan_path")
        if settings.floorplan_path.lower().endswith(".pdf"):
            input_box.prop(settings, "floorplan_page")
        input_box.prop(settings, "analyzer_python")

        geometry_box = layout.box()
        geometry_box.label(text="2. Authoritative room values", icon="DRIVER_DISTANCE")
        geometry_box.prop(settings, "ceiling_height_mm")
        geometry_box.prop(settings, "default_wall_thickness_mm")
        geometry_box.label(text="Ceiling height remains manual project truth.")

        analysis_box = layout.box()
        analysis_box.label(text="3. Floorplan analysis", icon="VIEWZOOM")
        analysis_box.operator("mh_room.analyze_floorplan", icon="FILE_REFRESH")
        analysis_box.label(text=f"Status: {settings.analysis_status}")
        if settings.analysis_json_path:
            analysis_box.separator()
            analysis_box.label(text=f"Source: {_SOURCE_LABELS.get(settings.analysis_source_kind, settings.analysis_source_kind)}")
            if settings.analysis_source_kind.startswith("pdf_raster") or settings.analysis_source_kind == "raster":
                ocr_ready = bool(settings.ocr_status and "not found" not in settings.ocr_status.lower())
                analysis_box.label(text=f"OCR: {'ready' if ocr_ready else 'not available'}", icon="CHECKMARK" if ocr_ready else "ERROR")
            analysis_box.label(text=f"Calibration: {settings.calibration_method}")
            analysis_box.label(text=f"Calibration confidence: {settings.calibration_confidence:.0%}")
            if settings.calibration_mm_per_unit:
                analysis_box.label(text=f"Scale: {settings.calibration_mm_per_unit:.4f} mm/source unit")
            analysis_box.label(text=f"Dimension labels: {settings.detected_dimensions}")
            analysis_box.label(text=f"Line segments: {settings.merged_segments} merged / {settings.raw_segments} raw")
            analysis_box.label(text=f"Raw wall hypotheses: {settings.raw_wall_hypotheses}")
            if settings.analysis_preview_path:
                analysis_box.operator("mh_room.open_analysis_preview", icon="IMAGE_DATA")
            if settings.warnings_count:
                warn_box = analysis_box.box()
                warn_box.label(text=f"Warnings: {settings.warnings_count}", icon="ERROR")
                for message in (settings.warning_1, settings.warning_2, settings.warning_3):
                    if message:
                        shown = message if len(message) <= 105 else message[:102] + "..."
                        warn_box.label(text=shown)

        ai_box = layout.box()
        ai_box.label(text="4. Local semantic AI / Ollama", icon="OUTLINER_OB_LIGHT")
        ai_box.prop(settings, "ollama_endpoint")
        ai_box.prop(settings, "ollama_model")
        row = ai_box.row(align=True)
        row.operator("mh_room.detect_ollama_models", text="Detect Models", icon="FILE_REFRESH")
        row.operator("mh_room.test_ollama_model", text="Test Model", icon="CHECKMARK")
        ai_box.label(text=f"Status: {settings.ollama_status}")
        if settings.ollama_capabilities:
            shown = settings.ollama_capabilities if len(settings.ollama_capabilities) < 110 else settings.ollama_capabilities[:107] + "..."
            ai_box.label(text=shown)
        ai_box.prop(settings, "allow_remote_ollama")
        if not settings.allow_remote_ollama:
            ai_box.label(text="Local-only safety gate active: customer images stay on this machine.", icon="LOCKED")
        col = ai_box.column(align=True)
        col.prop(settings, "semantic_candidate_count")
        col.prop(settings, "semantic_contact_batch_size")
        col.prop(settings, "semantic_include_overview")
        col.prop(settings, "semantic_timeout_seconds")
        row = ai_box.row(align=True)
        row.enabled = bool(settings.review_candidates and settings.ollama_model)
        row.operator("mh_room.semantic_review_next", text="AI Review Next Batch", icon="VIEWZOOM")
        row.operator("mh_room.semantic_review_selected", text="AI Review Selected")
        ai_box.label(text=f"Semantic status: {settings.semantic_status}")
        if settings.semantic_preview_path:
            ai_box.operator("mh_room.open_semantic_preview", icon="IMAGE_DATA")
        ai_box.label(text="AI classifies evidence only; it never authorizes geometry.")

        review_box = layout.box()
        review_box.label(text="5. Wall review", icon="GREASEPENCIL")
        row = review_box.row(align=True)
        row.prop(settings, "min_wall_confidence")
        row.prop(settings, "review_limit")
        review_box.operator("mh_room.reload_review_candidates", icon="FILE_REFRESH")
        review_box.label(
            text=f"Loaded {len(settings.review_candidates)} | Accepted {settings.accepted_candidates} | "
                 f"Rejected {settings.rejected_candidates} | AI {settings.ai_reviewed_candidates}"
        )
        review_box.template_list("MH_UL_wall_review", "", settings, "review_candidates", settings, "review_index", rows=7)

        if settings.review_candidates and settings.review_index < len(settings.review_candidates):
            item = settings.review_candidates[settings.review_index]
            detail = review_box.box()
            detail.label(text=f"Candidate {item.candidate_id} - {item.review_status}")
            detail.label(text=f"Geometry score: {item.geometry_confidence:.3f}")
            if item.semantic_source not in {"", "none"}:
                detail.label(text=f"AI: {item.semantic_class} / {item.semantic_confidence:.3f} ({item.semantic_model})")
                if item.semantic_rationale:
                    shown = item.semantic_rationale if len(item.semantic_rationale) <= 115 else item.semantic_rationale[:112] + "..."
                    detail.label(text=shown)
            row = detail.row(align=True)
            row.prop(item, "start_x_mm")
            row.prop(item, "start_y_mm")
            row = detail.row(align=True)
            row.prop(item, "end_x_mm")
            row.prop(item, "end_y_mm")
            detail.prop(item, "thickness_mm")
            detail.operator("mh_room.open_candidate_preview", icon="IMAGE_DATA")
            row = detail.row(align=True)
            row.operator("mh_room.accept_candidate", icon="CHECKMARK")
            row.operator("mh_room.reject_candidate", icon="X")
            row.operator("mh_room.reset_candidate_review", text="Reset", icon="LOOP_BACK")
            detail.prop(item, "user_class")
            detail.operator("mh_room.apply_candidate_class", icon="FILE_TICK")

        dataset = review_box.box()
        dataset.label(text="Future MH floorplan model dataset", icon="FILE_FOLDER")
        dataset.prop(settings, "log_training_examples")
        if settings.log_training_examples:
            dataset.prop(settings, "training_dataset_dir")
            dataset.label(text="Only your manual labels are recorded as training truth.")

        build_box = layout.box()
        build_box.label(text="6. Clean geometry", icon="MESH_CUBE")
        row = build_box.row(align=True)
        row.enabled = settings.accepted_candidates > 0 and settings.calibration_confidence >= 0.55
        row.operator("mh_room.build_walls", icon="CHECKMARK")
        build_box.operator("mh_room.clear_walls", icon="TRASH")
        build_box.label(text="Accepted wall: 8 vertices / 6 quad faces / no booleans")
        if not settings.accepted_candidates:
            build_box.label(text="Human acceptance is required before any wall is buildable.", icon="LOCKED")

        ref_box = layout.box()
        ref_box.label(text="7. Reference renderings", icon="IMAGE_DATA")
        ref_box.template_list("MH_UL_references", "", settings, "references", settings, "reference_index", rows=3)
        row = ref_box.row(align=True)
        row.operator("mh_room.add_reference", text="Add", icon="ADD")
        row.operator("mh_room.remove_reference", text="Remove", icon="REMOVE")

        if settings.references and settings.reference_index < len(settings.references):
            item = settings.references[settings.reference_index]
            ref_box.prop(item, "kind")
            ref_box.prop(item, "notes")
            row = ref_box.row(align=True)
            row.enabled = bool(settings.ollama_model)
            row.operator("mh_room.analyze_reference_ai", icon="VIEWZOOM")
            if item.ai_json_path:
                row.operator("mh_room.open_reference_ai_result", text="Open JSON", icon="FILE")
            ref_box.label(text=f"AI status: {item.ai_status}")
            if item.ai_summary:
                shown = item.ai_summary if len(item.ai_summary) <= 120 else item.ai_summary[:117] + "..."
                ref_box.label(text=shown)
            ref_box.separator()
            ref_box.label(text="Optional human estimates; never treated as measured data")
            ref_box.prop(item, "has_sill_estimate")
            if item.has_sill_estimate:
                ref_box.prop(item, "sill_height_mm")
            ref_box.prop(item, "has_height_estimate")
            if item.has_height_estimate:
                ref_box.prop(item, "opening_height_mm")
            ref_box.prop(item, "has_frame_estimate")
            if item.has_frame_estimate:
                ref_box.prop(item, "frame_width_mm")
