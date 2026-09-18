from __future__ import annotations


def _classes():
    from .operators import (
        MH_OT_accept_candidate,
        MH_OT_add_reference,
        MH_OT_analyze_floorplan,
        MH_OT_analyze_reference_ai,
        MH_OT_apply_candidate_class,
        MH_OT_build_walls,
        MH_OT_clear_walls,
        MH_OT_detect_ollama_models,
        MH_OT_open_analysis_preview,
        MH_OT_open_candidate_preview,
        MH_OT_open_reference_ai_result,
        MH_OT_open_semantic_preview,
        MH_OT_reject_candidate,
        MH_OT_reload_review_candidates,
        MH_OT_remove_reference,
        MH_OT_reset_candidate_review,
        MH_OT_semantic_review_next,
        MH_OT_semantic_review_selected,
        MH_OT_test_ollama_model,
    )
    from .props import MHReferenceImage, MHReviewCandidate, MHRoomBuilderSettings
    from .ui import MH_PT_room_builder, MH_UL_references, MH_UL_wall_review

    return (
        MHReferenceImage,
        MHReviewCandidate,
        MHRoomBuilderSettings,
        MH_OT_analyze_floorplan,
        MH_OT_reload_review_candidates,
        MH_OT_open_analysis_preview,
        MH_OT_detect_ollama_models,
        MH_OT_test_ollama_model,
        MH_OT_semantic_review_selected,
        MH_OT_semantic_review_next,
        MH_OT_open_semantic_preview,
        MH_OT_open_candidate_preview,
        MH_OT_accept_candidate,
        MH_OT_reject_candidate,
        MH_OT_apply_candidate_class,
        MH_OT_reset_candidate_review,
        MH_OT_build_walls,
        MH_OT_clear_walls,
        MH_OT_add_reference,
        MH_OT_remove_reference,
        MH_OT_analyze_reference_ai,
        MH_OT_open_reference_ai_result,
        MH_UL_references,
        MH_UL_wall_review,
        MH_PT_room_builder,
    )


def register():
    import bpy
    from .props import MHRoomBuilderSettings

    for cls in _classes():
        bpy.utils.register_class(cls)
    bpy.types.Scene.mh_room_builder = bpy.props.PointerProperty(type=MHRoomBuilderSettings)


def unregister():
    import bpy

    if hasattr(bpy.types.Scene, "mh_room_builder"):
        del bpy.types.Scene.mh_room_builder
    for cls in reversed(_classes()):
        bpy.utils.unregister_class(cls)
