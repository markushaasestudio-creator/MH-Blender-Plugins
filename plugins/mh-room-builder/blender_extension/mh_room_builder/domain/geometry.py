from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from .models import Point2D

MM_TO_M = 0.001


@dataclass(frozen=True, slots=True)
class PrismGeometry:
    vertices_m: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, int, int, int], ...]


def wall_prism(
    start: Point2D,
    end: Point2D,
    thickness_mm: float,
    height_mm: float,
    base_z_mm: float = 0.0,
) -> PrismGeometry:
    """Create one clean rectangular wall prism.

    Topology contract:
    - exactly 8 vertices
    - exactly 6 quad faces
    - no triangles
    - no n-gons
    - no booleans
    """
    dx = end.x_mm - start.x_mm
    dy = end.y_mm - start.y_mm
    length = hypot(dx, dy)
    if length <= 1e-6:
        raise ValueError("Wall length must be greater than zero")
    if thickness_mm <= 0:
        raise ValueError("Wall thickness must be greater than zero")
    if height_mm <= 0:
        raise ValueError("Wall height must be greater than zero")

    nx = -dy / length
    ny = dx / length
    half = thickness_mm * 0.5

    p0 = (start.x_mm + nx * half, start.y_mm + ny * half)
    p1 = (end.x_mm + nx * half, end.y_mm + ny * half)
    p2 = (end.x_mm - nx * half, end.y_mm - ny * half)
    p3 = (start.x_mm - nx * half, start.y_mm - ny * half)

    z0 = base_z_mm
    z1 = base_z_mm + height_mm

    verts_mm = (
        (p0[0], p0[1], z0),
        (p1[0], p1[1], z0),
        (p2[0], p2[1], z0),
        (p3[0], p3[1], z0),
        (p0[0], p0[1], z1),
        (p1[0], p1[1], z1),
        (p2[0], p2[1], z1),
        (p3[0], p3[1], z1),
    )
    vertices_m = tuple(
        (x * MM_TO_M, y * MM_TO_M, z * MM_TO_M) for x, y, z in verts_mm
    )

    faces = (
        (0, 3, 2, 1),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    )
    return PrismGeometry(vertices_m=vertices_m, faces=faces)
