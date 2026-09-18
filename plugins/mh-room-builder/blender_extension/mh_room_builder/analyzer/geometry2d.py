from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, hypot, pi, sin
from statistics import median


@dataclass(frozen=True, slots=True)
class P2:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Segment:
    a: P2
    b: P2
    source: str = "unknown"

    @property
    def dx(self) -> float:
        return self.b.x - self.a.x

    @property
    def dy(self) -> float:
        return self.b.y - self.a.y

    @property
    def length(self) -> float:
        return hypot(self.dx, self.dy)

    @property
    def angle(self) -> float:
        return atan2(self.dy, self.dx) % pi

    @property
    def midpoint(self) -> P2:
        return P2((self.a.x + self.b.x) * 0.5, (self.a.y + self.b.y) * 0.5)


def _angle_delta(a: float, b: float) -> float:
    d = abs(a - b) % pi
    return min(d, pi - d)


def merge_collinear_segments(segments: list[Segment], angle_tol_deg: float = 1.0, offset_tol: float = 1.5, gap_tol: float = 3.0) -> list[Segment]:
    if not segments:
        return []
    angle_tol = angle_tol_deg * pi / 180.0
    remaining = sorted(segments, key=lambda s: s.length, reverse=True)
    merged: list[Segment] = []
    while remaining:
        seed = remaining.pop(0)
        if seed.length <= 1e-9:
            continue
        ux = seed.dx / seed.length
        uy = seed.dy / seed.length
        nx, ny = -uy, ux
        origin = seed.a
        t_values = [0.0, seed.length]
        group = [seed]
        keep: list[Segment] = []
        for seg in remaining:
            if seg.length <= 1e-9 or _angle_delta(seed.angle, seg.angle) > angle_tol:
                keep.append(seg); continue
            offsets = [(seg.a.x-origin.x)*nx + (seg.a.y-origin.y)*ny, (seg.b.x-origin.x)*nx + (seg.b.y-origin.y)*ny]
            if max(abs(v) for v in offsets) > offset_tol:
                keep.append(seg); continue
            ts = [(seg.a.x-origin.x)*ux + (seg.a.y-origin.y)*uy, (seg.b.x-origin.x)*ux + (seg.b.y-origin.y)*uy]
            current_min,current_max=min(t_values),max(t_values)
            seg_min,seg_max=min(ts),max(ts)
            gap=max(seg_min-current_max,current_min-seg_max,0.0)
            if gap > gap_tol:
                keep.append(seg); continue
            t_values.extend(ts); group.append(seg)
        t0,t1=min(t_values),max(t_values)
        offsets_all=[]
        for seg in group:
            for point in (seg.a,seg.b):
                offsets_all.append((point.x-origin.x)*nx + (point.y-origin.y)*ny)
        offset=median(offsets_all) if offsets_all else 0.0
        a=P2(origin.x+ux*t0+nx*offset, origin.y+uy*t0+ny*offset)
        b=P2(origin.x+ux*t1+nx*offset, origin.y+uy*t1+ny*offset)
        merged.append(Segment(a,b,source=seed.source))
        remaining=sorted(keep,key=lambda s:s.length,reverse=True)
    return merged


def infer_wall_pairs(segments: list[Segment], mm_per_unit: float, default_thickness_mm: float, min_wall_length_mm: float = 400.0, min_thickness_mm: float = 60.0, max_thickness_mm: float = 500.0, angle_tol_deg: float = 1.5) -> list[dict]:
    if mm_per_unit <= 0:
        return []
    angle_tol=angle_tol_deg*pi/180.0
    min_len_units=min_wall_length_mm/mm_per_unit
    usable=[s for s in segments if s.length>=min_len_units]
    candidates=[]
    for i,first in enumerate(usable):
        ux=first.dx/first.length; uy=first.dy/first.length; nx,ny=-uy,ux
        for second in usable[i+1:]:
            angle_diff=_angle_delta(first.angle,second.angle)
            if angle_diff>angle_tol: continue
            sm=second.midpoint
            distance_units=(sm.x-first.a.x)*nx + (sm.y-first.a.y)*ny
            thickness_mm=abs(distance_units)*mm_per_unit
            if not (min_thickness_mm<=thickness_mm<=max_thickness_mm): continue
            first_range=(0.0,first.length)
            s_t=[(second.a.x-first.a.x)*ux + (second.a.y-first.a.y)*uy, (second.b.x-first.a.x)*ux + (second.b.y-first.a.y)*uy]
            second_range=(min(s_t),max(s_t))
            t0=max(first_range[0],second_range[0]); t1=min(first_range[1],second_range[1])
            overlap=t1-t0; overlap_mm=overlap*mm_per_unit
            if overlap_mm<min_wall_length_mm: continue
            center_offset=distance_units*0.5
            start=P2(first.a.x+ux*t0+nx*center_offset, first.a.y+uy*t0+ny*center_offset)
            end=P2(first.a.x+ux*t1+nx*center_offset, first.a.y+uy*t1+ny*center_offset)
            angle_score=max(0.0,1.0-angle_diff/angle_tol)
            overlap_score=min(1.0,overlap_mm/2500.0)
            if default_thickness_mm>0:
                rel_error=abs(thickness_mm-default_thickness_mm)/max(default_thickness_mm,1.0)
                thickness_score=max(0.0,1.0-min(rel_error,1.0))
            else: thickness_score=0.5
            confidence=min(0.97,0.48+0.18*angle_score+0.20*overlap_score+0.11*thickness_score)
            candidates.append({"start":start,"end":end,"thickness_mm":thickness_mm,"confidence":confidence,"source":"parallel_line_pair","evidence":[f"parallel edge separation {thickness_mm:.1f} mm",f"parallel overlap {overlap_mm:.1f} mm"]})
    return deduplicate_wall_candidates(candidates,mm_per_unit)


def deduplicate_wall_candidates(candidates: list[dict], mm_per_unit: float) -> list[dict]:
    accepted=[]
    for candidate in sorted(candidates,key=lambda c:c["confidence"],reverse=True):
        c_start=candidate["start"]; c_end=candidate["end"]
        c_mid=P2((c_start.x+c_end.x)*0.5,(c_start.y+c_end.y)*0.5)
        c_angle=atan2(c_end.y-c_start.y,c_end.x-c_start.x)%pi
        duplicate=False
        for existing in accepted:
            e_start=existing["start"]; e_end=existing["end"]
            e_mid=P2((e_start.x+e_end.x)*0.5,(e_start.y+e_end.y)*0.5)
            e_angle=atan2(e_end.y-e_start.y,e_end.x-e_start.x)%pi
            mid_distance_mm=hypot(c_mid.x-e_mid.x,c_mid.y-e_mid.y)*mm_per_unit
            if mid_distance_mm<80.0 and _angle_delta(c_angle,e_angle)<(1.5*pi/180.0):
                duplicate=True; break
        if not duplicate: accepted.append(candidate)
    return accepted
