from __future__ import annotations

import bpy

from .domain import WallCandidate, wall_prism

ROOT_COLLECTION = "MH_ROOM"
WALL_COLLECTION = "ARCH_WALLS"


def ensure_collection(name: str, parent: bpy.types.Collection | None = None) -> bpy.types.Collection:
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
    if parent is None:
        if bpy.context.scene.collection.children.get(collection.name) is None:
            try:
                bpy.context.scene.collection.children.link(collection)
            except RuntimeError:
                pass
    else:
        if parent.children.get(collection.name) is None:
            try:
                parent.children.link(collection)
            except RuntimeError:
                pass
    return collection


def room_collections() -> tuple[bpy.types.Collection, bpy.types.Collection]:
    root = bpy.data.collections.get(ROOT_COLLECTION)
    if root is None:
        root = bpy.data.collections.new(ROOT_COLLECTION)
        bpy.context.scene.collection.children.link(root)
    walls = bpy.data.collections.get(WALL_COLLECTION)
    if walls is None:
        walls = bpy.data.collections.new(WALL_COLLECTION)
        root.children.link(walls)
    elif root.children.get(walls.name) is None:
        try:
            root.children.link(walls)
        except RuntimeError:
            pass
    return root, walls


def clear_generated_walls() -> int:
    collection = bpy.data.collections.get(WALL_COLLECTION)
    if collection is None:
        return 0
    objects = list(collection.objects)
    for obj in objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    return len(objects)


def build_wall_object(wall: WallCandidate, ceiling_height_mm: float) -> bpy.types.Object:
    geometry = wall_prism(wall.start, wall.end, thickness_mm=wall.thickness_mm, height_mm=ceiling_height_mm)
    mesh = bpy.data.meshes.new(f"{wall.id}_MESH")
    mesh.from_pydata(geometry.vertices_m, [], geometry.faces)
    mesh.update(calc_edges=True)
    if mesh.validate(verbose=False):
        raise RuntimeError(f"Generated invalid mesh for {wall.id}")
    obj = bpy.data.objects.new(wall.id, mesh)
    obj["mh_role"] = "WALL"
    obj["mh_wall_id"] = wall.id
    obj["mh_source"] = wall.source
    obj["mh_confidence"] = float(wall.confidence)
    obj["mh_thickness_mm"] = float(wall.thickness_mm)
    obj["mh_height_mm"] = float(ceiling_height_mm)
    obj["mh_topology_contract"] = "8 verts / 6 quads / no boolean"
    _, walls_collection = room_collections()
    walls_collection.objects.link(obj)
    return obj
