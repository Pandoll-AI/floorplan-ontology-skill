"""Label normalization and classification."""

from __future__ import annotations

import re
from typing import Dict, Optional, Tuple


DIMENSION_RE = re.compile(
    r"(?P<dim>\d+\s*'\s*\d+\s*\"\s*x\s*\d+\s*'\s*\d+\s*\")",
    re.IGNORECASE,
)

SPACE_TYPES = {
    "LIVING ROOM": ("Room", "LivingSpace", "room_label"),
    "OFFICE": ("Room", "Office", "room_label"),
    "ENTRY": ("CirculationSpace", "Entry", "room_label"),
    "BEDROOM": ("Room", "Bedroom", "room_label"),
    "DINING": ("Room", "Dining", "room_label"),
    "BATHROOM": ("Room", "Bathroom", "room_label"),
    "KITCHEN": ("Room", "Kitchen", "room_label"),
    "PANTRY": ("Storage", "Pantry", "storage_label"),
    "CLOSET": ("Storage", "Closet", "storage_label"),
    "DECK": ("OutdoorArea", "Deck", "outdoor_label"),
    "VERANDA": ("OutdoorArea", "Veranda", "outdoor_label"),
}

FIXTURE_LABELS = {
    "FP": ("Fixture", "Fireplace"),
    "DW": ("Fixture", "Dishwasher"),
}


def slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return text or "item"


def normalize_quotes(text: str) -> str:
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2032": "'",
        "\u2033": '"',
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


def normalize_text(text: str) -> str:
    cleaned = normalize_quotes(text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.replace("APPR OXIM ATE", "APPROXIMATE")
    return cleaned


def split_name_dimension(text: str) -> Tuple[str, Optional[str]]:
    normalized = normalize_text(text)
    match = DIMENSION_RE.search(normalized)
    if not match:
        return normalized.strip(), None
    dimension = re.sub(r"\s+", "", match.group("dim")).replace("x", " x ")
    name = (normalized[: match.start()] + " " + normalized[match.end() :]).strip()
    return name.strip(), dimension


def classify_label(raw_text: str) -> Dict[str, object]:
    normalized = normalize_text(raw_text)
    name, dimension = split_name_dimension(normalized)
    upper_name = name.upper().strip()
    upper_norm = normalized.upper().strip()

    if upper_name in SPACE_TYPES:
        entity_type, subtype, label_type = SPACE_TYPES[upper_name]
        return {
            "labelType": label_type,
            "name": upper_name,
            "dimensionText": dimension,
            "entityType": entity_type,
            "subtype": subtype,
        }

    if upper_norm in FIXTURE_LABELS:
        entity_type, subtype = FIXTURE_LABELS[upper_norm]
        return {
            "labelType": "fixture_label",
            "name": upper_norm,
            "dimensionText": None,
            "entityType": entity_type,
            "subtype": subtype,
        }

    if upper_norm == "FLOOR 1":
        return {
            "labelType": "floor_label",
            "name": upper_norm,
            "dimensionText": None,
            "entityType": "Annotation",
            "subtype": "FloorLabel",
        }

    annotation_markers = [
        "LOGO",
        "GROSS INTERNAL AREA",
        "TOTAL:",
        "SIZES AND DIMENSIONS",
        "FLOOR 1:",
        "FLOOR 2:",
    ]
    if any(marker in upper_norm for marker in annotation_markers):
        return {
            "labelType": "annotation",
            "name": upper_norm,
            "dimensionText": None,
            "entityType": "Annotation",
            "subtype": "Note",
        }

    return {
        "labelType": "unknown_label",
        "name": upper_name or upper_norm,
        "dimensionText": dimension,
        "entityType": "Annotation",
        "subtype": "UnknownLabel",
    }

