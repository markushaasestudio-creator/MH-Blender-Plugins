from __future__ import annotations

import argparse
import json
from math import ceil, hypot
from pathlib import Path
import sys
import tempfile
from typing import Any

THIS_DIR = Path(__file__).resolve().parent
PACKAGE_DIR = THIS_DIR.parent
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))

from analyzer.ollama_client import (  # type: ignore  # noqa: E402
    OllamaError,
    chat_structured,
    is_local_endpoint,
    list_models,
    model_capabilities,
    normalize_endpoint,
)

ALLOWED_CLASSES = [
    "WALL","CABINET","KITCHEN","FURNITURE","DOOR","WINDOW",
    "COLUMN","STAIRS","SANITARY","DIMENSION","ANNOTATION","UNKNOWN",
]

SEMANTIC_SCHEMA = {
    "type": "object",
    "properties": {"results": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "candidate_id": {"type": "string"},
            "class": {"type": "string", "enum": ALLOWED_CLASSES},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "structural_boundary": {"type": "boolean"},
            "rationale": {"type": "string"},
        },
        "required": ["candidate_id","class","confidence","structural_boundary","rationale"],
        "additionalProperties": False,
    }}},
    "required": ["results"],
    "additionalProperties": False,
}

REFERENCE_SCHEMA = {
    "type":"object",
    "properties":{
        "summary":{"type":"string"},
        "architectural_elements":{"type":"array","items":{
            "type":"object",
            "properties":{
                "class":{"type":"string","enum":["WINDOW","DOOR","CABINET","KITCHEN","WALL","COLUMN","CEILING_DETAIL","OTHER"]},
                "description":{"type":"string"},
                "confidence":{"type":"number","minimum":0.0,"maximum":1.0},
                "relative_vertical_position":{"type":"string"},
                "frame_or_division_pattern":{"type":"string"},
            },
            "required":["class","description","confidence","relative_vertical_position","frame_or_division_pattern"],
            "additionalProperties":False,
        }},
        "uncertainties":{"type":"array","items":{"type":"string"}},
    },
    "required":["summary","architectural_elements","uncertainties"],
    "additionalProperties":False,
}

SYSTEM_PROMPT = """You are the semantic reviewer inside MH Room Builder, an architectural reconstruction tool.
You classify what a geometrically inferred line-pair most likely represents in an architectural floorplan.
You are NOT allowed to create geometry, infer exact dimensions, or override measured drawing data.
A true WALL is a full architectural wall/boundary. Kitchen fronts, wardrobes, shelves, furniture and annotations are not walls even when they create long parallel lines.
When evidence is ambiguous, use UNKNOWN rather than guessing. Confidence is an internal evidence score, not a calibrated probability.
Return only data matching the supplied JSON schema."""


def _imports_cv2():
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Semantic image preparation requires opencv-python-headless in the analyzer environment") from exc
    return cv2


def _load_analysis(path: str | Path) -> dict[str, Any]:
    p=Path(path); data=json.loads(p.read_text(encoding="utf-8"))
    if not data.get("wall_hypotheses"):
        raise RuntimeError("Analysis contains no reviewable wall hypotheses")
    preview=Path(str(data.get("preview_path") or ""))
    if not preview.exists():
        raise RuntimeError(f"Analysis preview source image not found: {preview}")
    return data


def _source_to_preview_scale(analysis: dict[str, Any]) -> float:
    return max(float(analysis.get("stats",{}).get("preview_scale_from_source") or 1.0),1e-9)


def _hypothesis_map(analysis: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(v["id"]):v for v in analysis.get("wall_hypotheses",[])}


def _candidate_raw_crop(image, candidate: dict[str, Any], source_scale: float):
    sx,sy=[float(v)*source_scale for v in candidate["start_source"]]
    ex,ey=[float(v)*source_scale for v in candidate["end_source"]]
    length=hypot(ex-sx,ey-sy); margin=max(120.0,min(700.0,length*0.40)); min_crop=420.0
    x0=min(sx,ex)-margin; y0=min(sy,ey)-margin; x1=max(sx,ex)+margin; y1=max(sy,ey)+margin
    if x1-x0<min_crop:
        cx=(x0+x1)*0.5; x0,x1=cx-min_crop*0.5,cx+min_crop*0.5
    if y1-y0<min_crop:
        cy=(y0+y1)*0.5; y0,y1=cy-min_crop*0.5,cy+min_crop*0.5
    h,w=image.shape[:2]
    ix0,iy0=max(0,int(x0)),max(0,int(y0)); ix1,iy1=min(w,int(ceil(x1))),min(h,int(ceil(y1)))
    crop=image[iy0:iy1,ix0:ix1].copy()
    if crop.size==0:
        raise RuntimeError(f"Empty crop for candidate {candidate['id']}")
    p1=(int(round(sx-ix0)),int(round(sy-iy0))); p2=(int(round(ex-ix0)),int(round(ey-iy0)))
    return crop,p1,p2


def _candidate_crop(image,candidate:dict[str,Any],source_scale:float,cv2,tile_w:int=640,tile_h:int=430):
    crop,p1,p2=_candidate_raw_crop(image,candidate,source_scale)
    cv2.line(crop,p1,p2,(220,0,220),5,cv2.LINE_AA); cv2.circle(crop,p1,9,(255,210,0),-1,cv2.LINE_AA); cv2.circle(crop,p2,9,(255,210,0),-1,cv2.LINE_AA)
    header=42; avail_h=tile_h-header; scale=min(tile_w/crop.shape[1],avail_h/crop.shape[0])
    resized=cv2.resize(crop,(max(1,int(crop.shape[1]*scale)),max(1,int(crop.shape[0]*scale))),interpolation=cv2.INTER_AREA)
    tile=255*__import__("numpy").ones((tile_h,tile_w,3),dtype="uint8")
    ox=(tile_w-resized.shape[1])//2; oy=header+(avail_h-resized.shape[0])//2
    tile[oy:oy+resized.shape[0],ox:ox+resized.shape[1]]=resized
    text=f"{candidate['id']}  geom {float(candidate.get('geometry_confidence',0.0)):.2f}  {float(candidate.get('thickness_mm',0.0)):.0f} mm"
    cv2.putText(tile,text,(12,29),cv2.FONT_HERSHEY_SIMPLEX,0.63,(0,0,0),2,cv2.LINE_AA)
    return tile


def _make_contact_sheet(analysis:dict[str,Any],candidate_ids:list[str],output_path:Path)->Path:
    cv2=_imports_cv2(); import numpy as np  # type: ignore
    image_path=Path(str(analysis["preview_path"])); image=cv2.imread(str(image_path),cv2.IMREAD_COLOR)
    if image is None: raise RuntimeError(f"Could not open analysis image: {image_path}")
    candidates=_hypothesis_map(analysis); scale=_source_to_preview_scale(analysis)
    tiles=[_candidate_crop(image,candidates[cid],scale,cv2) for cid in candidate_ids if cid in candidates]
    if not tiles: raise RuntimeError("No requested candidate IDs were found in the analysis")
    cols=1 if len(tiles)==1 else 2; rows=int(ceil(len(tiles)/cols)); tile_h,tile_w=tiles[0].shape[:2]
    sheet=245*np.ones((rows*tile_h,cols*tile_w,3),dtype="uint8")
    for idx,tile in enumerate(tiles):
        r,c=divmod(idx,cols); y0,x0=r*tile_h,c*tile_w; sheet[y0:y0+tile_h,x0:x0+tile_w]=tile
    output_path.parent.mkdir(parents=True,exist_ok=True)
    if not cv2.imwrite(str(output_path),sheet): raise RuntimeError(f"Could not write semantic contact sheet: {output_path}")
    return output_path


def _make_overview(analysis:dict[str,Any],output_path:Path,max_side:int=1600)->Path:
    cv2=_imports_cv2(); image_path=Path(str(analysis["preview_path"])); image=cv2.imread(str(image_path),cv2.IMREAD_COLOR)
    if image is None: raise RuntimeError(f"Could not open analysis image: {image_path}")
    h,w=image.shape[:2]; scale=min(1.0,max_side/max(h,w))
    if scale<1.0: image=cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
    output_path.parent.mkdir(parents=True,exist_ok=True); cv2.imwrite(str(output_path),image); return output_path


def _semantic_prompt(candidate_ids:list[str],include_overview:bool)->str:
    intro=("The attached candidate contact sheet contains cropped regions of one floorplan. "
           "A MAGENTA line with CYAN/YELLOW endpoints marks the exact geometric wall candidate to classify. "
           "Ignore the marker color itself and inspect the underlying plan context. ")
    if include_overview:
        intro+="The first attached image is a low-resolution full-plan overview; the second is the candidate contact sheet. "
    return intro+f"Return exactly one result for each of these IDs: {', '.join(candidate_ids)}. Do not omit or invent IDs."


def review_candidates(analysis_path:str,endpoint:str,model:str,candidate_ids:list[str],output_path:str,batch_size:int=6,timeout:int=240,allow_remote:bool=False,include_overview:bool=False)->dict[str,Any]:
    analysis=_load_analysis(analysis_path); available=_hypothesis_map(analysis); ids=[cid for cid in candidate_ids if cid in available]
    if not ids: raise RuntimeError("No valid candidate IDs were supplied for semantic review")
    temp_root=Path(tempfile.gettempdir())/"mh_room_builder"/"semantic"; temp_root.mkdir(parents=True,exist_ok=True)
    overview=None
    if include_overview: overview=_make_overview(analysis,temp_root/"floorplan_overview.png")
    all_results=[]; sheets=[]
    for offset in range(0,len(ids),max(1,batch_size)):
        batch=ids[offset:offset+max(1,batch_size)]
        sheet=_make_contact_sheet(analysis,batch,temp_root/f"semantic_candidates_{offset//max(1,batch_size)+1:03d}.png"); sheets.append(str(sheet))
        images=[sheet] if overview is None else [overview,sheet]
        parsed,_raw=chat_structured(endpoint,model,_semantic_prompt(batch,include_overview),images,SEMANTIC_SCHEMA,system=SYSTEM_PROMPT,timeout=timeout,allow_remote=allow_remote)
        returned={}
        for item in parsed.get("results",[]):
            cid=str(item.get("candidate_id",""))
            if cid in batch and cid not in returned: returned[cid]=item
        for cid in batch:
            item=returned.get(cid)
            if item is None:
                all_results.append({"candidate_id":cid,"class":"UNKNOWN","confidence":0.0,"structural_boundary":False,"rationale":"Model omitted this candidate; human review required."})
            else:
                cls=str(item.get("class","UNKNOWN")).upper()
                if cls not in ALLOWED_CLASSES: cls="UNKNOWN"
                all_results.append({"candidate_id":cid,"class":cls,"confidence":max(0.0,min(1.0,float(item.get("confidence",0.0)))),"structural_boundary":bool(item.get("structural_boundary",False)),"rationale":str(item.get("rationale",""))[:700]})
    payload={"schema_version":"0.1.2","analysis_path":str(Path(analysis_path).resolve()),"endpoint":normalize_endpoint(endpoint),"local_endpoint":is_local_endpoint(endpoint),"model":model,"results":all_results,"contact_sheets":sheets,"overview":str(overview) if overview else ""}
    out=Path(output_path); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8"); return payload


def analyze_reference_image(image_path:str,endpoint:str,model:str,output_path:str,timeout:int=240,allow_remote:bool=False)->dict[str,Any]:
    prompt="""Analyze this customer interior rendering only as non-authoritative architectural evidence.
Identify visible windows, doors, wall/ceiling details, built-in cabinetry and kitchen elements.
For windows/doors, describe relative vertical position and visible frame/division pattern, but do NOT invent millimetre dimensions.
Do not infer hidden geometry. Put ambiguous observations in uncertainties. Return JSON only."""
    parsed,_raw=chat_structured(endpoint,model,prompt,[image_path],REFERENCE_SCHEMA,system="You assist an architectural reconstruction tool. Visual observations are estimates, never measured truth.",timeout=timeout,allow_remote=allow_remote)
    payload={"schema_version":"0.1.2","image":str(Path(image_path).resolve()),"endpoint":normalize_endpoint(endpoint),"local_endpoint":is_local_endpoint(endpoint),"model":model,**parsed}
    out=Path(output_path); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8"); return payload


def make_candidate_preview(analysis_path:str,candidate_id:str,output_path:str)->dict[str,Any]:
    analysis=_load_analysis(analysis_path); candidates=_hypothesis_map(analysis)
    if candidate_id not in candidates: raise RuntimeError(f"Candidate not found: {candidate_id}")
    out=_make_contact_sheet(analysis,[candidate_id],Path(output_path)); return {"candidate_id":candidate_id,"preview":str(out)}


def export_training_example(analysis_path:str,candidate_id:str,label:str,dataset_dir:str)->dict[str,Any]:
    analysis=_load_analysis(analysis_path); candidates=_hypothesis_map(analysis)
    if candidate_id not in candidates: raise RuntimeError(f"Candidate not found: {candidate_id}")
    label=label.upper()
    if label not in ALLOWED_CLASSES: raise RuntimeError(f"Unsupported training label: {label}")
    root=Path(dataset_dir).expanduser().resolve(); root.mkdir(parents=True,exist_ok=True)
    safe_source=Path(str(analysis.get("source",{}).get("path","floorplan"))).stem; stem=f"{safe_source}_{candidate_id}_{label.lower()}"
    crop_path=root/"images"/f"{stem}.png"; crop_path.parent.mkdir(parents=True,exist_ok=True)
    cv2=_imports_cv2(); image=cv2.imread(str(Path(analysis["preview_path"])),cv2.IMREAD_COLOR)
    if image is None: raise RuntimeError(f"Could not open analysis image: {analysis['preview_path']}")
    crop,p1,p2=_candidate_raw_crop(image,candidates[candidate_id],_source_to_preview_scale(analysis))
    if not cv2.imwrite(str(crop_path),crop): raise RuntimeError(f"Could not write training crop: {crop_path}")
    meta={"schema_version":"0.1.2","source_floorplan":str(analysis.get("source",{}).get("path","")),"analysis_schema":str(analysis.get("schema_version","")),"candidate_id":candidate_id,"label":label,"candidate":candidates[candidate_id],"candidate_line_in_crop_px":{"start":list(p1),"end":list(p2)},"image":str(crop_path),"image_has_review_overlay":False}
    meta_path=root/"labels"/f"{stem}.json"; meta_path.parent.mkdir(parents=True,exist_ok=True); meta_path.write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding="utf-8")
    return {"image":str(crop_path),"metadata":str(meta_path)}


def main()->int:
    parser=argparse.ArgumentParser(description="MH Room Builder local Ollama semantic bridge"); sub=parser.add_subparsers(dest="command",required=True)
    p_list=sub.add_parser("list"); p_list.add_argument("--endpoint",default="http://127.0.0.1:11434"); p_list.add_argument("--timeout",type=int,default=30)
    p_check=sub.add_parser("check"); p_check.add_argument("--endpoint",default="http://127.0.0.1:11434"); p_check.add_argument("--model",required=True); p_check.add_argument("--timeout",type=int,default=30)
    p_review=sub.add_parser("review"); p_review.add_argument("--analysis",required=True); p_review.add_argument("--endpoint",default="http://127.0.0.1:11434"); p_review.add_argument("--model",required=True); p_review.add_argument("--candidate-ids",required=True); p_review.add_argument("--output",required=True); p_review.add_argument("--batch-size",type=int,default=6); p_review.add_argument("--timeout",type=int,default=240); p_review.add_argument("--allow-remote",action="store_true"); p_review.add_argument("--include-overview",action="store_true")
    p_ref=sub.add_parser("reference"); p_ref.add_argument("--image",required=True); p_ref.add_argument("--endpoint",default="http://127.0.0.1:11434"); p_ref.add_argument("--model",required=True); p_ref.add_argument("--output",required=True); p_ref.add_argument("--timeout",type=int,default=240); p_ref.add_argument("--allow-remote",action="store_true")
    p_preview=sub.add_parser("preview"); p_preview.add_argument("--analysis",required=True); p_preview.add_argument("--candidate-id",required=True); p_preview.add_argument("--output",required=True)
    p_export=sub.add_parser("export-label"); p_export.add_argument("--analysis",required=True); p_export.add_argument("--candidate-id",required=True); p_export.add_argument("--label",required=True); p_export.add_argument("--dataset-dir",required=True)
    args=parser.parse_args()
    try:
        if args.command=="list":
            rows=[]
            for model in list_models(args.endpoint,timeout=args.timeout):
                name=str(model.get("name") or model.get("model") or "")
                if not name: continue
                try: caps=model_capabilities(args.endpoint,name,timeout=args.timeout)
                except Exception: caps=[]
                rows.append({"name":name,"capabilities":caps,"details":model.get("details",{})})
            print(json.dumps({"endpoint":normalize_endpoint(args.endpoint),"models":rows},ensure_ascii=False)); return 0
        if args.command=="check":
            caps=model_capabilities(args.endpoint,args.model,timeout=args.timeout); print(json.dumps({"endpoint":normalize_endpoint(args.endpoint),"model":args.model,"capabilities":caps,"vision":"vision" in caps},ensure_ascii=False)); return 0
        if args.command=="review":
            ids=[v.strip() for v in args.candidate_ids.split(",") if v.strip()]
            payload=review_candidates(args.analysis,args.endpoint,args.model,ids,args.output,batch_size=args.batch_size,timeout=args.timeout,allow_remote=args.allow_remote,include_overview=args.include_overview)
            print(json.dumps({"output":args.output,"results":len(payload["results"]),"contact_sheets":payload["contact_sheets"]},ensure_ascii=False)); return 0
        if args.command=="reference":
            payload=analyze_reference_image(args.image,args.endpoint,args.model,args.output,timeout=args.timeout,allow_remote=args.allow_remote); print(json.dumps({"output":args.output,"elements":len(payload.get("architectural_elements",[]))},ensure_ascii=False)); return 0
        if args.command=="preview":
            print(json.dumps(make_candidate_preview(args.analysis,args.candidate_id,args.output),ensure_ascii=False)); return 0
        if args.command=="export-label":
            print(json.dumps(export_training_example(args.analysis,args.candidate_id,args.label,args.dataset_dir),ensure_ascii=False)); return 0
        return 2
    except (OllamaError,RuntimeError,ValueError,OSError) as exc:
        print(f"ERROR: {exc}",file=sys.stderr); return 2


if __name__=="__main__":
    raise SystemExit(main())
