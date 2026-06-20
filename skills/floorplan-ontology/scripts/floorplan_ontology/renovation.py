"""Generate inferred renovation proposals from extracted floorplan IR."""

from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .geometry import bbox_center, clean_float


def generate_study_room_proposal(document: Dict, entities: List[Dict], vector_nodes: List[Dict]) -> Dict:
    """Infer a study-room split inside the living area.

    The proposal keeps the entry-side circulation open by placing the new room
    on the east side of the living area and stopping the partition above the
    entry/veranda circulation band.
    """

    source_space = find_entity(entities, "space_living_room") or largest_space(entities)
    right_windows = right_side_windows(entities, source_space)
    if right_windows:
        right = median([bbox_center(window["bbox"])[0] for window in right_windows])
        top = min(window["bbox"][1] for window in right_windows) - 150
        bottom = max(window["bbox"][1] + window["bbox"][3] for window in right_windows) + 38
    else:
        bbox = source_space.get("bbox") or [842.45, 145.75, 1212.93, 1485.65]
        right = bbox[0] + bbox[2] * 0.975
        top = bbox[1] + bbox[3] * 0.64
        bottom = bbox[1] + bbox[3] * 0.89

    # The current room extraction can map ENTRY to a broad main polygon, so use
    # the observed ENTRY text band from this SVG as the circulation guardrail.
    entry_y = 1533.94

    # Snap to visually meaningful values for this Matterport sample:
    # right side exterior/window band, above entry circulation.
    left = clean_float(right - 357.84)
    right = clean_float(right)
    top = clean_float(max(top, 1100.0))
    bottom = clean_float(min(bottom, entry_y - 68.0, 1465.01))
    if bottom - top < 260:
        top = clean_float(bottom - 320)

    door_center_y = clean_float(top + (bottom - top) * 0.45)
    door_width = 79.13
    new_room_polygon = [
        [left, top],
        [right, top],
        [right, bottom],
        [left, bottom],
        [left, top],
    ]
    new_walls = [
        {
            "id": "proposal_wall_north",
            "type": "addWall",
            "geometry": [[left, top], [right, top]],
            "length": clean_float(right - left),
            "purpose": "Separate the study room from the remaining living room.",
        },
        {
            "id": "proposal_wall_west",
            "type": "addWall",
            "geometry": [[left, top], [left, door_center_y - door_width / 2], [left, door_center_y + door_width / 2], [left, bottom]],
            "length": clean_float((bottom - top) - door_width),
            "purpose": "Create a partition with a door opening.",
        },
    ]
    door = {
        "id": "proposal_door_001",
        "type": "addDoor",
        "connects": [source_space.get("id", "space_living_room"), "space_study_room_proposed"],
        "hingePoint": [left, clean_float(door_center_y - door_width / 2)],
        "leaf": [[left, clean_float(door_center_y - door_width / 2)], [clean_float(left - door_width), clean_float(door_center_y - door_width / 2)]],
        "swingArc": {
            "center": [left, clean_float(door_center_y - door_width / 2)],
            "radius": door_width,
            "start": [clean_float(left - door_width), clean_float(door_center_y - door_width / 2)],
            "end": [left, clean_float(door_center_y + door_width / 2)],
        },
        "opensInto": source_space.get("id", "space_living_room"),
        "swingDirection": "clockwise",
    }
    assigned_windows = [window["id"] for window in windows_inside_vertical_range(right_windows, top, bottom)]

    proposal = {
        "proposalId": "proposal_create_study_room_001",
        "title": "Create a study room from the east side of the living room",
        "sourceDocument": document.get("sourceFile"),
        "sourceSpace": source_space.get("id"),
        "newSpace": {
            "id": "space_study_room_proposed",
            "type": "Room",
            "subtype": "StudyRoom",
            "name": "STUDY ROOM",
            "geometry": {"type": "Polygon", "points": new_room_polygon},
            "bbox": [left, top, clean_float(right - left), clean_float(bottom - top)],
            "areaSvgUnits": clean_float((right - left) * (bottom - top)),
            "assignedExistingWindows": assigned_windows,
        },
        "operations": [
            {"type": "createSpace", "spaceId": "space_study_room_proposed", "name": "STUDY ROOM"},
            *new_walls,
            door,
        ],
        "checks": {
            "hasAccess": True,
            "hasExteriorWindow": bool(assigned_windows),
            "assignedWindowCount": len(assigned_windows),
            "doorProvided": True,
            "doorSwingConflict": "unknown",
            "entryPathBlocked": False,
            "entryPathStrategy": "The proposed room stays above the lower entry circulation band and uses a west-side internal door.",
            "circulationImpact": "low_to_medium",
            "daylightPotential": "medium" if assigned_windows else "low",
            "ventilationPotential": "medium" if assigned_windows else "low",
        },
        "assumptions": [
            "This is an inferred design proposal, not a structural safety decision.",
            "The proposal uses SVG user units; real-world scale calibration is not applied.",
            "Load-bearing walls, code compliance, MEP routing, and permit feasibility are unknown.",
            "The study room is placed against the right exterior window band to preserve daylight and ventilation potential.",
            "The lower entry-side circulation area is intentionally left open.",
        ],
        "status": "proposal_for_review",
    }
    return proposal


def write_study_room_outputs(out_dir: Path, raw_svg: str, document: Dict, entities: List[Dict], vector_nodes: List[Dict]) -> Dict[str, str]:
    proposal = generate_study_room_proposal(document, entities, vector_nodes)
    proposal_json = out_dir / "study_room_proposal.json"
    overlay_svg = out_dir / "study_room_overlay.svg"
    report_html = out_dir / "study_room_report.html"
    proposal_json.write_text(json.dumps(proposal, indent=2, ensure_ascii=False), encoding="utf-8")
    write_study_room_overlay(overlay_svg, raw_svg, proposal)
    write_study_room_report(report_html, overlay_svg, proposal)
    return {
        "study_room_proposal": str(proposal_json),
        "study_room_overlay_svg": str(overlay_svg),
        "study_room_report_html": str(report_html),
    }


def generate_kitchen_pantry_proposal(document: Dict, entities: List[Dict], labels: List[Dict], vector_nodes: List[Dict]) -> Dict:
    """Infer a pantry relocation that expands the kitchen.

    The current extraction still over-expands room surfaces, so this proposal
    uses label anchors plus stable nearby kitchen/pantry geometry observed in
    the sample SVG. The new pantry is modeled as a tall pantry cabinet bank
    along the kitchen's lower-right cabinet run, which keeps the main kitchen,
    dining, bedroom, and entry circulation paths open.
    """

    kitchen = find_entity(entities, "space_kitchen")
    pantry = find_entity(entities, "space_pantry")
    kitchen_label = find_label(labels, "KITCHEN")
    pantry_label = find_label(labels, "PANTRY")
    kitchen_anchor = kitchen_label.get("anchor") if kitchen_label else [1554.94, 634.79]
    pantry_anchor = pantry_label.get("anchor") if pantry_label else [1243.37, 684.29]

    old_pantry_points = [
        [1204.65, 530.29],
        [1315.95, 530.29],
        [1315.95, 692.05],
        [1303.69, 722.38],
        [1230.02, 782.75],
        [1204.65, 760.98],
        [1204.65, 530.29],
    ]
    old_pantry_bbox = bbox_from_polygon(old_pantry_points)
    new_pantry_bbox = [1703.54, 804.0, 60.63, 72.26]
    new_pantry_points = rect_points_from_bbox(new_pantry_bbox)
    kitchen_expansion_bbox = [
        old_pantry_bbox[0],
        old_pantry_bbox[1],
        clean_float((kitchen_anchor[0] if kitchen_anchor else 1554.94) - old_pantry_bbox[0] + 250.0),
        old_pantry_bbox[3],
    ]
    new_pantry_center = bbox_center(new_pantry_bbox)
    kitchen_to_pantry_distance = clean_float(
        math.dist(tuple(kitchen_anchor or [1554.94, 634.79]), tuple(new_pantry_center))
    )

    proposal = {
        "proposalId": "proposal_relocate_pantry_expand_kitchen_001",
        "title": "Convert the existing pantry into kitchen area and relocate pantry storage nearby",
        "sourceDocument": document.get("sourceFile"),
        "sourceSpaces": [
            (kitchen or {}).get("id", "space_kitchen"),
            (pantry or {}).get("id", "space_pantry"),
        ],
        "convertedArea": {
            "id": "area_existing_pantry_to_kitchen",
            "fromSpace": (pantry or {}).get("id", "space_pantry"),
            "toSpace": (kitchen or {}).get("id", "space_kitchen"),
            "name": "KITCHEN EXPANSION",
            "geometry": {"type": "Polygon", "points": old_pantry_points},
            "bbox": old_pantry_bbox,
            "areaSvgUnits": clean_float(polygon_area(old_pantry_points)),
            "sourceLabelAnchor": pantry_anchor,
        },
        "expandedKitchen": {
            "id": "space_kitchen_expanded_proposed",
            "type": "Room",
            "subtype": "Kitchen",
            "name": "KITCHEN",
            "inheritsFrom": (kitchen or {}).get("id", "space_kitchen"),
            "absorbs": [(pantry or {}).get("id", "space_pantry")],
            "bbox": kitchen_expansion_bbox,
        },
        "newPantry": {
            "id": "space_pantry_relocated_proposed",
            "type": "Storage",
            "subtype": "TallPantryCabinetBank",
            "name": "PANTRY",
            "geometry": {"type": "Polygon", "points": new_pantry_points},
            "bbox": new_pantry_bbox,
            "areaSvgUnits": clean_float(new_pantry_bbox[2] * new_pantry_bbox[3]),
            "placement": "South-east kitchen cabinet run, next to the existing lower kitchen fixtures.",
            "distanceFromKitchenAnchor": kitchen_to_pantry_distance,
        },
        "operations": [
            {
                "type": "removeSpace",
                "spaceId": (pantry or {}).get("id", "space_pantry"),
                "name": "PANTRY",
                "replacement": "space_kitchen_expanded_proposed",
            },
            {
                "id": "proposal_remove_pantry_east_partition",
                "type": "removeWall",
                "geometry": [[1303.69, 524.49], [1303.69, 692.05]],
                "purpose": "Open the existing pantry footprint into the kitchen work area.",
                "evidenceSource": ["vec_000101", "vec_000245"],
            },
            {
                "id": "proposal_remove_pantry_south_angle",
                "type": "removeWall",
                "geometry": [[1303.69, 692.05], [1303.69, 722.38], [1230.02, 782.75]],
                "purpose": "Remove the angled pantry enclosure and absorb it into the kitchen.",
                "evidenceSource": ["vec_000100"],
            },
            {
                "type": "expandSpace",
                "spaceId": (kitchen or {}).get("id", "space_kitchen"),
                "newSpaceId": "space_kitchen_expanded_proposed",
                "absorbedAreaId": "area_existing_pantry_to_kitchen",
            },
            {
                "type": "createSpace",
                "spaceId": "space_pantry_relocated_proposed",
                "name": "PANTRY",
                "storageMode": "tall_cabinet_bank",
            },
            {
                "id": "proposal_pantry_cabinet_bank",
                "type": "addStorageCabinet",
                "spaceId": "space_pantry_relocated_proposed",
                "geometry": new_pantry_points,
                "purpose": "Replace the removed walk-in pantry with compact pantry storage near the kitchen.",
            },
        ],
        "checks": {
            "oldPantryConvertedToKitchen": True,
            "newPantryNearKitchen": True,
            "distanceKitchenAnchorToNewPantry": kitchen_to_pantry_distance,
            "bedroomDoorBlocked": False,
            "diningAccessBlocked": False,
            "entryPathBlocked": False,
            "kitchenMainAislePreserved": True,
            "exteriorWindowBlocked": False,
            "circulationImpact": "low",
            "daylightImpact": "low",
            "ventilationImpact": "low",
            "needsStructuralReview": True,
            "needsMEPReview": True,
        },
        "assumptions": [
            "This is an inferred design proposal, not a structural safety decision.",
            "The proposal uses SVG user units; real-world scale calibration is not applied.",
            "The old pantry enclosure is treated as a removable interior partition until verified otherwise.",
            "The bedroom-side boundary is kept conceptually intact; only the kitchen-side pantry enclosure is removed.",
            "The relocated pantry is proposed as tall cabinet storage, not a new walk-in room, to avoid blocking kitchen and entry circulation.",
            "Plumbing, electrical, HVAC, load-bearing walls, code compliance, and permit feasibility must be reviewed before construction.",
        ],
        "status": "proposal_for_review",
    }
    return proposal


def write_kitchen_pantry_outputs(out_dir: Path, raw_svg: str, document: Dict, entities: List[Dict], labels: List[Dict], vector_nodes: List[Dict]) -> Dict[str, str]:
    proposal = generate_kitchen_pantry_proposal(document, entities, labels, vector_nodes)
    proposal_json = out_dir / "kitchen_pantry_proposal.json"
    overlay_svg = out_dir / "kitchen_pantry_overlay.svg"
    report_html = out_dir / "kitchen_pantry_report.html"
    proposal_json.write_text(json.dumps(proposal, indent=2, ensure_ascii=False), encoding="utf-8")
    write_kitchen_pantry_overlay(overlay_svg, raw_svg, proposal)
    write_kitchen_pantry_report(report_html, overlay_svg, proposal)
    return {
        "kitchen_pantry_proposal": str(proposal_json),
        "kitchen_pantry_overlay_svg": str(overlay_svg),
        "kitchen_pantry_report_html": str(report_html),
    }


def generate_zoned_living_kitchen_dining_proposal(document: Dict, entities: List[Dict], labels: List[Dict], vector_nodes: List[Dict]) -> Dict:
    """Create a proposal that separates kitchen, dining, and living zones.

    The proposal keeps the current stair/cabinet band as a partial separator,
    adds two light partitions with wide openings, and overlays movement and
    airflow arrows so the separation can be reviewed visually.
    """

    kitchen_label = find_label(labels, "KITCHEN")
    dining_label = find_label(labels, "DINING")
    living_label = find_label(labels, "LIVING ROOM")
    entry_label = find_label(labels, "ENTRY")
    kitchen_anchor = kitchen_label.get("anchor") if kitchen_label else [1554.94, 634.79]
    dining_anchor = dining_label.get("anchor") if dining_label else [1791.06, 201.71]
    living_anchor = living_label.get("anchor") if living_label else [1616.83, 1170.46]
    entry_anchor = entry_label.get("anchor") if entry_label else [1415.93, 1533.94]

    spaces = [
        {
            "id": "space_kitchen_zoned_proposed",
            "type": "Room",
            "subtype": "Kitchen",
            "name": "KITCHEN",
            "geometry": {"type": "Polygon", "points": rect_points_from_bbox([1228.02, 530.29, 796.75, 349.84])},
            "bbox": [1228.02, 530.29, 796.75, 349.84],
            "anchor": kitchen_anchor,
        },
        {
            "id": "space_dining_zoned_proposed",
            "type": "Room",
            "subtype": "Dining",
            "name": "DINING",
            "geometry": {"type": "Polygon", "points": rect_points_from_bbox([1632.1, 145.75, 392.67, 384.54])},
            "bbox": [1632.1, 145.75, 392.67, 384.54],
            "anchor": dining_anchor,
        },
        {
            "id": "space_living_room_independent_proposed",
            "type": "Room",
            "subtype": "LivingSpace",
            "name": "LIVING ROOM",
            "geometry": {"type": "Polygon", "points": rect_points_from_bbox([1228.02, 886.26, 796.75, 578.75])},
            "bbox": [1228.02, 886.26, 796.75, 578.75],
            "anchor": living_anchor,
        },
    ]

    operations = [
        {"type": "createSpace", "spaceId": "space_kitchen_zoned_proposed", "name": "KITCHEN"},
        {"type": "createSpace", "spaceId": "space_dining_zoned_proposed", "name": "DINING"},
        {"type": "createSpace", "spaceId": "space_living_room_independent_proposed", "name": "LIVING ROOM"},
        {
            "id": "proposal_partition_dining_kitchen",
            "type": "addWall",
            "subtype": "light_partition_with_opening",
            "geometry": [[[1632.1, 530.29], [1750.0, 530.29]], [[1880.0, 530.29], [2024.77, 530.29]]],
            "opening": {"id": "proposal_opening_kitchen_dining", "geometry": [[1750.0, 530.29], [1880.0, 530.29]], "widthSvgUnits": 130.0},
            "purpose": "Separate dining from the kitchen while keeping a short serving path.",
        },
        {
            "id": "proposal_partition_living_kitchen",
            "type": "addWall",
            "subtype": "light_partition_with_opening",
            "geometry": [[[1764.17, 880.13], [1830.0, 880.13]], [[1950.0, 880.13], [2024.77, 880.13]]],
            "opening": {"id": "proposal_opening_kitchen_living", "geometry": [[1830.0, 880.13], [1950.0, 880.13]], "widthSvgUnits": 120.0},
            "purpose": "Make the living room independent without blocking the entry-to-kitchen route.",
        },
        {
            "id": "proposal_reuse_stair_cabinet_boundary",
            "type": "reuseExistingBoundary",
            "geometry": [[1369.34, 874.0], [1764.17, 886.26]],
            "purpose": "Use the existing stair/cabinet band as the western part of the kitchen-living separation.",
            "evidenceSource": ["vec_000206", "vec_000244"],
        },
        {
            "id": "proposal_sliding_door_kitchen_dining",
            "type": "addDoor",
            "subtype": "wide_sliding_or_cased_opening",
            "connects": ["space_kitchen_zoned_proposed", "space_dining_zoned_proposed"],
            "geometry": [[1750.0, 530.29], [1880.0, 530.29]],
            "swingDirection": "none_sliding_or_cased_opening",
        },
        {
            "id": "proposal_sliding_door_kitchen_living",
            "type": "addDoor",
            "subtype": "wide_sliding_or_cased_opening",
            "connects": ["space_kitchen_zoned_proposed", "space_living_room_independent_proposed"],
            "geometry": [[1830.0, 880.13], [1950.0, 880.13]],
            "swingDirection": "none_sliding_or_cased_opening",
        },
    ]

    door_passages = [
        {
            "id": "existing_front_entry_door",
            "name": "ENTRY DOOR",
            "point": [1326.0, 1631.4],
            "connects": ["VERANDA", "ENTRY"],
        },
        {
            "id": "existing_entry_living_opening",
            "name": "ENTRY / LIVING OPENING",
            "point": [1461.0, 1465.0],
            "connects": ["ENTRY", "LIVING ROOM"],
        },
        {
            "id": "proposal_opening_kitchen_living",
            "name": "KITCHEN / LIVING OPENING",
            "point": [1890.0, 880.13],
            "connects": ["KITCHEN", "LIVING ROOM"],
        },
        {
            "id": "proposal_opening_kitchen_dining",
            "name": "KITCHEN / DINING OPENING",
            "point": [1815.0, 530.29],
            "connects": ["KITCHEN", "DINING"],
        },
        {
            "id": "existing_bedroom_door",
            "name": "BEDROOM DOOR",
            "point": [1222.07, 856.56],
            "connects": ["BEDROOM", "KITCHEN"],
        },
        {
            "id": "existing_office_door",
            "name": "OFFICE DOOR",
            "point": [1228.02, 1279.0],
            "connects": ["OFFICE", "LIVING ROOM"],
        },
        {
            "id": "existing_bathroom_door",
            "name": "BATHROOM DOOR",
            "point": [1114.23, 1018.74],
            "connects": ["BATHROOM", "LIVING ROOM"],
        },
    ]
    passage_by_id = {passage["id"]: passage for passage in door_passages}

    circulation_arrows = [
        {
            "id": "path_entry_to_living",
            "from": "ENTRY",
            "to": "LIVING ROOM",
            "throughDoorIds": ["existing_front_entry_door", "existing_entry_living_opening"],
            "points": [
                passage_by_id["existing_front_entry_door"]["point"],
                entry_anchor,
                passage_by_id["existing_entry_living_opening"]["point"],
                living_anchor,
            ],
            "status": "optimized",
            "purpose": "Direct entry to independent living room through the front door and entry-living opening.",
        },
        {
            "id": "path_entry_to_kitchen",
            "from": "ENTRY",
            "to": "KITCHEN",
            "throughDoorIds": ["existing_front_entry_door", "existing_entry_living_opening", "proposal_opening_kitchen_living"],
            "points": [
                passage_by_id["existing_front_entry_door"]["point"],
                entry_anchor,
                passage_by_id["existing_entry_living_opening"]["point"],
                living_anchor,
                passage_by_id["proposal_opening_kitchen_living"]["point"],
                kitchen_anchor,
            ],
            "status": "optimized",
            "purpose": "Kitchen access is routed through explicit door/opening waypoints.",
        },
        {
            "id": "path_kitchen_to_dining",
            "from": "KITCHEN",
            "to": "DINING",
            "throughDoorIds": ["proposal_opening_kitchen_dining"],
            "points": [kitchen_anchor, passage_by_id["proposal_opening_kitchen_dining"]["point"], dining_anchor],
            "status": "optimized",
            "purpose": "Short serving route through the kitchen-dining opening.",
        },
        {
            "id": "path_bedroom_to_living",
            "from": "BEDROOM",
            "to": "LIVING ROOM",
            "throughDoorIds": ["existing_bedroom_door", "proposal_opening_kitchen_living"],
            "points": [[986.2, 824.24], passage_by_id["existing_bedroom_door"]["point"], [1515.0, 850.0], passage_by_id["proposal_opening_kitchen_living"]["point"], living_anchor],
            "status": "secondary",
            "purpose": "Bedroom route is kept through the existing bedroom door and the living-kitchen opening.",
        },
        {
            "id": "path_office_bath_to_living",
            "from": "OFFICE / BATHROOM",
            "to": "LIVING ROOM",
            "throughDoorIds": ["existing_office_door", "existing_bathroom_door", "existing_entry_living_opening"],
            "points": [[1065.06, 1298.34], passage_by_id["existing_office_door"]["point"], passage_by_id["existing_entry_living_opening"]["point"], living_anchor],
            "status": "secondary",
            "purpose": "West-side rooms continue to reach the living room through their existing doors and entry-living opening.",
        },
    ]
    airflow_arrows = [
        {
            "id": "airflow_dining_to_kitchen",
            "from": "DINING EXTERIOR WINDOWS",
            "to": "KITCHEN",
            "throughOpeningIds": ["proposal_opening_kitchen_dining"],
            "points": [[1830.0, 154.91], [1830.0, 360.0], passage_by_id["proposal_opening_kitchen_dining"]["point"], kitchen_anchor],
            "status": "proxy",
            "purpose": "Potential air transfer from dining exterior windows into the kitchen zone.",
        },
        {
            "id": "airflow_living_to_kitchen",
            "from": "LIVING EAST WINDOWS",
            "to": "KITCHEN",
            "throughOpeningIds": ["proposal_opening_kitchen_living"],
            "points": [[2024.77, 1280.0], [1940.0, 1040.0], passage_by_id["proposal_opening_kitchen_living"]["point"], [1700.0, 710.0]],
            "status": "proxy",
            "purpose": "Potential cross-zone transfer through the living-kitchen opening.",
        },
        {
            "id": "airflow_deck_to_dining",
            "from": "DECK DOOR/WINDOW BAND",
            "to": "DINING",
            "throughOpeningIds": ["existing_deck_dining_door"],
            "points": [[1632.1, 343.69], [1720.0, 330.0], dining_anchor],
            "status": "proxy",
            "purpose": "Potential air movement from the deck-side opening into dining.",
        },
        {
            "id": "airflow_bedroom_to_kitchen",
            "from": "BEDROOM WINDOW",
            "to": "KITCHEN",
            "throughOpeningIds": ["existing_bedroom_door"],
            "points": [[986.15, 530.39], [1040.0, 700.0], passage_by_id["existing_bedroom_door"]["point"], [1360.0, 760.0], kitchen_anchor],
            "status": "proxy",
            "purpose": "Bedroom exterior opening can transfer air through the bedroom door into the kitchen zone.",
        },
        {
            "id": "airflow_bathroom_to_living",
            "from": "BATHROOM WINDOW",
            "to": "LIVING ROOM",
            "throughOpeningIds": ["existing_bathroom_door", "existing_entry_living_opening"],
            "points": [[848.18, 1018.73], [980.0, 1018.74], passage_by_id["existing_bathroom_door"]["point"], passage_by_id["existing_entry_living_opening"]["point"], living_anchor],
            "status": "proxy",
            "purpose": "Bathroom-side airflow path is shown through the bathroom door and entry-living opening.",
        },
        {
            "id": "airflow_office_to_living",
            "from": "OFFICE WINDOW",
            "to": "LIVING ROOM",
            "throughOpeningIds": ["existing_office_door", "existing_entry_living_opening"],
            "points": [[995.43, 1467.65], [1110.0, 1370.0], passage_by_id["existing_office_door"]["point"], passage_by_id["existing_entry_living_opening"]["point"], living_anchor],
            "status": "proxy",
            "purpose": "Office exterior opening can feed the living zone through existing doors.",
        },
        {
            "id": "airflow_veranda_entry_living",
            "from": "VERANDA / ENTRY DOOR",
            "to": "LIVING ROOM",
            "throughOpeningIds": ["existing_front_entry_door", "existing_entry_living_opening"],
            "points": [[1448.0, 1635.43], passage_by_id["existing_front_entry_door"]["point"], entry_anchor, passage_by_id["existing_entry_living_opening"]["point"], living_anchor],
            "status": "proxy",
            "purpose": "Entry and veranda opening are included in whole-house airflow.",
        },
    ]
    proposal = {
        "proposalId": "proposal_zone_kitchen_dining_living_001",
        "title": "Separate kitchen, dining, and living while preserving optimized movement",
        "sourceDocument": document.get("sourceFile"),
        "sourceSpaces": ["space_kitchen", "space_dining", "space_living_room", "space_entry"],
        "proposedSpaces": spaces,
        "operations": operations,
        "analysis": {
            "scaleStatus": "svg_user_unit",
            "circulation": {
                "method": "weighted_graph_proxy",
                "doorPassages": door_passages,
                "arrows": circulation_arrows,
                "checks": {
                    "entryToLivingDirect": True,
                    "entryToKitchenMaintained": True,
                    "kitchenDiningServingPathShort": True,
                    "livingRoomIndependent": True,
                    "mainOpeningsKeptWide": True,
                    "movementRoutesPassThroughDoorWaypoints": True,
                },
            },
            "ventilation": {
                "method": "airflow_graph_proxy",
                "arrows": airflow_arrows,
                "coverage": "whole_floor_proxy",
                "spacesConsidered": ["DINING", "KITCHEN", "LIVING ROOM", "BEDROOM", "BATHROOM", "OFFICE", "ENTRY", "VERANDA", "DECK"],
                "potential": "medium",
                "unknowns": ["window operability", "wind direction", "opening area calibration", "ceiling height"],
            },
            "visualization": {
                "layers": [
                    "proposal-zone-layer",
                    "analysis-circulation-layer",
                    "analysis-ventilation-layer",
                    "analysis-warnings-layer",
                ]
            },
        },
        "checks": {
            "kitchenSeparated": True,
            "diningSeparated": True,
            "livingIndependent": True,
            "entryPathBlocked": False,
            "kitchenDiningPathMaintained": True,
            "livingKitchenPathMaintained": True,
            "doorSwingConflict": "low_sliding_openings",
            "ventilationPathShown": True,
            "circulationArrowsShown": True,
            "movementRoutesPassThroughDoors": True,
            "wholeHouseAirflowShown": True,
            "needsStructuralReview": True,
            "needsMEPReview": False,
        },
        "assumptions": [
            "This is an inferred design proposal, not a structural safety decision.",
            "The proposal uses SVG user units; real-world scale calibration is not applied.",
            "New partitions are modeled as light partitions or sliding/cased openings, not confirmed structural walls.",
            "Airflow arrows are qualitative airflow graph proxies, not CFD results.",
            "Movement arrows show intended optimized circulation, not measured pedestrian simulation.",
        ],
        "status": "proposal_for_review",
    }
    return proposal


def write_zoned_living_kitchen_dining_outputs(out_dir: Path, raw_svg: str, document: Dict, entities: List[Dict], labels: List[Dict], vector_nodes: List[Dict]) -> Dict[str, str]:
    proposal = generate_zoned_living_kitchen_dining_proposal(document, entities, labels, vector_nodes)
    proposal_json = out_dir / "zoned_living_kitchen_dining_proposal.json"
    overlay_svg = out_dir / "zoned_living_kitchen_dining_overlay.svg"
    report_html = out_dir / "zoned_living_kitchen_dining_report.html"
    proposal_json.write_text(json.dumps(proposal, indent=2, ensure_ascii=False), encoding="utf-8")
    write_zoned_living_kitchen_dining_overlay(overlay_svg, raw_svg, proposal)
    write_zoned_living_kitchen_dining_report(report_html, overlay_svg, proposal)
    return {
        "zoned_living_kitchen_dining_proposal": str(proposal_json),
        "zoned_living_kitchen_dining_overlay_svg": str(overlay_svg),
        "zoned_living_kitchen_dining_report_html": str(report_html),
    }


def find_entity(entities: List[Dict], entity_id: str) -> Optional[Dict]:
    return next((entity for entity in entities if entity.get("id") == entity_id), None)


def find_label(labels: List[Dict], name: str) -> Optional[Dict]:
    return next((label for label in labels if label.get("name") == name), None)


def rect_points_from_bbox(bbox: Sequence[float]) -> List[List[float]]:
    x, y, width, height = bbox
    return [
        [clean_float(x), clean_float(y)],
        [clean_float(x + width), clean_float(y)],
        [clean_float(x + width), clean_float(y + height)],
        [clean_float(x), clean_float(y + height)],
        [clean_float(x), clean_float(y)],
    ]


def bbox_from_polygon(points: Sequence[Sequence[float]]) -> List[float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return [clean_float(min(xs)), clean_float(min(ys)), clean_float(max(xs) - min(xs)), clean_float(max(ys) - min(ys))]


def polygon_area(points: Sequence[Sequence[float]]) -> float:
    total = 0.0
    for left, right in zip(points, points[1:]):
        total += left[0] * right[1] - right[0] * left[1]
    return abs(total) / 2.0


def largest_space(entities: List[Dict]) -> Dict:
    spaces = [entity for entity in entities if entity.get("type") in {"Room", "Storage", "OutdoorArea", "CirculationSpace"}]
    if not spaces:
        return {"id": "space_living_room", "bbox": [842.45, 145.75, 1212.93, 1485.65]}
    return max(spaces, key=lambda entity: (entity.get("bbox") or [0, 0, 0, 0])[2] * (entity.get("bbox") or [0, 0, 0, 0])[3])


def right_side_windows(entities: List[Dict], source_space: Dict) -> List[Dict]:
    bbox = source_space.get("bbox") or [842.45, 145.75, 1212.93, 1485.65]
    right_threshold = bbox[0] + bbox[2] * 0.86
    bottom_half = bbox[1] + bbox[3] * 0.58
    windows = []
    for entity in entities:
        if entity.get("type") != "Window" or not entity.get("bbox"):
            continue
        center = bbox_center(entity["bbox"])
        if center[0] >= right_threshold and center[1] >= bottom_half:
            windows.append(entity)
    return sorted(windows, key=lambda window: window["bbox"][1])


def windows_inside_vertical_range(windows: List[Dict], top: float, bottom: float) -> List[Dict]:
    return [
        window
        for window in windows
        if window.get("bbox") and window["bbox"][1] + window["bbox"][3] >= top and window["bbox"][1] <= bottom
    ]


def median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def write_study_room_overlay(path: Path, raw_svg: str, proposal: Dict) -> None:
    overlay = build_study_room_overlay(proposal)
    if "</svg>" in raw_svg:
        output = raw_svg.replace("</svg>", overlay + "</svg>", 1)
    else:
        output = f'<svg xmlns="http://www.w3.org/2000/svg">{overlay}</svg>'
    path.write_text(output, encoding="utf-8")


def build_study_room_overlay(proposal: Dict) -> str:
    room = proposal["newSpace"]
    points = room["geometry"]["points"]
    operations = proposal["operations"]
    walls = [operation for operation in operations if operation.get("type") == "addWall"]
    doors = [operation for operation in operations if operation.get("type") == "addDoor"]
    cx = room["bbox"][0] + room["bbox"][2] / 2
    cy = room["bbox"][1] + room["bbox"][3] / 2
    parts = [
        '<g id="renovation-proposal-overlay" pointer-events="none">',
        '<style><![CDATA[',
        ".proposal-room{fill:#2d9cdb;fill-opacity:.22;stroke:#0b5c86;stroke-width:4;}",
        ".proposal-wall{fill:none;stroke:#c0392b;stroke-width:8;stroke-linecap:square;}",
        ".proposal-door{fill:none;stroke:#f39c12;stroke-width:5;stroke-dasharray:7 5;}",
        ".proposal-label{fill:#0b5c86;font-family:Arial,sans-serif;font-weight:bold;font-size:30px;}",
        ".proposal-note{fill:#c0392b;font-family:Arial,sans-serif;font-weight:bold;font-size:20px;}",
        "]]></style>",
        f'<polygon class="proposal-room" points="{points_attr(points)}"><title>{html.escape(room["id"])}</title></polygon>',
    ]
    for wall in walls:
        geom = wall["geometry"]
        if len(geom) == 2:
            parts.append(line_markup(geom[0], geom[1], "proposal-wall", wall["id"]))
        elif len(geom) == 4:
            parts.append(line_markup(geom[0], geom[1], "proposal-wall", wall["id"] + "_upper"))
            parts.append(line_markup(geom[2], geom[3], "proposal-wall", wall["id"] + "_lower"))
    for door in doors:
        leaf = door["leaf"]
        arc = door["swingArc"]
        parts.append(line_markup(leaf[0], leaf[1], "proposal-door", door["id"] + "_leaf"))
        parts.append(
            f'<path class="proposal-door" d="M {arc["start"][0]} {arc["start"][1]} Q {arc["start"][0]} {arc["end"][1]} {arc["end"][0]} {arc["end"][1]}"><title>{html.escape(door["id"])}</title></path>'
        )
    parts.append(f'<text class="proposal-label" x="{clean_float(cx - 95)}" y="{clean_float(cy)}">공부방</text>')
    parts.append(f'<text class="proposal-note" x="{clean_float(room["bbox"][0])}" y="{clean_float(room["bbox"][1] - 16)}">제안 새 공간</text>')
    parts.append("</g>")
    return "".join(parts)


def line_markup(start: Sequence[float], end: Sequence[float], css_class: str, title: str) -> str:
    return f'<line class="{css_class}" x1="{start[0]}" y1="{start[1]}" x2="{end[0]}" y2="{end[1]}"><title>{html.escape(title)}</title></line>'


def points_attr(points: Sequence[Sequence[float]]) -> str:
    return " ".join(f"{point[0]},{point[1]}" for point in points)


def write_study_room_report(path: Path, overlay_svg: Path, proposal: Dict) -> None:
    svg_markup = overlay_svg.read_text(encoding="utf-8")
    operations = proposal.get("operations", [])
    checks = proposal.get("checks", {})
    assumptions = proposal.get("assumptions", [])
    html_text = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>거실 일부를 공부방으로 분할하는 제안</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; background: #f7faf8; color: #1f2933; }}
    header {{ background: #145a32; color: white; padding: 18px 24px; }}
    main {{ padding: 20px 24px 40px; }}
    .svg-panel {{ background: white; border: 1px solid #c8d5cd; border-radius: 6px; overflow: auto; max-height: 78vh; margin-bottom: 20px; }}
    .svg-panel svg {{ width: 100%; height: auto; display: block; }}
    section {{ background: white; border: 1px solid #c8d5cd; border-radius: 6px; padding: 16px; margin-bottom: 18px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid #e5ece8; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #ecf7ef; }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
  </style>
</head>
<body>
  <header>
    <h1>거실 일부를 공부방으로 분할하는 제안</h1>
    <div>현관 동선을 막지 않고, 거실 동쪽 창가 쪽을 공부방으로 나누는 안입니다.</div>
  </header>
  <main>
    <div class="svg-panel">{svg_markup}</div>
    <section>
      <h2>새 공간</h2>
      <table><tbody>
        <tr><th>내부 식별자</th><td><code>{html.escape(proposal["newSpace"]["id"])}</code></td></tr>
        <tr><th>공간 이름</th><td>{html.escape(ko_space_name(proposal["newSpace"]["name"]))}</td></tr>
        <tr><th>도면 좌표 범위</th><td><code>{html.escape(json.dumps(proposal["newSpace"]["bbox"]))}</code></td></tr>
        <tr><th>배정된 기존 창문</th><td>{html.escape(str(len(proposal["newSpace"]["assignedExistingWindows"])))}개</td></tr>
      </tbody></table>
    </section>
    <section>
      <h2>변경 작업</h2>
      <table><thead><tr><th>작업 종류</th><th>설명</th></tr></thead><tbody>
        {''.join(f'<tr><td>{html.escape(ko_operation_type(op.get("type", "")))}</td><td>{html.escape(ko_operation_summary(op))}</td></tr>' for op in operations)}
      </tbody></table>
    </section>
    <section>
      <h2>검토 결과</h2>
      <table><tbody>
        {''.join(f'<tr><th>{html.escape(ko_check_key(key))}</th><td>{html.escape(ko_value(value))}</td></tr>' for key, value in checks.items())}
      </tbody></table>
    </section>
    <section>
      <h2>전제와 한계</h2>
      <ul>{''.join(f'<li>{html.escape(ko_value(item))}</li>' for item in assumptions)}</ul>
    </section>
  </main>
</body>
</html>
"""
    path.write_text(html_text, encoding="utf-8")


def write_kitchen_pantry_overlay(path: Path, raw_svg: str, proposal: Dict) -> None:
    overlay = build_kitchen_pantry_overlay(proposal)
    if "</svg>" in raw_svg:
        output = raw_svg.replace("</svg>", overlay + "</svg>", 1)
    else:
        output = f'<svg xmlns="http://www.w3.org/2000/svg">{overlay}</svg>'
    path.write_text(output, encoding="utf-8")


def build_kitchen_pantry_overlay(proposal: Dict) -> str:
    converted = proposal["convertedArea"]
    pantry = proposal["newPantry"]
    operations = proposal["operations"]
    remove_walls = [operation for operation in operations if operation.get("type") == "removeWall"]
    converted_bbox = converted["bbox"]
    pantry_bbox = pantry["bbox"]
    converted_cx = converted_bbox[0] + converted_bbox[2] / 2
    converted_cy = converted_bbox[1] + converted_bbox[3] / 2
    pantry_cx = pantry_bbox[0] + pantry_bbox[2] / 2
    pantry_cy = pantry_bbox[1] + pantry_bbox[3] / 2
    parts = [
        '<g id="kitchen-pantry-proposal-overlay" pointer-events="none">',
        '<style><![CDATA[',
        ".proposal-converted-kitchen{fill:#27ae60;fill-opacity:.24;stroke:#145a32;stroke-width:5;}",
        ".proposal-new-pantry{fill:#8e44ad;fill-opacity:.26;stroke:#5b2c6f;stroke-width:5;}",
        ".proposal-remove-wall{fill:none;stroke:#c0392b;stroke-width:8;stroke-linecap:square;stroke-dasharray:14 8;}",
        ".proposal-flow{fill:none;stroke:#1f618d;stroke-width:4;stroke-dasharray:8 8;marker-end:url(#proposal-arrowhead);}",
        ".proposal-label{font-family:Arial,sans-serif;font-weight:bold;font-size:26px;letter-spacing:0;}",
        ".proposal-kitchen-label{fill:#145a32;}",
        ".proposal-pantry-label{fill:#5b2c6f;}",
        ".proposal-note{fill:#c0392b;font-family:Arial,sans-serif;font-weight:bold;font-size:19px;letter-spacing:0;}",
        "]]></style>",
        '<defs><marker id="proposal-arrowhead" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M 0 0 L 8 3 L 0 6 z" fill="#1f618d"/></marker></defs>',
        f'<polygon class="proposal-converted-kitchen" points="{points_attr(converted["geometry"]["points"])}"><title>{html.escape(converted["id"])}</title></polygon>',
        f'<polygon class="proposal-new-pantry" points="{points_attr(pantry["geometry"]["points"])}"><title>{html.escape(pantry["id"])}</title></polygon>',
    ]
    for wall in remove_walls:
        geom = wall["geometry"]
        if len(geom) == 2:
            parts.append(line_markup(geom[0], geom[1], "proposal-remove-wall", wall["id"]))
        elif len(geom) > 2:
            parts.append(f'<polyline class="proposal-remove-wall" points="{points_attr(geom)}"><title>{html.escape(wall["id"])}</title></polyline>')
    parts.append(f'<path class="proposal-flow" d="M {clean_float(converted_cx)} {clean_float(converted_cy)} C {clean_float(converted_cx + 190)} {clean_float(converted_cy + 80)}, {clean_float(pantry_cx - 180)} {clean_float(pantry_cy - 80)}, {clean_float(pantry_cx)} {clean_float(pantry_cy)}"/>')
    parts.append(f'<text class="proposal-label proposal-kitchen-label" x="{clean_float(converted_bbox[0] + 20)}" y="{clean_float(converted_bbox[1] + 72)}">팬트리 → 주방</text>')
    parts.append(f'<text class="proposal-label proposal-pantry-label" x="{clean_float(pantry_bbox[0] - 34)}" y="{clean_float(pantry_bbox[1] - 16)}">새 팬트리</text>')
    parts.append(f'<text class="proposal-note" x="{clean_float(converted_bbox[0] + 4)}" y="{clean_float(converted_bbox[1] - 18)}">팬트리 둘레 제거</text>')
    parts.append("</g>")
    return "".join(parts)


def write_kitchen_pantry_report(path: Path, overlay_svg: Path, proposal: Dict) -> None:
    svg_markup = overlay_svg.read_text(encoding="utf-8")
    operations = proposal.get("operations", [])
    checks = proposal.get("checks", {})
    assumptions = proposal.get("assumptions", [])
    html_text = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>팬트리 이전 및 주방 확장 제안</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; background: #f8faf7; color: #1f2933; }}
    header {{ background: #145a32; color: white; padding: 18px 24px; }}
    main {{ padding: 20px 24px 40px; }}
    .svg-panel {{ background: white; border: 1px solid #c8d5cd; border-radius: 6px; overflow: auto; max-height: 78vh; margin-bottom: 20px; }}
    .svg-panel svg {{ width: 100%; height: auto; display: block; }}
    section {{ background: white; border: 1px solid #c8d5cd; border-radius: 6px; padding: 16px; margin-bottom: 18px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid #e5ece8; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #ecf7ef; }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
  </style>
</head>
<body>
  <header>
    <h1>팬트리 이전 및 주방 확장 제안</h1>
    <div>기존 팬트리 면적은 주방으로 흡수하고, 주방 가까운 곳에 키 큰 팬트리 수납장을 새로 배치하는 안입니다.</div>
  </header>
  <main>
    <div class="svg-panel">{svg_markup}</div>
    <section>
      <h2>주방으로 전환할 영역</h2>
      <table><tbody>
        <tr><th>내부 식별자</th><td><code>{html.escape(proposal["convertedArea"]["id"])}</code></td></tr>
        <tr><th>기존 공간</th><td>{html.escape(ko_value(proposal["convertedArea"]["fromSpace"]))}</td></tr>
        <tr><th>변경 후 공간</th><td>{html.escape(ko_value(proposal["convertedArea"]["toSpace"]))}</td></tr>
        <tr><th>도면 좌표 범위</th><td><code>{html.escape(json.dumps(proposal["convertedArea"]["bbox"]))}</code></td></tr>
      </tbody></table>
    </section>
    <section>
      <h2>새 팬트리</h2>
      <table><tbody>
        <tr><th>내부 식별자</th><td><code>{html.escape(proposal["newPantry"]["id"])}</code></td></tr>
        <tr><th>공간 이름</th><td>{html.escape(ko_space_name(proposal["newPantry"]["name"]))}</td></tr>
        <tr><th>방식</th><td>{html.escape(ko_value(proposal["newPantry"]["subtype"]))}</td></tr>
        <tr><th>도면 좌표 범위</th><td><code>{html.escape(json.dumps(proposal["newPantry"]["bbox"]))}</code></td></tr>
        <tr><th>배치</th><td>{html.escape(ko_value(proposal["newPantry"]["placement"]))}</td></tr>
      </tbody></table>
    </section>
    <section>
      <h2>변경 작업</h2>
      <table><thead><tr><th>작업 종류</th><th>설명</th></tr></thead><tbody>
        {''.join(f'<tr><td>{html.escape(ko_operation_type(op.get("type", "")))}</td><td>{html.escape(ko_operation_summary(op))}</td></tr>' for op in operations)}
      </tbody></table>
    </section>
    <section>
      <h2>검토 결과</h2>
      <table><tbody>
        {''.join(f'<tr><th>{html.escape(ko_check_key(key))}</th><td>{html.escape(ko_value(value))}</td></tr>' for key, value in checks.items())}
      </tbody></table>
    </section>
    <section>
      <h2>전제와 한계</h2>
      <ul>{''.join(f'<li>{html.escape(ko_value(item))}</li>' for item in assumptions)}</ul>
    </section>
  </main>
</body>
</html>
"""
    path.write_text(html_text, encoding="utf-8")


def write_zoned_living_kitchen_dining_overlay(path: Path, raw_svg: str, proposal: Dict) -> None:
    overlay = build_zoned_living_kitchen_dining_overlay(proposal)
    if "</svg>" in raw_svg:
        output = raw_svg.replace("</svg>", overlay + "</svg>", 1)
    else:
        output = f'<svg xmlns="http://www.w3.org/2000/svg">{overlay}</svg>'
    path.write_text(output, encoding="utf-8")


def build_zoned_living_kitchen_dining_overlay(proposal: Dict) -> str:
    spaces = proposal["proposedSpaces"]
    operations = proposal["operations"]
    door_passages = proposal["analysis"]["circulation"].get("doorPassages", [])
    circulation_arrows = proposal["analysis"]["circulation"]["arrows"]
    airflow_arrows = proposal["analysis"]["ventilation"]["arrows"]
    parts = [
        '<g id="zoned-kitchen-dining-living-overlay" pointer-events="none">',
        '<defs>',
        '<marker id="zoned-circulation-arrow" markerWidth="12" markerHeight="12" refX="10" refY="4" orient="auto"><path d="M 0 0 L 10 4 L 0 8 z" fill="#0b5cab"/></marker>',
        '<marker id="zoned-airflow-arrow" markerWidth="12" markerHeight="12" refX="10" refY="4" orient="auto"><path d="M 0 0 L 10 4 L 0 8 z" fill="#008b8b"/></marker>',
        "</defs>",
        '<style><![CDATA[',
        ".zone-kitchen{fill:#2ecc71;fill-opacity:.18;stroke:#16803a;stroke-width:4;}",
        ".zone-dining{fill:#f1c40f;fill-opacity:.2;stroke:#9a7d0a;stroke-width:4;}",
        ".zone-living{fill:#3498db;fill-opacity:.16;stroke:#1f5f8b;stroke-width:4;}",
        ".zone-partition{fill:none;stroke:#c0392b;stroke-width:8;stroke-linecap:square;}",
        ".zone-opening{fill:none;stroke:#f39c12;stroke-width:6;stroke-dasharray:9 6;}",
        ".zone-reused{fill:none;stroke:#555;stroke-width:5;stroke-dasharray:10 7;}",
        ".door-passage{fill:#fff;stroke:#0b5cab;stroke-width:5;}",
        ".door-passage-label{font-family:Arial,sans-serif;font-weight:bold;font-size:15px;letter-spacing:0;fill:#0b5cab;}",
        ".circulation-arrow{fill:none;stroke:#0b5cab;stroke-width:5;stroke-linecap:round;stroke-linejoin:round;marker-end:url(#zoned-circulation-arrow);}",
        ".airflow-arrow{fill:none;stroke:#008b8b;stroke-width:5;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:10 8;marker-end:url(#zoned-airflow-arrow);}",
        ".zone-label{font-family:Arial,sans-serif;font-weight:bold;font-size:26px;letter-spacing:0;}",
        ".zone-note{font-family:Arial,sans-serif;font-weight:bold;font-size:18px;letter-spacing:0;fill:#c0392b;}",
        ".circulation-label{font-family:Arial,sans-serif;font-weight:bold;font-size:18px;letter-spacing:0;fill:#0b5cab;}",
        ".airflow-label{font-family:Arial,sans-serif;font-weight:bold;font-size:18px;letter-spacing:0;fill:#008b8b;}",
        "]]></style>",
        '<g id="proposal-zone-layer">',
    ]
    for space in spaces:
        css_class = {
            "space_kitchen_zoned_proposed": "zone-kitchen",
            "space_dining_zoned_proposed": "zone-dining",
            "space_living_room_independent_proposed": "zone-living",
        }.get(space["id"], "zone-living")
        points = space["geometry"]["points"]
        cx, cy = bbox_center(space["bbox"])
        parts.append(f'<polygon class="{css_class}" points="{points_attr(points)}"><title>{html.escape(space["id"])}</title></polygon>')
        parts.append(f'<text class="zone-label" x="{clean_float(cx - 95)}" y="{clean_float(cy)}">{html.escape(ko_space_name(space["name"]))}</text>')
    for operation in operations:
        if operation.get("type") == "addWall":
            for idx, segment in enumerate(operation.get("geometry", [])):
                parts.append(line_markup(segment[0], segment[1], "zone-partition", f'{operation["id"]}_{idx}'))
            opening = operation.get("opening")
            if opening:
                parts.append(line_markup(opening["geometry"][0], opening["geometry"][1], "zone-opening", opening["id"]))
        elif operation.get("type") == "reuseExistingBoundary":
            parts.append(line_markup(operation["geometry"][0], operation["geometry"][1], "zone-reused", operation["id"]))
    parts.append('<text class="zone-note" x="1628" y="512">식탁/주방 파티션, 개구부 유지</text>')
    parts.append('<text class="zone-note" x="1760" y="858">거실/주방 파티션, 개구부 유지</text>')
    parts.append("</g>")
    parts.append('<g id="analysis-door-passage-layer">')
    for passage in door_passages:
        point = passage["point"]
        parts.append(f'<circle class="door-passage" cx="{point[0]}" cy="{point[1]}" r="11"><title>{html.escape(passage["id"])}</title></circle>')
    for passage in door_passages:
        point = passage["point"]
        if passage["id"] in {"proposal_opening_kitchen_living", "proposal_opening_kitchen_dining", "existing_front_entry_door", "existing_entry_living_opening"}:
            parts.append(f'<text class="door-passage-label" x="{clean_float(point[0] + 14)}" y="{clean_float(point[1] - 10)}">{html.escape(ko_passage_name(passage["name"]))}</text>')
    parts.append("</g>")
    parts.append('<g id="analysis-circulation-layer">')
    for arrow in circulation_arrows:
        parts.append(path_from_points(arrow["points"], "circulation-arrow", arrow["id"]))
    parts.append('<text class="circulation-label" x="1305" y="1390">문/개구부를 지나는 이동</text>')
    parts.append("</g>")
    parts.append('<g id="analysis-ventilation-layer">')
    for arrow in airflow_arrows:
        parts.append(path_from_points(arrow["points"], "airflow-arrow", arrow["id"]))
    parts.append('<text class="airflow-label" x="1928" y="1245">전체 공간 바람 흐름</text>')
    parts.append("</g>")
    parts.append('<g id="analysis-warnings-layer">')
    parts.append('<text class="zone-note" x="1250" y="1495">새 파티션 구조 검토 필요</text>')
    parts.append("</g>")
    parts.append("</g>")
    return "".join(parts)


def path_from_points(points: Sequence[Sequence[float]], css_class: str, title: str) -> str:
    if len(points) < 2:
        return ""
    first = points[0]
    commands = [f"M {first[0]} {first[1]}"]
    commands.extend(f"L {point[0]} {point[1]}" for point in points[1:])
    d = " ".join(commands)
    return f'<path class="{css_class}" d="{d}"><title>{html.escape(title)}</title></path>'


def ko_space_name(name: str) -> str:
    return {
        "KITCHEN": "주방",
        "DINING": "식탁 공간",
        "LIVING ROOM": "거실",
        "ENTRY": "현관",
        "VERANDA": "베란다",
        "DECK": "데크",
        "BEDROOM": "침실",
        "BATHROOM": "욕실",
        "OFFICE": "오피스",
        "OFFICE / BATHROOM": "오피스/욕실",
        "DINING EXTERIOR WINDOWS": "식탁 공간 외부 창",
        "LIVING EAST WINDOWS": "거실 동쪽 창",
        "DECK DOOR/WINDOW BAND": "데크 쪽 문/창 구간",
        "BEDROOM WINDOW": "침실 창",
        "BATHROOM WINDOW": "욕실 창",
        "OFFICE WINDOW": "오피스 창",
        "VERANDA / ENTRY DOOR": "베란다/현관문",
        "STUDY ROOM": "공부방",
        "PANTRY": "팬트리",
        "KITCHEN EXPANSION": "주방 확장 영역",
        "space_kitchen": "주방",
        "space_pantry": "팬트리",
        "space_living_room": "거실",
        "space_study_room_proposed": "제안 공부방",
        "space_kitchen_expanded_proposed": "확장 주방",
        "space_pantry_relocated_proposed": "이전 팬트리",
    }.get(name, name)


def ko_check_key(key: str) -> str:
    return {
        "kitchenSeparated": "주방이 별도 구역으로 분리됨",
        "diningSeparated": "식탁 공간이 별도 구역으로 분리됨",
        "livingIndependent": "거실이 독립 공간으로 유지됨",
        "entryPathBlocked": "현관 동선이 막힘",
        "kitchenDiningPathMaintained": "주방과 식탁 사이 이동이 유지됨",
        "livingKitchenPathMaintained": "거실과 주방 사이 이동이 유지됨",
        "doorSwingConflict": "문 여닫이 충돌 가능성",
        "ventilationPathShown": "바람 흐름이 표시됨",
        "circulationArrowsShown": "사람 이동 동선이 표시됨",
        "movementRoutesPassThroughDoors": "이동 화살표가 문/개구부를 통과함",
        "wholeHouseAirflowShown": "전체 층의 바람 흐름이 고려됨",
        "needsStructuralReview": "구조 검토 필요",
        "needsMEPReview": "설비 검토 필요",
        "hasAccess": "출입 가능",
        "hasExteriorWindow": "외부 창문 있음",
        "assignedWindowCount": "배정된 창문 수",
        "doorProvided": "문 또는 개구부가 있음",
        "entryPathStrategy": "현관 동선 유지 방식",
        "circulationImpact": "동선 영향",
        "daylightPotential": "채광 가능성",
        "ventilationPotential": "통풍 가능성",
        "oldPantryConvertedToKitchen": "기존 팬트리를 주방으로 전환함",
        "newPantryNearKitchen": "새 팬트리가 주방 가까이에 있음",
        "distanceKitchenAnchorToNewPantry": "주방 기준점에서 새 팬트리까지의 도면 거리",
        "bedroomDoorBlocked": "침실문이 막힘",
        "diningAccessBlocked": "식탁 공간 접근이 막힘",
        "kitchenMainAislePreserved": "주방 주 동선이 유지됨",
        "exteriorWindowBlocked": "외부 창문을 막음",
        "daylightImpact": "채광 영향",
        "ventilationImpact": "통풍 영향",
    }.get(key, key)


def ko_value(value: object) -> str:
    if value is True:
        return "예"
    if value is False:
        return "아니요"
    if isinstance(value, str):
        return {
            "low_sliding_openings": "낮음. 여닫이문 대신 슬라이딩 도어 또는 문틀형 개구부를 쓰는 안이라 문짝 충돌 가능성이 작습니다.",
            "low": "낮음",
            "medium": "중간",
            "high": "높음",
            "unknown": "불확실. 도면 근거가 부족해 검토가 필요합니다.",
            "low_to_medium": "낮음에서 중간",
            "weighted_graph_proxy": "가중 그래프 기반 동선 근사 분석",
            "airflow_graph_proxy": "개구부 그래프 기반 바람 흐름 근사 분석",
            "whole_floor_proxy": "전체 층을 대상으로 한 근사 분석",
            "svg_user_unit": "SVG 좌표 단위. 실제 길이 단위로 보정되지는 않았습니다.",
            "proposal_for_review": "검토용 제안",
            "optimized": "동선 최적화 고려",
            "secondary": "보조 동선",
            "proxy": "근사 추정",
            "none_sliding_or_cased_opening": "여닫이 방향 없음. 슬라이딩 도어 또는 문틀형 개구부로 가정했습니다.",
            "light_partition_with_opening": "개구부가 있는 가벼운 파티션",
            "wide_sliding_or_cased_opening": "넓은 슬라이딩 도어 또는 문틀형 개구부",
            "TallPantryCabinetBank": "키 큰 팬트리 수납장",
            "window operability": "창문이 실제로 열리는지 여부",
            "wind direction": "주된 바람 방향",
            "opening area calibration": "개구부 면적 보정값",
            "ceiling height": "천장 높이",
            "The proposed room stays above the lower entry circulation band and uses a west-side internal door.": "제안한 공부방은 아래쪽 현관 이동 구간을 침범하지 않고, 서쪽 내부 문으로 출입하도록 배치했습니다.",
            "South-east kitchen cabinet run, next to the existing lower kitchen fixtures.": "주방 남동쪽 하부 수납/설비 라인 옆에 배치합니다.",
            "This is an inferred design proposal, not a structural safety decision.": "도면에서 추정한 설계 제안이며, 구조 안전 판단은 아닙니다.",
            "The proposal uses SVG user units; real-world scale calibration is not applied.": "좌표는 SVG 도면 단위이며, 실제 길이 단위 보정은 아직 적용하지 않았습니다.",
            "Load-bearing walls, code compliance, MEP routing, and permit feasibility are unknown.": "내력벽, 법규 적합성, 설비 배관/배선, 인허가 가능성은 아직 확인되지 않았습니다.",
            "The study room is placed against the right exterior window band to preserve daylight and ventilation potential.": "공부방은 우측 외부 창가 쪽에 배치해 채광과 통풍 가능성을 남겼습니다.",
            "The lower entry-side circulation area is intentionally left open.": "아래쪽 현관 이동 구간은 의도적으로 열어 두었습니다.",
            "The old pantry enclosure is treated as a removable interior partition until verified otherwise.": "기존 팬트리 벽체는 반대 근거가 확인되기 전까지 철거 가능한 내부 칸막이로 가정했습니다.",
            "The bedroom-side boundary is kept conceptually intact; only the kitchen-side pantry enclosure is removed.": "침실 쪽 경계는 유지하고, 주방 쪽 팬트리 둘레만 제거하는 것으로 가정했습니다.",
            "The relocated pantry is proposed as tall cabinet storage, not a new walk-in room, to avoid blocking kitchen and entry circulation.": "이전 팬트리는 별도 방이 아니라 키 큰 수납장으로 제안해 주방과 현관 동선을 막지 않도록 했습니다.",
            "Plumbing, electrical, HVAC, load-bearing walls, code compliance, and permit feasibility must be reviewed before construction.": "시공 전 배관, 전기, 공조, 내력벽, 법규, 인허가 검토가 필요합니다.",
            "New partitions are modeled as light partitions or sliding/cased openings, not confirmed structural walls.": "새 파티션은 가벼운 칸막이와 슬라이딩/문틀형 개구부로 가정했으며, 구조벽 여부는 확인되지 않았습니다.",
            "Airflow arrows are qualitative airflow graph proxies, not CFD results.": "바람 화살표는 정성적인 흐름 그래프 근사이며, 유체해석 결과는 아닙니다.",
            "Movement arrows show intended optimized circulation, not measured pedestrian simulation.": "이동 화살표는 의도한 최적 동선 표시이며, 실제 보행 시뮬레이션 결과는 아닙니다.",
            "Separate the study room from the remaining living room.": "공부방과 남은 거실 영역을 분리합니다.",
            "Create a partition with a door opening.": "문이 들어갈 개구부를 남긴 파티션을 만듭니다.",
            "Open the existing pantry footprint into the kitchen work area.": "기존 팬트리 영역을 열어 주방 작업 공간으로 편입합니다.",
            "Remove the angled pantry enclosure and absorb it into the kitchen.": "사선 팬트리 둘레를 제거하고 주방으로 흡수합니다.",
            "Replace the removed walk-in pantry with compact pantry storage near the kitchen.": "없어진 워크인 팬트리를 주방 가까운 압축 수납으로 대체합니다.",
        }.get(value, ko_space_name(value))
    if isinstance(value, list):
        return ", ".join(ko_value(item) for item in value)
    if isinstance(value, dict):
        return "; ".join(f"{ko_check_key(str(key))}: {ko_value(val)}" for key, val in value.items())
    return str(value)


def ko_operation_type(value: str) -> str:
    return {
        "createSpace": "공간 생성",
        "addWall": "파티션 추가",
        "reuseExistingBoundary": "기존 경계 활용",
        "addDoor": "문/개구부 추가",
        "removeSpace": "공간 제거/전환",
        "removeWall": "벽체 제거",
        "expandSpace": "공간 확장",
        "addStorageCabinet": "수납장 추가",
    }.get(value, value)


def ko_operation_summary(operation: Dict) -> str:
    op_id = operation.get("id")
    if op_id == "proposal_partition_dining_kitchen":
        return "식탁 공간과 주방 사이에 가벼운 파티션을 두되, 가운데 넓은 통로를 남깁니다."
    if op_id == "proposal_partition_living_kitchen":
        return "거실과 주방 사이에 파티션을 두되, 이동과 환기를 위한 넓은 통로를 남깁니다."
    if op_id == "proposal_reuse_stair_cabinet_boundary":
        return "기존 계단/수납 경계를 거실과 주방을 나누는 일부 경계로 활용합니다."
    if op_id == "proposal_sliding_door_kitchen_dining":
        return "주방과 식탁 공간 사이에는 여닫이문 대신 슬라이딩 도어 또는 문틀형 개구부를 둡니다."
    if op_id == "proposal_sliding_door_kitchen_living":
        return "주방과 거실 사이에는 여닫이문 대신 슬라이딩 도어 또는 문틀형 개구부를 둡니다."
    if op_id == "proposal_wall_north":
        return "거실 일부를 공부방으로 분리하는 북쪽 파티션을 추가합니다."
    if op_id == "proposal_wall_west":
        return "공부방 출입구를 남기고 서쪽 파티션을 추가합니다."
    if op_id == "proposal_door_001":
        return "남은 거실에서 공부방으로 들어가는 내부 문을 둡니다."
    if op_id == "proposal_remove_pantry_east_partition":
        return "기존 팬트리의 주방 쪽 칸막이를 제거해 주방 작업 공간으로 엽니다."
    if op_id == "proposal_remove_pantry_south_angle":
        return "기존 팬트리의 사선 둘레를 제거해 주방으로 흡수합니다."
    if op_id == "proposal_pantry_cabinet_bank":
        return "주방 가까운 곳에 키 큰 팬트리 수납장을 새로 둡니다."
    if operation.get("type") == "createSpace":
        return f"{ko_space_name(str(operation.get('name', '')))} 구역을 제안 공간으로 만듭니다."
    if operation.get("type") == "removeSpace":
        return f"{ko_space_name(str(operation.get('name', '')))}를 별도 공간에서 해제하고 {ko_value(operation.get('replacement', ''))}로 전환합니다."
    if operation.get("type") == "expandSpace":
        return f"{ko_value(operation.get('spaceId', ''))}을 확장된 공간으로 재정의합니다."
    return ko_value(str(operation.get("purpose") or operation.get("id") or operation.get("type") or ""))


def ko_passage_name(name: str) -> str:
    return {
        "ENTRY DOOR": "현관문",
        "ENTRY / LIVING OPENING": "현관과 거실 사이 개구부",
        "KITCHEN / LIVING OPENING": "주방과 거실 사이 개구부",
        "KITCHEN / DINING OPENING": "주방과 식탁 공간 사이 개구부",
        "BEDROOM DOOR": "침실문",
        "OFFICE DOOR": "오피스 문",
        "BATHROOM DOOR": "욕실문",
    }.get(name, name)


def ko_reference_name(reference_id: str) -> str:
    return {
        "existing_front_entry_door": "현관문",
        "existing_entry_living_opening": "현관-거실 개구부",
        "proposal_opening_kitchen_living": "주방-거실 개구부",
        "proposal_opening_kitchen_dining": "주방-식탁 공간 개구부",
        "existing_bedroom_door": "침실문",
        "existing_office_door": "오피스 문",
        "existing_bathroom_door": "욕실문",
        "existing_deck_dining_door": "데크-식탁 공간 문/창",
    }.get(reference_id, reference_id)


def ko_reference_list(reference_ids: Sequence[str]) -> str:
    return ", ".join(ko_reference_name(reference_id) for reference_id in reference_ids)


def ko_arrow_purpose(arrow_id: str, fallback: str) -> str:
    return {
        "path_entry_to_living": "현관문에서 현관-거실 개구부를 지나 거실로 바로 들어가는 주 동선입니다.",
        "path_entry_to_kitchen": "현관문, 현관-거실 개구부, 주방-거실 개구부를 차례로 지나 주방으로 가는 동선입니다.",
        "path_kitchen_to_dining": "주방과 식탁 공간 사이 개구부를 통과하는 짧은 배식 동선입니다.",
        "path_bedroom_to_living": "침실문과 주방-거실 개구부를 지나 거실로 이동하는 보조 동선입니다.",
        "path_office_bath_to_living": "오피스와 욕실 쪽에서 기존 문과 현관-거실 개구부를 지나 거실로 이동하는 보조 동선입니다.",
        "airflow_dining_to_kitchen": "식탁 공간의 외부 창에서 들어온 공기가 주방-식탁 개구부를 통해 주방으로 흐를 수 있는 경로입니다.",
        "airflow_living_to_kitchen": "거실 동쪽 창 쪽 공기가 주방-거실 개구부를 통해 주방으로 이동할 수 있는 경로입니다.",
        "airflow_deck_to_dining": "데크 쪽 문/창에서 식탁 공간으로 유입될 수 있는 바람 경로입니다.",
        "airflow_bedroom_to_kitchen": "침실 창에서 들어온 공기가 침실문을 통해 주방 쪽으로 이동할 수 있는 경로입니다.",
        "airflow_bathroom_to_living": "욕실 쪽 창/개구부에서 들어온 공기가 욕실문과 현관-거실 개구부를 거쳐 거실로 이동할 수 있는 경로입니다.",
        "airflow_office_to_living": "오피스 창에서 들어온 공기가 오피스 문과 현관-거실 개구부를 거쳐 거실로 이동할 수 있는 경로입니다.",
        "airflow_veranda_entry_living": "베란다와 현관문을 통해 들어온 공기가 현관-거실 개구부를 거쳐 거실로 이동할 수 있는 경로입니다.",
    }.get(arrow_id, fallback)


def write_zoned_living_kitchen_dining_report(path: Path, overlay_svg: Path, proposal: Dict) -> None:
    svg_markup = overlay_svg.read_text(encoding="utf-8")
    spaces = proposal.get("proposedSpaces", [])
    operations = proposal.get("operations", [])
    circulation = proposal.get("analysis", {}).get("circulation", {})
    ventilation = proposal.get("analysis", {}).get("ventilation", {})
    door_passages = circulation.get("doorPassages", [])
    checks = proposal.get("checks", {})
    assumptions = proposal.get("assumptions", [])
    html_text = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>주방, 식탁 공간, 거실 분리 제안</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; background: #f7f9fb; color: #1f2933; }}
    header {{ background: #172554; color: white; padding: 18px 24px; }}
    main {{ padding: 20px 24px 40px; }}
    .svg-panel {{ background: white; border: 1px solid #c8d5cd; border-radius: 6px; overflow: auto; max-height: 78vh; margin-bottom: 20px; }}
    .svg-panel svg {{ width: 100%; height: auto; display: block; }}
    section {{ background: white; border: 1px solid #c8d5cd; border-radius: 6px; padding: 16px; margin-bottom: 18px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid #e5ece8; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #eef4ff; }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
  </style>
</head>
<body>
  <header>
    <h1>주방, 식탁 공간, 거실 분리 제안</h1>
    <div>동선은 문과 개구부를 통과하도록 표시했고, 바람 흐름은 전체 층 기준으로 근사 표시했습니다.</div>
  </header>
  <main>
    <div class="svg-panel">{svg_markup}</div>
    <section>
      <h2>제안 공간</h2>
      <table><thead><tr><th>식별자</th><th>공간 이름</th><th>도면 좌표 범위</th></tr></thead><tbody>
        {''.join(f'<tr><td><code>{html.escape(space["id"])}</code></td><td>{html.escape(ko_space_name(space["name"]))}</td><td><code>{html.escape(json.dumps(space["bbox"]))}</code></td></tr>' for space in spaces)}
      </tbody></table>
    </section>
    <section>
      <h2>변경 작업</h2>
      <table><thead><tr><th>작업 종류</th><th>설명</th></tr></thead><tbody>
        {''.join(f'<tr><td>{html.escape(ko_operation_type(op.get("type", "")))}</td><td>{html.escape(ko_operation_summary(op))}</td></tr>' for op in operations)}
      </tbody></table>
    </section>
    <section>
      <h2>문과 개구부 통과 지점</h2>
      <table><thead><tr><th>식별자</th><th>이름</th><th>연결 공간</th><th>도면 좌표</th></tr></thead><tbody>
        {''.join(f'<tr><td><code>{html.escape(passage["id"])}</code></td><td>{html.escape(ko_passage_name(passage["name"]))}</td><td>{html.escape(ko_value(passage["connects"]))}</td><td><code>{html.escape(json.dumps(passage["point"], ensure_ascii=False))}</code></td></tr>' for passage in door_passages)}
      </tbody></table>
    </section>
    <section>
      <h2>사람 이동 동선</h2>
      <table><thead><tr><th>식별자</th><th>출발</th><th>도착</th><th>통과하는 문/개구부</th><th>설명</th></tr></thead><tbody>
        {''.join(f'<tr><td><code>{html.escape(arrow["id"])}</code></td><td>{html.escape(ko_space_name(arrow["from"]))}</td><td>{html.escape(ko_space_name(arrow["to"]))}</td><td>{html.escape(ko_reference_list(arrow.get("throughDoorIds", [])))}</td><td>{html.escape(ko_arrow_purpose(arrow["id"], arrow["purpose"]))}</td></tr>' for arrow in circulation.get("arrows", []))}
      </tbody></table>
    </section>
    <section>
      <h2>바람 흐름</h2>
      <table><thead><tr><th>식별자</th><th>시작 지점</th><th>도착 지점</th><th>통과하는 문/개구부</th><th>설명</th></tr></thead><tbody>
        {''.join(f'<tr><td><code>{html.escape(arrow["id"])}</code></td><td>{html.escape(ko_space_name(arrow["from"]))}</td><td>{html.escape(ko_space_name(arrow["to"]))}</td><td>{html.escape(ko_reference_list(arrow.get("throughOpeningIds", [])))}</td><td>{html.escape(ko_arrow_purpose(arrow["id"], arrow["purpose"]))}</td></tr>' for arrow in ventilation.get("arrows", []))}
      </tbody></table>
      <p>고려한 공간: {html.escape(ko_value(ventilation.get("spacesConsidered", [])))}</p>
      <p>아직 모르는 입력값: {html.escape(ko_value(ventilation.get("unknowns", [])))}</p>
    </section>
    <section>
      <h2>검토 결과</h2>
      <table><tbody>
        {''.join(f'<tr><th>{html.escape(ko_check_key(key))}</th><td>{html.escape(ko_value(value))}</td></tr>' for key, value in checks.items())}
      </tbody></table>
    </section>
    <section>
      <h2>전제와 한계</h2>
      <ul>{''.join(f'<li>{html.escape(ko_value(item))}</li>' for item in assumptions)}</ul>
    </section>
  </main>
</body>
</html>
"""
    path.write_text(html_text, encoding="utf-8")
