from math import isclose

from mh_room_builder.domain.geometry import wall_prism
from mh_room_builder.domain.models import Point2D


def test_wall_prism_topology_contract():
    geo = wall_prism(Point2D(0, 0), Point2D(4000, 0), 120, 2800)
    assert len(geo.vertices_m) == 8
    assert len(geo.faces) == 6
    assert all(len(face) == 4 for face in geo.faces)
    assert isclose(max(v[2] for v in geo.vertices_m), 2.8)
    assert isclose(min(v[2] for v in geo.vertices_m), 0.0)


def test_wall_prism_rotated_keeps_clean_topology():
    geo = wall_prism(Point2D(100, 200), Point2D(2100, 2200), 150, 3000)
    assert len(set(geo.vertices_m)) == 8
    assert len(geo.faces) == 6
    assert all(len(set(face)) == 4 for face in geo.faces)
