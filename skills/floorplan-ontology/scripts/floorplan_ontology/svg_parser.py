"""SVG parsing and normalization."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from lxml import etree

from .geometry import (
    bbox_from_points,
    clean_float,
    centroid_from_points,
    ellipse_points,
    identity_matrix,
    line_length,
    line_points,
    matrix_to_list,
    multiply_matrix,
    parse_points,
    parse_transform,
    polygon_area,
    rect_points,
    sample_path_points,
    transform_points,
)
from .labels import classify_label, normalize_text, slugify

DRAWABLE_TAGS = {"rect", "polygon", "polyline", "line", "path", "circle", "ellipse", "text"}
SVG_NS = "http://www.w3.org/2000/svg"


def local_name(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def parse_style_declarations(style: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for part in (style or "").split(";"):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        result[key.strip()] = value.strip()
    return result


def parse_css_styles(root: etree._Element) -> Dict[str, Dict[str, str]]:
    styles: Dict[str, Dict[str, str]] = {}
    for style_el in root.xpath(".//*[local-name()='style']"):
        text = "".join(style_el.itertext())
        for selectors, body in re.findall(r"([^{}]+)\{([^{}]+)\}", text):
            declarations = parse_style_declarations(body)
            for selector in selectors.split(","):
                selector = selector.strip()
                if selector.startswith("."):
                    styles.setdefault(selector[1:], {}).update(declarations)
    return styles


def computed_style(element: etree._Element, class_styles: Dict[str, Dict[str, str]]) -> Dict[str, str]:
    style: Dict[str, str] = {}
    for class_name in (element.get("class") or "").split():
        style.update(class_styles.get(class_name, {}))
    for attr_name in [
        "fill",
        "stroke",
        "stroke-width",
        "font-family",
        "font-size",
        "fill-rule",
        "stroke-miterlimit",
        "opacity",
    ]:
        if attr_name in element.attrib:
            style[attr_name] = element.attrib[attr_name]
    style.update(parse_style_declarations(element.get("style", "")))
    return style


def style_value(style: Dict[str, str], name: str, default: Optional[str] = None) -> Optional[str]:
    return style.get(name, default)


def font_size(style: Dict[str, str]) -> float:
    value = style.get("font-size", "12")
    match = re.search(r"[-+]?(?:\d*\.\d+|\d+)", value)
    return float(match.group(0)) if match else 12.0


def get_viewbox(root: etree._Element) -> List[float]:
    raw = root.get("viewBox") or root.get("viewbox") or ""
    nums = [float(value) for value in re.findall(r"[-+]?(?:\d*\.\d+|\d+)", raw)]
    return [clean_float(value) for value in nums[:4]] if len(nums) >= 4 else [0.0, 0.0, 0.0, 0.0]


def orientation_from_transform(transform: str) -> float:
    match = re.search(r"rotate\(([-+]?(?:\d*\.\d+|\d+))", transform or "")
    return clean_float(float(match.group(1))) if match else 0.0


def categorize_vector(node: Dict) -> List[Dict[str, object]]:
    candidates: List[Dict[str, object]] = []
    tag = node.get("sourceTag")
    style = node.get("style", {})
    bbox = node.get("bbox") or [0, 0, 0, 0]
    metrics = node.get("metrics", {})
    fill = str(style.get("fill", "")).lower()
    stroke = str(style.get("stroke", "")).lower()
    width, height = bbox[2], bbox[3]
    area = float(metrics.get("area") or 0.0)
    length = float(metrics.get("length") or 0.0)
    source_class = node.get("sourceClass") or ""
    min_dim = min(width, height)
    max_dim = max(width, height)

    if tag == "text":
        candidates.append({"category": "text_anchor", "confidence": 1.0, "evidence": ["svg_text"]})

    if tag in {"polygon", "rect"} and area > 2000 and fill not in {"", "none", "#000", "#000000"}:
        candidates.append({"category": "space_surface_candidate", "confidence": 0.62, "evidence": ["large_filled_shape"]})

    if tag in {"line", "polyline"} and stroke in {"#000", "#000000", "black"} and length >= 40:
        candidates.append({"category": "wall_candidate", "confidence": 0.48, "evidence": ["long_black_stroke"]})

    if tag == "polygon" and ("cls-36" in source_class or "cls-46" in source_class or fill == "#f0f0ff"):
        if min_dim <= 18 and max_dim >= 40:
            candidates.append({"category": "window_candidate", "confidence": 0.8, "evidence": ["thin_repeated_light_polygon"]})

    if tag == "path" and looks_like_door_swing(str(node.get("rawAttributes", {}).get("d", ""))):
        candidates.append({"category": "door_swing_candidate", "confidence": 0.82, "evidence": ["quadratic_swing_sector"]})

    if tag == "polygon" and any(cls in source_class.split() for cls in ["cls-33", "cls-35", "cls-40"]):
        if min_dim <= 20 and max_dim >= 50:
            candidates.append({"category": "door_leaf_candidate", "confidence": 0.72, "evidence": ["thin_door_leaf_polygon"]})

    if tag in {"path", "rect", "polygon", "circle", "ellipse"} and area < 2000 and not candidates:
        candidates.append({"category": "fixture_or_detail_candidate", "confidence": 0.35, "evidence": ["small_graphic"]})

    return candidates


def looks_like_door_swing(d: str) -> bool:
    if not d:
        return False
    tokens = re.findall(r"[A-Za-z]|[-+]?(?:\d*\.\d+|\d+)", d)
    has_quad = any(token in {"q", "Q"} for token in tokens)
    has_close = any(token in {"Z", "z"} for token in tokens)
    nums = [float(token) for token in tokens if re.match(r"[-+]?(?:\d*\.\d+|\d+)$", token)]
    has_door_radius = any(55 <= abs(num) <= 95 for num in nums)
    return has_quad and has_close and has_door_radius


class SvgParser:
    def __init__(self, path: Path):
        self.path = path
        self.tree = etree.parse(str(path))
        self.root = self.tree.getroot()
        self.class_styles = parse_css_styles(self.root)
        self.raw_svg = path.read_text(encoding="utf-8")
        self.source_counts: Counter = Counter()
        self.vector_nodes: List[Dict] = []
        self.labels: List[Dict] = []
        self._drawable_index = 0

    def parse(self) -> Dict[str, object]:
        self._walk(self.root, identity_matrix())
        document = {
            "id": f"doc_{slugify(self.path.stem)}",
            "sourceFile": self.path.name,
            "sourceType": "svg",
            "viewBox": get_viewbox(self.root),
            "coordinateSystem": {
                "origin": "top_left",
                "xAxis": "right",
                "yAxis": "down",
                "unit": "svg_user_unit",
            },
            "sourceCounts": dict(self.source_counts),
        }
        return {
            "document": document,
            "vectorNodes": self.vector_nodes,
            "labels": self.labels,
            "rawSvg": self.raw_svg,
        }

    def _walk(self, element: etree._Element, parent_matrix: Tuple[float, float, float, float, float, float]) -> None:
        tag = local_name(element.tag)
        local_matrix = parse_transform(element.get("transform"))
        matrix = multiply_matrix(parent_matrix, local_matrix)
        if tag in DRAWABLE_TAGS:
            self._drawable_index += 1
            node = self._node_for_element(element, tag, matrix, self._drawable_index)
            if node:
                self.vector_nodes.append(node)
                self.source_counts[tag] += 1
                if tag == "text":
                    label = self._label_for_text(element, node)
                    self.labels.append(label)
        for child in element:
            self._walk(child, matrix)

    def _node_for_element(self, element: etree._Element, tag: str, matrix, index: int) -> Optional[Dict]:
        source_id = f"svg_el_{index:06d}"
        style = computed_style(element, self.class_styles)
        attrs = dict(element.attrib)
        points: List[Tuple[float, float]] = []
        geometry_type = tag
        geometry: Dict[str, object] = {}
        closed = tag in {"rect", "polygon", "circle", "ellipse"}

        if tag == "rect":
            points = transform_points(rect_points(attrs), matrix)
            geometry = {"type": "Rect", "points": rounded_points(points)}
        elif tag == "polygon":
            points = transform_points(parse_points(attrs.get("points", "")), matrix)
            geometry = {"type": "Polygon", "points": rounded_points(points)}
        elif tag == "polyline":
            points = transform_points(parse_points(attrs.get("points", "")), matrix)
            geometry = {"type": "LineString", "points": rounded_points(points)}
        elif tag == "line":
            points = transform_points(line_points(attrs), matrix)
            geometry = {"type": "LineString", "points": rounded_points(points)}
        elif tag in {"circle", "ellipse"}:
            points = transform_points(ellipse_points(attrs), matrix)
            geometry = {"type": "Polygon", "points": rounded_points(points)}
            geometry_type = tag
        elif tag == "path":
            sampled = transform_points(sample_path_points(attrs.get("d", "")), matrix)
            points = sampled
            geometry = {
                "type": "Path",
                "pathData": attrs.get("d", ""),
                "sampledPoints": rounded_points(sampled),
            }
        elif tag == "text":
            x = float(attrs.get("x", 0.0))
            y = float(attrs.get("y", 0.0))
            anchor = transform_points([(x, y)], matrix)[0]
            text = normalize_text("".join(element.itertext()))
            size = font_size(style)
            width = max(size * 0.55 * len(text), size)
            height = size * 1.35
            points = [anchor]
            geometry = {
                "type": "Point",
                "points": [clean_float(anchor[0]), clean_float(anchor[1])],
                "approxTextBox": [
                    clean_float(anchor[0]),
                    clean_float(anchor[1] - height),
                    clean_float(width),
                    clean_float(height),
                ],
            }
            geometry_type = "text"

        bbox = bbox_from_points(points)
        if tag == "text":
            bbox = geometry["approxTextBox"]  # type: ignore[assignment]
        centroid = centroid_from_points(points, closed=closed)
        if tag == "text":
            centroid = geometry["points"]  # type: ignore[assignment]

        metrics = {
            "area": clean_float(polygon_area(points)) if closed else 0.0,
            "length": clean_float(line_length(points)) if tag in {"line", "polyline", "path"} else 0.0,
            "aspectRatio": clean_float((bbox[2] / bbox[3]) if bbox and bbox[3] else 0.0),
        }
        node = {
            "id": f"vec_{index:06d}",
            "sourceElementId": source_id,
            "sourceTag": tag,
            "sourceClass": attrs.get("class", ""),
            "geometryType": geometry_type,
            "geometry": geometry,
            "bbox": bbox,
            "centroid": centroid,
            "metrics": metrics,
            "style": style,
            "transform": matrix_to_list(matrix),
            "zOrder": index,
            "rawAttributes": attrs,
        }
        node["categoryCandidates"] = categorize_vector(node)
        return node

    def _label_for_text(self, element: etree._Element, node: Dict) -> Dict:
        raw_text = "".join(element.itertext())
        normalized = normalize_text(raw_text)
        classified = classify_label(raw_text)
        anchor = node.get("centroid") or [0, 0]
        label_id = f"label_{slugify(str(classified.get('name') or normalized))}"
        return {
            "id": label_id,
            "sourceElementId": node["sourceElementId"],
            "sourceVectorNodeId": node["id"],
            "rawText": raw_text,
            "normalizedText": normalized,
            "labelType": classified["labelType"],
            "name": classified["name"],
            "dimensionText": classified["dimensionText"],
            "entityType": classified["entityType"],
            "subtype": classified["subtype"],
            "anchor": anchor,
            "bbox": node.get("bbox"),
            "orientationDegrees": orientation_from_transform(element.get("transform", "")),
            "style": node.get("style", {}),
            "linkedEntityId": None,
            "confidence": 1.0,
        }


def rounded_points(points: Iterable[Tuple[float, float]]) -> List[List[float]]:
    return [[clean_float(x), clean_float(y)] for x, y in points]

