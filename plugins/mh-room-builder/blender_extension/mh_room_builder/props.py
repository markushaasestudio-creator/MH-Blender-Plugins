from __future__ import annotations

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import PropertyGroup

SEMANTIC_CLASS_ITEMS = [
    ("UNKNOWN", "Unknown", "Ambiguous or not classified"),
    ("WALL", "Wall", "Architectural full-height wall/boundary"),
    ("CABINET", "Cabinet", "Built-in or loose cabinetry/wardrobe"),
    ("KITCHEN", "Kitchen", "Kitchen unit/front/counter"),
    ("FURNITURE", "Furniture", "Loose furniture"),
    ("DOOR", "Door", "Door leaf/frame/opening symbol"),
    ("WINDOW", "Window", "Window/frame/opening symbol"),
    ("COLUMN", "Column", "Structural column/pier"),
    ("STAIRS", "Stairs", "Stair element"),
    ("SANITARY", "Sanitary", "Bathroom/sanitary fixture"),
    ("DIMENSION", "Dimension", "Dimension line or witness line"),
    ("ANNOTATION", "Annotation", "Grid/text/detail annotation"),
]

REVIEW_STATUS_ITEMS = [
    ("UNREVIEWED", "Unreviewed", "Not yet decided by a human"),
    ("ACCEPTED", "Accepted wall", "Human-accepted wall candidate; buildable"),
    ("REJECTED", "Rejected", "Human-rejected as a wall"),
]


class MHReferenceImage(PropertyGroup):
    path: StringProperty(name="Image", subtype="FILE_PATH")
    kind: EnumProperty(name="Reference Type", items=[
        ("GENERAL", "General", "General room rendering/reference"),
        ("WINDOW", "Window", "Reference used to judge window details"),
        ("DOOR", "Door", "Reference used to judge door details"),
        ("ARCH_DETAIL", "Arch Detail", "Other architectural detail"),
    ], default="GENERAL")
    notes: StringProperty(name="Notes", default="")
    has_sill_estimate: BoolProperty(name="Use sill estimate", default=False)
    sill_height_mm: FloatProperty(name="Sill height (mm)", default=900.0, min=0.0, max=10000.0)
    has_height_estimate: BoolProperty(name="Use opening estimate", default=False)
    opening_height_mm: FloatProperty(name="Opening height (mm)", default=1500.0, min=0.0, max=10000.0)
    has_frame_estimate: BoolProperty(name="Use frame estimate", default=False)
    frame_width_mm: FloatProperty(name="Frame width (mm)", default=70.0, min=0.0, max=1000.0)
    ai_status: StringProperty(name="AI status", default="Not analyzed")
    ai_summary: StringProperty(name="AI summary", default="")
    ai_json_path: StringProperty(name="AI result", subtype="FILE_PATH")
    ai_model: StringProperty(name="AI model", default="")
    ai_elements_count: IntProperty(name="AI elements", default=0, min=0)


class MHReviewCandidate(PropertyGroup):
    candidate_id: StringProperty(name="ID", default="")
    source: StringProperty(name="Source", default="")
    start_x_mm: FloatProperty(name="Start X (mm)")
    start_y_mm: FloatProperty(name="Start Y (mm)")
    end_x_mm: FloatProperty(name="End X (mm)")
    end_y_mm: FloatProperty(name="End Y (mm)")
    thickness_mm: FloatProperty(name="Thickness (mm)", default=120.0, min=1.0, max=2000.0)
    geometry_confidence: FloatProperty(name="Geometry score", default=0.0, min=0.0, max=1.0, subtype="FACTOR")
    semantic_class: EnumProperty(name="AI class", items=SEMANTIC_CLASS_ITEMS, default="UNKNOWN")
    semantic_confidence: FloatProperty(name="AI score", default=0.0, min=0.0, max=1.0, subtype="FACTOR")
    semantic_source: StringProperty(name="Semantic source", default="none")
    semantic_model: StringProperty(name="Semantic model", default="")
    semantic_rationale: StringProperty(name="AI rationale", default="")
    structural_boundary: BoolProperty(name="AI structural boundary", default=False)
    review_status: EnumProperty(name="Human review", items=REVIEW_STATUS_ITEMS, default="UNREVIEWED")
    user_class: EnumProperty(name="Human class", items=SEMANTIC_CLASS_ITEMS, default="UNKNOWN")


class MHRoomBuilderSettings(PropertyGroup):
    floorplan_path: StringProperty(name="Floorplan", subtype="FILE_PATH")
    floorplan_page: IntProperty(name="PDF page", default=1, min=1)
    ceiling_height_mm: FloatProperty(name="Ceiling height (mm)", description="Authoritative manual room height unless later replaced by verified project data", default=2800.0, min=1000.0, max=10000.0)
    default_wall_thickness_mm: FloatProperty(name="Expected wall thickness (mm)", description="Used only as a scoring hint; detected wall thickness is kept per wall", default=120.0, min=40.0, max=1000.0)
    min_wall_confidence: FloatProperty(name="Review geometry threshold", description="Geometric hypotheses below this score are hidden from the initial review list unless the threshold is lowered", default=0.62, min=0.0, max=1.0, subtype="FACTOR")
    analyzer_python: StringProperty(name="Analyzer Python", description="External Python executable with the analyzer dependencies installed", subtype="FILE_PATH")
    analysis_json_path: StringProperty(name="Analysis JSON", subtype="FILE_PATH")
    analysis_status: StringProperty(name="Status", default="Not analyzed")
    analysis_source_kind: StringProperty(name="Source kind", default="unknown")
    calibration_method: StringProperty(name="Calibration", default="unresolved")
    calibration_confidence: FloatProperty(name="Calibration confidence", default=0.0, min=0.0, max=1.0)
    calibration_mm_per_unit: FloatProperty(name="mm/source unit", default=0.0, min=0.0)
    detected_dimensions: IntProperty(name="Dimensions", default=0, min=0)
    detected_walls: IntProperty(name="Verified wall proposals", default=0, min=0)
    raw_wall_hypotheses: IntProperty(name="Raw wall hypotheses", default=0, min=0)
    raw_segments: IntProperty(name="Raw line segments", default=0, min=0)
    merged_segments: IntProperty(name="Merged line segments", default=0, min=0)
    plan_origin_x_mm: FloatProperty(name="Plan origin X (mm)", default=0.0)
    plan_origin_y_mm: FloatProperty(name="Plan origin Y (mm)", default=0.0)
    warnings_count: IntProperty(name="Warnings", default=0, min=0)
    warning_1: StringProperty(default="")
    warning_2: StringProperty(default="")
    warning_3: StringProperty(default="")
    ocr_status: StringProperty(name="OCR", default="not used")
    analysis_preview_path: StringProperty(name="Analysis preview", subtype="FILE_PATH")
    embedded_images: IntProperty(name="Embedded images", default=0, min=0)
    pdf_text_chars: IntProperty(name="PDF text chars", default=0, min=0)

    review_candidates: CollectionProperty(type=MHReviewCandidate)
    review_index: IntProperty(default=0, min=0)
    review_limit: IntProperty(name="Review candidate limit", description="Load the strongest N geometric hypotheses into Blender for interactive review", default=200, min=10, max=2000)
    accepted_candidates: IntProperty(name="Accepted", default=0, min=0)
    rejected_candidates: IntProperty(name="Rejected", default=0, min=0)
    ai_reviewed_candidates: IntProperty(name="AI reviewed", default=0, min=0)

    ollama_endpoint: StringProperty(name="Ollama endpoint", description="Local Ollama REST API. Studio images are not sent to non-local endpoints unless explicitly enabled", default="http://127.0.0.1:11434")
    ollama_model: StringProperty(name="Vision model", description="Exact installed Ollama model tag. Use Detect Models to discover local vision models", default="")
    ollama_status: StringProperty(name="Ollama status", default="Not checked")
    ollama_capabilities: StringProperty(name="Capabilities", default="")
    allow_remote_ollama: BoolProperty(name="Allow non-local endpoint", description="OFF by default to prevent customer plans/renderings from being sent away from this machine", default=False)
    semantic_candidate_count: IntProperty(name="Candidates per AI run", description="How many highest-priority unreviewed candidates to classify per run", default=24, min=1, max=200)
    semantic_contact_batch_size: IntProperty(name="Candidates per contact sheet", description="Number of candidate crops placed in one vision-model request", default=6, min=1, max=12)
    semantic_timeout_seconds: IntProperty(name="AI timeout (s)", default=240, min=30, max=1800)
    semantic_include_overview: BoolProperty(name="Include full-plan overview", description="Adds a reduced whole-plan image to each AI batch; improves context but increases inference cost", default=False)
    semantic_status: StringProperty(name="Semantic status", default="Not run")
    semantic_json_path: StringProperty(name="Semantic JSON", subtype="FILE_PATH")
    semantic_preview_path: StringProperty(name="Semantic preview", subtype="FILE_PATH")
    candidate_preview_path: StringProperty(name="Candidate preview", subtype="FILE_PATH")

    log_training_examples: BoolProperty(name="Log manual labels", description="Save locally reviewed candidate crops/labels for a future MH-specific floorplan model", default=True)
    training_dataset_dir: StringProperty(name="Dataset folder", subtype="DIR_PATH", default="~/Documents/MH_Room_Builder_Dataset")

    references: CollectionProperty(type=MHReferenceImage)
    reference_index: IntProperty(default=0, min=0)
