from __future__ import annotations

from pathlib import Path
from typing import Any
import tempfile

from .calibration import TextDimension, calibration_from_print_scale, infer_calibration_from_dimensions
from .dimensions import parse_dimension, parse_scale_denominator
from .geometry2d import P2, Segment, infer_wall_pairs, merge_collinear_segments
from .hypotheses import serialize_wall_hypotheses


def _import_pymupdf():
    try:
        import pymupdf  # type: ignore
        return pymupdf
    except ImportError:
        try:
            import fitz as pymupdf  # type: ignore
            return pymupdf
        except ImportError as exc:
            raise RuntimeError("PyMuPDF is required for PDF analysis. Install analyzer requirements first.") from exc


def _extract_segments(page: Any) -> list[Segment]:
    segments: list[Segment] = []
    for path in page.get_drawings():
        for item in path.get("items", []):
            if not item:
                continue
            kind = item[0]
            if kind == "l" and len(item) >= 3:
                a, b = item[1], item[2]
                segments.append(Segment(P2(float(a.x), float(a.y)), P2(float(b.x), float(b.y)), "pdf_vector"))
            elif kind == "re" and len(item) >= 2:
                rect = item[1]
                p0 = P2(float(rect.x0), float(rect.y0)); p1 = P2(float(rect.x1), float(rect.y0)); p2 = P2(float(rect.x1), float(rect.y1)); p3 = P2(float(rect.x0), float(rect.y1))
                segments.extend([Segment(p0,p1,"pdf_rect"), Segment(p1,p2,"pdf_rect"), Segment(p2,p3,"pdf_rect"), Segment(p3,p0,"pdf_rect")])
    return segments


def _extract_text(page: Any) -> tuple[list[TextDimension], str]:
    dimensions=[]; all_text=[]
    data=page.get_text("dict")
    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            direction=tuple(float(v) for v in line.get("dir", (1.0,0.0)))
            for span in line.get("spans", []):
                text=str(span.get("text", "")).strip()
                if not text: continue
                all_text.append(text)
                parsed=parse_dimension(text)
                if parsed is None: continue
                bbox=tuple(float(v) for v in span.get("bbox", (0,0,0,0)))
                dimensions.append(TextDimension(text=text,value_mm=parsed.value_mm,bbox=bbox,confidence=parsed.confidence,interpretation=parsed.interpretation,direction=direction))
    return dimensions," ".join(all_text)


def analyze_pdf_vector(input_path: str, page_number: int, default_wall_thickness_mm: float, render_preview: bool = True) -> dict:
    pymupdf=_import_pymupdf(); path=Path(input_path); document=pymupdf.open(path)
    if page_number<1 or page_number>len(document): raise ValueError(f"Page {page_number} is outside document range 1..{len(document)}")
    page=document[page_number-1]
    raw_segments=_extract_segments(page)
    segments=merge_collinear_segments(raw_segments,angle_tol_deg=0.6,offset_tol=1.2,gap_tol=2.5)
    dimensions,page_text=_extract_text(page)
    printed_denominator=parse_scale_denominator(page_text)
    dim_cal=infer_calibration_from_dimensions(dimensions,segments)
    printed_cal=calibration_from_print_scale(printed_denominator) if printed_denominator else None
    warnings=[]; calibration=dim_cal
    if printed_cal and dim_cal.mm_per_unit:
        disagreement=abs(printed_cal.mm_per_unit-dim_cal.mm_per_unit)/max(dim_cal.mm_per_unit,1e-9)
        if disagreement<=0.08:
            calibration=type(dim_cal)(mm_per_unit=(printed_cal.mm_per_unit+dim_cal.mm_per_unit)*0.5,confidence=min(0.98,max(printed_cal.confidence,dim_cal.confidence)+0.04),method="printed_scale_plus_dimensions",evidence=printed_cal.evidence+dim_cal.evidence)
        else:
            warnings.append(f"Printed scale and dimension-derived scale disagree by {disagreement * 100:.1f}%. Dimension-derived calibration kept; review is required.")
    elif printed_cal and not dim_cal.mm_per_unit:
        calibration=printed_cal
    if calibration.mm_per_unit is None:
        warnings.append("No trustworthy drawing scale could be resolved. No wall geometry will be proposed."); wall_candidates=[]
    else:
        wall_candidates=infer_wall_pairs(segments,mm_per_unit=calibration.mm_per_unit,default_thickness_mm=default_wall_thickness_mm)
        if not wall_candidates: warnings.append("Scale was resolved, but no parallel-line wall pairs met the current wall criteria.")
    walls=[]
    wall_hypotheses=serialize_wall_hypotheses(wall_candidates,calibration.mm_per_unit or 0.0,prefix="V")
    preview_path=None
    if render_preview:
        preview_dir=Path(tempfile.gettempdir())/"mh_room_builder"; preview_dir.mkdir(parents=True,exist_ok=True)
        preview_path=str(preview_dir/f"{path.stem}_mh_preview_p{page_number}.png")
        pix=page.get_pixmap(dpi=300,alpha=False); pix.save(preview_path)
    return {"source_kind":("pdf_vector" if raw_segments else ("pdf_raster_image" if page.get_images(full=True) else "pdf_raster_or_empty")),"calibration":{"mm_per_source_unit":calibration.mm_per_unit,"confidence":calibration.confidence,"method":calibration.method,"evidence":list(calibration.evidence)},"dimensions":[{"text":item.text,"value_mm":item.value_mm,"bbox_source":list(item.bbox),"confidence":item.confidence,"unit_interpretation":item.interpretation} for item in dimensions],"walls":walls,"wall_hypotheses":wall_hypotheses,"warnings":warnings,"preview_path":preview_path,"stats":{"preview_scale_from_source":(300.0/72.0) if preview_path else 1.0,"raw_segments":len(raw_segments),"merged_segments":len(segments),"pdf_text_chars":len(page_text),"embedded_images":len(page.get_images(full=True)),"dimension_labels":len(dimensions),"wall_candidates":len(wall_hypotheses),"raw_wall_hypotheses":len(wall_hypotheses)}}
