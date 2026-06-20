"""Entity and relation construction."""

from __future__ import annotations

import math
import re
import statistics
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from shapely.geometry import LineString, Point

from .geometry import (
    bbox_center,
    bbox_key,
    clean_float,
    distance_between_bboxes,
    geometry_to_shapely,
)
from .labels import slugify


SPACE_LABEL_TYPES = {"room_label", "storage_label", "outdoor_label"}


def has_category(node: Dict, category: str) -> bool:
    return any(candidate.get("category") == category for candidate in node.get("categoryCandidates", []))


def build_entities_and_relations(vector_nodes: List[Dict], labels: List[Dict]) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    entities: List[Dict] = []
    relations: List[Dict] = []
    warnings: List[Dict] = []

    shape_cache = {node["id"]: geometry_to_shapely(node) for node in vector_nodes}
    space_candidates = build_space_candidates(vector_nodes, shape_cache)
    spaces = build_space_entities(labels, space_candidates, shape_cache, warnings)
    entities.extend(spaces)
    space_by_id = {space["id"]: space for space in spaces}

    for label in labels:
        if label["labelType"] in SPACE_LABEL_TYPES:
            continue
        if label["labelType"] == "fixture_label":
            fixture = build_fixture_entity(label, spaces, shape_cache)
            entities.append(fixture)
            label["linkedEntityId"] = fixture["id"]
            located_in = fixture.get("locatedIn")
            if located_in:
                relations.append(relation("locatedIn", fixture["id"], [located_in], fixture["confidence"], fixture["evidence"]))
                relations.append(relation("contains", located_in, [fixture["id"]], fixture["confidence"], fixture["evidence"]))
        else:
            annotation = build_annotation_entity(label)
            entities.append(annotation)
            label["linkedEntityId"] = annotation["id"]

    walls, line_groups = build_wall_entities(vector_nodes, shape_cache)
    entities.extend(walls)
    entities.extend(line_groups)

    windows = build_window_entities(vector_nodes, walls, spaces, shape_cache)
    entities.extend(windows)
    for window in windows:
        if window.get("locatedOn"):
            relations.append(relation("locatedOn", window["id"], [window["locatedOn"]], window["confidence"], window["evidence"]))
        for space_id in window.get("adjacentTo", []):
            relations.append(relation("adjacentTo", window["id"], [space_id], window["confidence"], window["evidence"]))

    doors = build_door_entities(vector_nodes, spaces, shape_cache)
    entities.extend(doors)
    for door in doors:
        connects = door.get("connects", [])
        if connects:
            relations.append(relation("connects", door["id"], connects, door["confidence"], door["evidence"]))
        if door.get("opensInto") and door.get("opensInto") != "unknown":
            relations.append(relation("opensInto", door["id"], [door["opensInto"]], door["confidence"], door["evidence"]))

    for space in spaces:
        label_ids = space.get("labelIds", [])
        for label_id in label_ids:
            relations.append(relation("hasLabel", space["id"], [label_id], space["confidence"], space["evidence"]))
        for wall in nearest_walls_for_space(space, walls, shape_cache):
            relations.append(relation("boundedBy", space["id"], [wall["id"]], 0.35, ["nearest_wall_candidate"]))

    return entities, relations, warnings


def relation(rel_type: str, from_id: str, to_ids: Sequence[str], confidence: float, evidence: Sequence[str]) -> Dict:
    return {
        "id": f"rel_{rel_type}_{slugify(from_id)}_{slugify('_'.join(to_ids))}",
        "type": rel_type,
        "from": from_id,
        "to": list(to_ids),
        "confidence": clean_float(confidence),
        "evidence": list(evidence),
    }


def build_space_candidates(vector_nodes: List[Dict], shape_cache: Dict[str, object]) -> List[Dict]:
    candidates = []
    for node in vector_nodes:
        if not has_category(node, "space_surface_candidate"):
            continue
        bbox = node.get("bbox") or [0, 0, 0, 0]
        if bbox[1] > 1850:
            continue
        geom = shape_cache.get(node["id"])
        if geom is None or getattr(geom, "area", 0) < 2000:
            continue
        candidates.append({"node": node, "geom": geom, "area": float(getattr(geom, "area", 0))})
    return candidates


def build_space_entities(labels: List[Dict], candidates: List[Dict], shape_cache: Dict[str, object], warnings: List[Dict]) -> List[Dict]:
    spaces = []
    used_ids: Dict[str, int] = defaultdict(int)
    for label in labels:
        if label["labelType"] not in SPACE_LABEL_TYPES:
            continue
        anchor = label.get("anchor") or [0, 0]
        point = Point(anchor[0], anchor[1])
        containing = [candidate for candidate in candidates if candidate["geom"].contains(point) or candidate["geom"].touches(point)]
        containing.sort(key=lambda item: item["area"])

        status = "inferred"
        confidence = 0.9
        evidence = ["label_inside_space_surface"]
        matched = containing[0] if containing else None

        if matched is None and candidates:
            nearest = min(candidates, key=lambda item: item["geom"].distance(point))
            matched = nearest
            status = "needs_review"
            confidence = 0.52
            evidence = ["nearest_space_surface"]
            warnings.append({"type": "space_match_needs_review", "labelId": label["id"], "message": "No containing polygon found."})

        if matched is None:
            status = "needs_review"
            confidence = 0.2
            evidence = ["no_space_surface_candidate"]
            entity_geom = None
            bbox = None
            centroid = anchor
            geometry_refs: List[str] = []
        else:
            entity_geom = matched["geom"]
            node = matched["node"]
            bbox = node.get("bbox")
            centroid = node.get("centroid")
            geometry_refs = [node["id"]]

        base_id = f"space_{slugify(str(label['name']))}"
        used_ids[base_id] += 1
        entity_id = base_id if used_ids[base_id] == 1 else f"{base_id}_{used_ids[base_id]}"
        label["linkedEntityId"] = entity_id
        space = {
            "id": entity_id,
            "type": label.get("entityType", "Room"),
            "subtype": label.get("subtype"),
            "name": label["name"],
            "labelIds": [label["id"]],
            "dimensions": {
                "raw": label.get("dimensionText"),
                "unit": "imperial_text",
            },
            "geometryRefs": geometry_refs,
            "bbox": bbox,
            "centroid": centroid,
            "status": status,
            "confidence": confidence,
            "evidence": evidence,
        }
        if entity_geom is not None:
            space["_shape"] = entity_geom
        spaces.append(space)
    return spaces


def build_fixture_entity(label: Dict, spaces: List[Dict], shape_cache: Dict[str, object]) -> Dict:
    anchor = label.get("anchor") or [0, 0]
    point = Point(anchor[0], anchor[1])
    containing = []
    for space in spaces:
        geom = space.get("_shape")
        if geom is not None and (geom.contains(point) or geom.touches(point)):
            containing.append(space)
    containing.sort(key=lambda space: float(space.get("_shape").area if space.get("_shape") is not None else 0))
    located_in = containing[0]["id"] if containing else None
    evidence = ["fixture_label"]
    if located_in:
        evidence.append("label_inside_space")
    return {
        "id": f"fixture_{slugify(str(label['name']))}",
        "type": "Fixture",
        "subtype": label.get("subtype"),
        "name": label["name"],
        "labelIds": [label["id"]],
        "geometryRefs": [label.get("sourceVectorNodeId")],
        "anchor": anchor,
        "locatedIn": located_in,
        "status": "inferred" if located_in else "needs_review",
        "confidence": 0.78 if located_in else 0.5,
        "evidence": evidence,
    }


def build_annotation_entity(label: Dict) -> Dict:
    return {
        "id": f"annotation_{slugify(str(label['name']))}",
        "type": "Annotation",
        "subtype": label.get("subtype"),
        "name": label["name"],
        "labelIds": [label["id"]],
        "geometryRefs": [label.get("sourceVectorNodeId")],
        "anchor": label.get("anchor"),
        "status": "observed",
        "confidence": 1.0,
        "evidence": ["label_classification"],
    }


def build_wall_entities(vector_nodes: List[Dict], shape_cache: Dict[str, object]) -> Tuple[List[Dict], List[Dict]]:
    segments = collect_axis_aligned_wall_segments(vector_nodes)
    if not segments:
        return [], []

    tolerances = line_group_tolerances(segments)
    detail_segment_keys = detect_repeated_detail_segments(segments, tolerances)
    window_bboxes = [node.get("bbox") for node in vector_nodes if has_category(node, "window_candidate") and node.get("bbox")]
    merged = merge_collinear_segments(segments, tolerances)

    walls: List[Dict] = []
    line_groups: List[Dict] = []
    wall_idx = 1
    group_idx = 1
    for group in merged:
        ref_ids = unique_refs(segment["nodeId"] for segment in group["segments"])
        length = group["end"] - group["start"]
        segment_keys = {segment["segmentKey"] for segment in group["segments"]}
        is_repeated_detail = bool(segment_keys & detail_segment_keys)
        is_window_detail = group_near_window(group, window_bboxes, tolerances) and length <= tolerances["window_detail_max_length"]
        if is_repeated_detail or is_window_detail:
            subtype = "RepeatedParallelDetail" if is_repeated_detail else "WindowDetail"
            line_groups.append(line_group_entity(group_idx, subtype, group, ref_ids, tolerances))
            group_idx += 1
            continue
        if length < tolerances["minWallLength"] and len(ref_ids) == 1:
            line_groups.append(line_group_entity(group_idx, "ShortUnmergedCandidate", group, ref_ids, tolerances))
            group_idx += 1
            continue
        walls.append(wall_entity(wall_idx, group, ref_ids, tolerances))
        wall_idx += 1
    return walls, line_groups


def collect_axis_aligned_wall_segments(vector_nodes: List[Dict]) -> List[Dict]:
    segments = []
    for node in vector_nodes:
        if not has_category(node, "wall_candidate"):
            continue
        points = node.get("geometry", {}).get("points") or node.get("geometry", {}).get("sampledPoints") or []
        if len(points) < 2:
            continue
        pairs = []
        if node.get("sourceTag") == "line":
            pairs = [(points[0], points[1])]
        elif node.get("sourceTag") == "polyline":
            pairs = list(zip(points, points[1:]))
        else:
            continue
        for idx, (left, right) in enumerate(pairs):
            segment = segment_from_points(node, idx, left, right)
            if segment:
                segments.append(segment)
    return segments


def segment_from_points(node: Dict, segment_index: int, left: Sequence[float], right: Sequence[float]) -> Optional[Dict]:
    x1, y1 = float(left[0]), float(left[1])
    x2, y2 = float(right[0]), float(right[1])
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    length = math.hypot(dx, dy)
    if length < 35:
        return None
    if dx >= dy * 5:
        orientation = "horizontal"
        axis = (y1 + y2) / 2
        start = min(x1, x2)
        end = max(x1, x2)
    elif dy >= dx * 5:
        orientation = "vertical"
        axis = (x1 + x2) / 2
        start = min(y1, y2)
        end = max(y1, y2)
    else:
        return None
    return {
        "segmentKey": f"{node['id']}:{segment_index}",
        "nodeId": node["id"],
        "orientation": orientation,
        "axis": axis,
        "start": start,
        "end": end,
        "length": length,
        "sourceTag": node.get("sourceTag"),
    }


def line_group_tolerances(segments: List[Dict]) -> Dict[str, float]:
    lengths = [segment["length"] for segment in segments]
    median_length = statistics.median(lengths)
    return {
        "medianSegmentLength": clean_float(median_length),
        "axisTolerance": clean_float(max(1.5, min(8.0, median_length * 0.025))),
        "gapTolerance": clean_float(max(10.0, min(45.0, median_length * 0.25))),
        "spanTolerance": clean_float(max(8.0, min(30.0, median_length * 0.15))),
        "minWallLength": clean_float(max(70.0, median_length * 0.75)),
        "windowDetailMaxDistance": 10.0,
        "window_detail_max_length": clean_float(max(180.0, median_length * 2.4)),
    }


def detect_repeated_detail_segments(segments: List[Dict], tolerances: Dict[str, float]) -> set:
    buckets: List[List[Dict]] = []
    span_tol = tolerances["spanTolerance"]
    for segment in sorted(segments, key=lambda item: (item["orientation"], item["start"], item["end"])):
        placed = False
        for bucket in buckets:
            head = bucket[0]
            if (
                segment["orientation"] == head["orientation"]
                and abs(segment["start"] - head["start"]) <= span_tol
                and abs(segment["end"] - head["end"]) <= span_tol
            ):
                bucket.append(segment)
                placed = True
                break
        if not placed:
            buckets.append([segment])

    repeated = set()
    for bucket in buckets:
        if len(bucket) < 3:
            continue
        axes = sorted(segment["axis"] for segment in bucket)
        spacings = [right - left for left, right in zip(axes, axes[1:]) if right - left > 0.5]
        if not spacings:
            continue
        median_spacing = statistics.median(spacings)
        axis_range = axes[-1] - axes[0]
        regularity = statistics.pstdev(spacings) / median_spacing if len(spacings) > 1 and median_spacing else 0
        if 8 <= median_spacing <= 90 and axis_range <= 360 and regularity <= 0.75:
            repeated.update(segment["segmentKey"] for segment in bucket)
    return repeated


def merge_collinear_segments(segments: List[Dict], tolerances: Dict[str, float]) -> List[Dict]:
    merged_groups = []
    axis_tol = tolerances["axisTolerance"]
    gap_tol = tolerances["gapTolerance"]
    for orientation in ["horizontal", "vertical"]:
        oriented = sorted([segment for segment in segments if segment["orientation"] == orientation], key=lambda item: item["axis"])
        axis_groups: List[Dict] = []
        for segment in oriented:
            if not axis_groups or abs(axis_groups[-1]["axisMean"] - segment["axis"]) > axis_tol:
                axis_groups.append({"axisValues": [segment["axis"]], "axisMean": segment["axis"], "segments": [segment]})
            else:
                axis_groups[-1]["segments"].append(segment)
                axis_groups[-1]["axisValues"].append(segment["axis"])
                axis_groups[-1]["axisMean"] = statistics.mean(axis_groups[-1]["axisValues"])
        for axis_group in axis_groups:
            intervals = sorted(axis_group["segments"], key=lambda item: item["start"])
            groups: List[Dict] = []
            for segment in intervals:
                if not groups or segment["start"] - groups[-1]["end"] > gap_tol:
                    groups.append(
                        {
                            "orientation": orientation,
                            "axis": axis_group["axisMean"],
                            "start": segment["start"],
                            "end": segment["end"],
                            "segments": [segment],
                        }
                    )
                else:
                    groups[-1]["segments"].append(segment)
                    groups[-1]["start"] = min(groups[-1]["start"], segment["start"])
                    groups[-1]["end"] = max(groups[-1]["end"], segment["end"])
            merged_groups.extend(groups)
    return merged_groups


def group_bbox(group: Dict) -> List[float]:
    if group["orientation"] == "horizontal":
        return [
            clean_float(group["start"]),
            clean_float(group["axis"]),
            clean_float(group["end"] - group["start"]),
            0.0,
        ]
    return [
        clean_float(group["axis"]),
        clean_float(group["start"]),
        0.0,
        clean_float(group["end"] - group["start"]),
    ]


def group_centroid(group: Dict) -> List[float]:
    if group["orientation"] == "horizontal":
        return [clean_float((group["start"] + group["end"]) / 2), clean_float(group["axis"])]
    return [clean_float(group["axis"]), clean_float((group["start"] + group["end"]) / 2)]


def group_geometry(group: Dict) -> Dict:
    if group["orientation"] == "horizontal":
        points = [[clean_float(group["start"]), clean_float(group["axis"])], [clean_float(group["end"]), clean_float(group["axis"])]]
    else:
        points = [[clean_float(group["axis"]), clean_float(group["start"])], [clean_float(group["axis"]), clean_float(group["end"])]]
    return {"type": "LineString", "points": points}


def group_near_window(group: Dict, window_bboxes: List[Sequence[float]], tolerances: Dict[str, float]) -> bool:
    bbox = group_bbox(group)
    return any(distance_between_bboxes(bbox, window_bbox) <= tolerances["windowDetailMaxDistance"] for window_bbox in window_bboxes)


def unique_refs(refs: Iterable[str]) -> List[str]:
    return list(dict.fromkeys(refs))


def wall_entity(index: int, group: Dict, refs: List[str], tolerances: Dict[str, float]) -> Dict:
    length = group["end"] - group["start"]
    return {
        "id": f"wall_{index:04d}",
        "type": "Wall",
        "subtype": "MergedBoundaryCandidate",
        "geometryRefs": refs,
        "computedGeometry": group_geometry(group),
        "bbox": group_bbox(group),
        "centroid": group_centroid(group),
        "length": clean_float(length),
        "orientation": group["orientation"],
        "sourceSegmentCount": len(group["segments"]),
        "mergeStats": {
            "axisTolerance": tolerances["axisTolerance"],
            "gapTolerance": tolerances["gapTolerance"],
            "medianSegmentLength": tolerances["medianSegmentLength"],
        },
        "status": "candidate",
        "confidence": 0.62 if len(group["segments"]) > 1 else 0.54,
        "evidence": ["statistical_collinear_merge", "long_black_stroke"],
    }


def line_group_entity(index: int, subtype: str, group: Dict, refs: List[str], tolerances: Dict[str, float]) -> Dict:
    length = group["end"] - group["start"]
    return {
        "id": f"line_group_{index:04d}",
        "type": "LineGroup",
        "subtype": subtype,
        "geometryRefs": refs,
        "computedGeometry": group_geometry(group),
        "bbox": group_bbox(group),
        "centroid": group_centroid(group),
        "length": clean_float(length),
        "orientation": group["orientation"],
        "sourceSegmentCount": len(group["segments"]),
        "mergeStats": {
            "axisTolerance": tolerances["axisTolerance"],
            "gapTolerance": tolerances["gapTolerance"],
            "medianSegmentLength": tolerances["medianSegmentLength"],
        },
        "status": "grouped",
        "confidence": 0.68,
        "evidence": ["statistical_line_grouping", subtype],
    }


def orientation_from_bbox(bbox: Sequence[float]) -> str:
    width, height = bbox[2], bbox[3]
    if width > height * 3:
        return "horizontal"
    if height > width * 3:
        return "vertical"
    return "other"


def build_window_entities(vector_nodes: List[Dict], walls: List[Dict], spaces: List[Dict], shape_cache: Dict[str, object]) -> List[Dict]:
    grouped: Dict[Tuple[float, float, float, float], List[Dict]] = defaultdict(list)
    for node in vector_nodes:
        if has_category(node, "window_candidate") and node.get("bbox"):
            grouped[bbox_key(node["bbox"])].append(node)

    windows = []
    for idx, nodes in enumerate(grouped.values(), start=1):
        primary = nodes[0]
        bbox = primary["bbox"]
        center = bbox_center(bbox)
        located_on = nearest_wall_id(bbox, walls)
        adjacent = nearest_space_ids_to_bbox(bbox, spaces, max_count=2)
        evidence = ["thin_repeated_light_polygon"]
        status = "inferred"
        confidence = 0.68
        if located_on:
            evidence.append("near_wall_candidate")
        else:
            status = "needs_review"
            confidence = 0.5
        windows.append(
            {
                "id": f"window_{idx:04d}",
                "type": "Window",
                "subtype": "WindowCandidate",
                "geometryRefs": [node["id"] for node in nodes],
                "bbox": bbox,
                "centroid": center,
                "locatedOn": located_on,
                "adjacentTo": adjacent,
                "width": {"value": clean_float(max(bbox[2], bbox[3])), "unit": "svg_user_unit"},
                "orientation": orientation_from_bbox(bbox),
                "openable": "unknown",
                "openingDirection": "unknown",
                "daylightSource": True,
                "ventilationSource": True,
                "status": status,
                "confidence": confidence,
                "evidence": evidence,
            }
        )
    return windows


def nearest_wall_id(bbox: Sequence[float], walls: List[Dict]) -> Optional[str]:
    if not walls:
        return None
    nearest = min(walls, key=lambda wall: distance_between_bboxes(bbox, wall.get("bbox") or [0, 0, 0, 0]))
    if distance_between_bboxes(bbox, nearest.get("bbox") or [0, 0, 0, 0]) <= 25:
        return nearest["id"]
    return None


def nearest_space_ids_to_bbox(bbox: Sequence[float], spaces: List[Dict], max_count: int = 2) -> List[str]:
    center = Point(*bbox_center(bbox))
    distances = []
    for space in spaces:
        geom = space.get("_shape")
        if geom is not None:
            distances.append((float(geom.distance(center)), space["id"]))
    distances.sort(key=lambda item: item[0])
    return [space_id for distance, space_id in distances[:max_count] if distance <= 80]


def build_door_entities(vector_nodes: List[Dict], spaces: List[Dict], shape_cache: Dict[str, object]) -> List[Dict]:
    swing_nodes = [node for node in vector_nodes if has_category(node, "door_swing_candidate")]
    leaf_nodes = [node for node in vector_nodes if has_category(node, "door_leaf_candidate")]
    doors = []
    for idx, swing_node in enumerate(swing_nodes, start=1):
        d = swing_node.get("rawAttributes", {}).get("d", "")
        parsed = parse_quadratic_door_swing(d)
        leaf = nearest_leaf(swing_node, leaf_nodes)
        swing_geom = shape_cache.get(swing_node["id"])
        centroid = swing_node.get("centroid") or bbox_center(swing_node.get("bbox") or [0, 0, 0, 0])
        opens_into = infer_opens_into(centroid, spaces)
        connects = nearest_space_ids_to_geometry(swing_geom, spaces, max_count=2)
        if opens_into and opens_into not in connects:
            connects = [opens_into] + connects
        connects = list(dict.fromkeys(connects))[:2]
        evidence = ["quadratic_swing_sector"]
        status = "inferred"
        confidence = 0.67
        if parsed:
            evidence.append("parsed_hinge_and_swing")
        else:
            status = "needs_review"
            confidence = 0.45
        if leaf:
            evidence.append("near_door_leaf")
        else:
            status = "needs_review"
            confidence = min(confidence, 0.55)

        doors.append(
            {
                "id": f"door_{idx:04d}",
                "type": "Door",
                "subtype": "SwingDoorCandidate",
                "geometryRefs": [swing_node["id"]] + ([leaf["id"]] if leaf else []),
                "bbox": swing_node.get("bbox"),
                "centroid": centroid,
                "hingePoint": parsed.get("hingePoint") if parsed else None,
                "swingArc": parsed.get("swingArc") if parsed else None,
                "swingDirection": parsed.get("swingDirection") if parsed else "unknown",
                "opensInto": opens_into or "unknown",
                "connects": connects,
                "clearWidth": parsed.get("clearWidth") if parsed else None,
                "status": status,
                "confidence": confidence,
                "evidence": evidence,
            }
        )
    return doors


def parse_quadratic_door_swing(d: str) -> Optional[Dict]:
    tokens = re.findall(r"[A-Za-z]|[-+]?(?:\d*\.\d+|\d+)", d or "")
    if not tokens:
        return None
    try:
        if tokens[0] not in {"M", "m"}:
            return None
        x0, y0 = float(tokens[1]), float(tokens[2])
        q_idx = next(idx for idx, token in enumerate(tokens) if token in {"q", "Q"})
        q_relative = tokens[q_idx] == "q"
        q_nums = [float(tokens[q_idx + offset]) for offset in range(1, 5)]
        if q_relative:
            x1 = x0 + q_nums[2]
            y1 = y0 + q_nums[3]
        else:
            x1, y1 = q_nums[2], q_nums[3]
        next_idx = q_idx + 5
        command = tokens[next_idx]
        value = float(tokens[next_idx + 1])
        if command == "h":
            hinge = (x1 + value, y1)
        elif command == "H":
            hinge = (value, y1)
        elif command == "v":
            hinge = (x1, y1 + value)
        elif command == "V":
            hinge = (x1, value)
        else:
            return None
        clear_width = max(math.dist((x0, y0), hinge), math.dist((x1, y1), hinge))
        direction = swing_direction(hinge, (x0, y0), (x1, y1))
        return {
            "hingePoint": [clean_float(hinge[0]), clean_float(hinge[1])],
            "swingArc": {
                "start": [clean_float(x0), clean_float(y0)],
                "end": [clean_float(x1), clean_float(y1)],
                "radius": clean_float(clear_width),
            },
            "swingDirection": direction,
            "clearWidth": {"value": clean_float(clear_width), "unit": "svg_user_unit"},
        }
    except Exception:
        return None


def swing_direction(hinge: Tuple[float, float], start: Tuple[float, float], end: Tuple[float, float]) -> str:
    start_angle = math.atan2(start[1] - hinge[1], start[0] - hinge[0])
    end_angle = math.atan2(end[1] - hinge[1], end[0] - hinge[0])
    delta = end_angle - start_angle
    while delta <= -math.pi:
        delta += 2 * math.pi
    while delta > math.pi:
        delta -= 2 * math.pi
    if abs(delta) < 0.05:
        return "unknown"
    return "clockwise" if delta > 0 else "counterclockwise"


def nearest_leaf(swing_node: Dict, leaf_nodes: List[Dict]) -> Optional[Dict]:
    bbox = swing_node.get("bbox")
    if not bbox or not leaf_nodes:
        return None
    nearest = min(leaf_nodes, key=lambda node: distance_between_bboxes(bbox, node.get("bbox") or [0, 0, 0, 0]))
    return nearest if distance_between_bboxes(bbox, nearest.get("bbox") or [0, 0, 0, 0]) <= 30 else None


def infer_opens_into(centroid: Sequence[float], spaces: List[Dict]) -> Optional[str]:
    point = Point(centroid[0], centroid[1])
    containing = []
    for space in spaces:
        geom = space.get("_shape")
        if geom is not None and (geom.contains(point) or geom.touches(point)):
            containing.append(space)
    if containing:
        containing.sort(key=lambda space: float(space.get("_shape").area))
        return containing[0]["id"]
    return nearest_space_to_point(point, spaces)


def nearest_space_to_point(point: Point, spaces: List[Dict]) -> Optional[str]:
    distances = []
    for space in spaces:
        geom = space.get("_shape")
        if geom is not None:
            distances.append((float(geom.distance(point)), space["id"]))
    if not distances:
        return None
    distances.sort(key=lambda item: item[0])
    return distances[0][1] if distances[0][0] <= 100 else None


def nearest_space_ids_to_geometry(geom: object, spaces: List[Dict], max_count: int = 2) -> List[str]:
    if geom is None:
        return []
    distances = []
    for space in spaces:
        space_geom = space.get("_shape")
        if space_geom is not None:
            distances.append((float(space_geom.distance(geom)), space["id"]))
    distances.sort(key=lambda item: item[0])
    return [space_id for distance, space_id in distances[:max_count] if distance <= 80]


def nearest_walls_for_space(space: Dict, walls: List[Dict], shape_cache: Dict[str, object]) -> List[Dict]:
    geom = space.get("_shape")
    if geom is None or not walls:
        return []
    scored = []
    for wall in walls:
        wall_geom = wall_computed_shape(wall) or shape_cache.get(wall.get("geometryRefs", [None])[0])
        if wall_geom is not None:
            scored.append((float(geom.distance(wall_geom)), wall))
    scored.sort(key=lambda item: item[0])
    return [wall for distance, wall in scored[:6] if distance <= 20]


def wall_computed_shape(wall: Dict) -> Optional[LineString]:
    points = wall.get("computedGeometry", {}).get("points") or []
    if len(points) < 2:
        return None
    try:
        return LineString(points)
    except Exception:
        return None


def strip_private_shapes(entities: Iterable[Dict]) -> List[Dict]:
    cleaned = []
    for entity in entities:
        item = dict(entity)
        item.pop("_shape", None)
        cleaned.append(item)
    return cleaned
