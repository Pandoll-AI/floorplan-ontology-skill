"""Geometry and SVG transform helpers."""

from __future__ import annotations

import math
import re
import warnings
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from shapely.geometry import LineString, Point, Polygon
from svgpathtools import parse_path

Point2D = Tuple[float, float]
Matrix = Tuple[float, float, float, float, float, float]


FLOAT_RE = re.compile(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?")


def clean_float(value: float, digits: int = 4) -> float:
    rounded = round(float(value), digits)
    if rounded == -0.0:
        return 0.0
    return rounded


def identity_matrix() -> Matrix:
    return (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def multiply_matrix(left: Matrix, right: Matrix) -> Matrix:
    a1, b1, c1, d1, e1, f1 = left
    a2, b2, c2, d2, e2, f2 = right
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def apply_matrix(matrix: Matrix, point: Point2D) -> Point2D:
    a, b, c, d, e, f = matrix
    x, y = point
    return (a * x + c * y + e, b * x + d * y + f)


def parse_numbers(value: str) -> List[float]:
    return [float(match.group(0)) for match in FLOAT_RE.finditer(value or "")]


def parse_transform(transform: Optional[str]) -> Matrix:
    if not transform:
        return identity_matrix()

    matrix = identity_matrix()
    for name, args in re.findall(r"([a-zA-Z]+)\(([^)]*)\)", transform):
        nums = parse_numbers(args)
        op = identity_matrix()
        lname = name.lower()
        if lname == "matrix" and len(nums) >= 6:
            op = (nums[0], nums[1], nums[2], nums[3], nums[4], nums[5])
        elif lname == "translate":
            tx = nums[0] if nums else 0.0
            ty = nums[1] if len(nums) > 1 else 0.0
            op = (1.0, 0.0, 0.0, 1.0, tx, ty)
        elif lname == "scale":
            sx = nums[0] if nums else 1.0
            sy = nums[1] if len(nums) > 1 else sx
            op = (sx, 0.0, 0.0, sy, 0.0, 0.0)
        elif lname == "rotate":
            angle = math.radians(nums[0] if nums else 0.0)
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            rotation = (cos_a, sin_a, -sin_a, cos_a, 0.0, 0.0)
            if len(nums) >= 3:
                cx, cy = nums[1], nums[2]
                op = multiply_matrix(
                    multiply_matrix((1.0, 0.0, 0.0, 1.0, cx, cy), rotation),
                    (1.0, 0.0, 0.0, 1.0, -cx, -cy),
                )
            else:
                op = rotation
        elif lname == "skewx":
            angle = math.radians(nums[0] if nums else 0.0)
            op = (1.0, 0.0, math.tan(angle), 1.0, 0.0, 0.0)
        elif lname == "skewy":
            angle = math.radians(nums[0] if nums else 0.0)
            op = (1.0, math.tan(angle), 0.0, 1.0, 0.0, 0.0)
        matrix = multiply_matrix(matrix, op)
    return matrix


def matrix_to_list(matrix: Matrix) -> List[float]:
    return [clean_float(value) for value in matrix]


def transform_points(points: Iterable[Point2D], matrix: Matrix) -> List[Point2D]:
    return [apply_matrix(matrix, point) for point in points]


def parse_points(points: str) -> List[Point2D]:
    nums = parse_numbers(points)
    return [(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]


def rect_points(attrs: Dict[str, str]) -> List[Point2D]:
    x = float(attrs.get("x", 0.0))
    y = float(attrs.get("y", 0.0))
    width = float(attrs.get("width", 0.0))
    height = float(attrs.get("height", 0.0))
    return [(x, y), (x + width, y), (x + width, y + height), (x, y + height)]


def line_points(attrs: Dict[str, str]) -> List[Point2D]:
    return [
        (float(attrs.get("x1", 0.0)), float(attrs.get("y1", 0.0))),
        (float(attrs.get("x2", 0.0)), float(attrs.get("y2", 0.0))),
    ]


def ellipse_points(attrs: Dict[str, str], samples: int = 36) -> List[Point2D]:
    cx = float(attrs.get("cx", 0.0))
    cy = float(attrs.get("cy", 0.0))
    if "r" in attrs:
        rx = ry = float(attrs.get("r", 0.0))
    else:
        rx = float(attrs.get("rx", 0.0))
        ry = float(attrs.get("ry", 0.0))
    return [
        (cx + rx * math.cos(2 * math.pi * idx / samples), cy + ry * math.sin(2 * math.pi * idx / samples))
        for idx in range(samples)
    ]


def sample_path_points(d: str, samples_per_segment: int = 12) -> List[Point2D]:
    if not d:
        return []
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            path = parse_path(d)
    except Exception:
        return []
    points: List[Point2D] = []
    for segment in path:
        for idx in range(samples_per_segment + 1):
            point = segment.point(idx / samples_per_segment)
            points.append((point.real, point.imag))
    return points


def bbox_from_points(points: Sequence[Point2D]) -> Optional[List[float]]:
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return [clean_float(min_x), clean_float(min_y), clean_float(max_x - min_x), clean_float(max_y - min_y)]


def centroid_from_points(points: Sequence[Point2D], closed: bool = False) -> Optional[List[float]]:
    if not points:
        return None
    try:
        geom = Polygon(points) if closed and len(points) >= 3 else LineString(points)
        centroid = geom.centroid
        return [clean_float(centroid.x), clean_float(centroid.y)]
    except Exception:
        x = sum(point[0] for point in points) / len(points)
        y = sum(point[1] for point in points) / len(points)
        return [clean_float(x), clean_float(y)]


def polygon_area(points: Sequence[Point2D]) -> float:
    if len(points) < 3:
        return 0.0
    try:
        return abs(float(Polygon(points).area))
    except Exception:
        total = 0.0
        for idx, (x1, y1) in enumerate(points):
            x2, y2 = points[(idx + 1) % len(points)]
            total += x1 * y2 - x2 * y1
        return abs(total / 2.0)


def line_length(points: Sequence[Point2D]) -> float:
    if len(points) < 2:
        return 0.0
    try:
        return float(LineString(points).length)
    except Exception:
        total = 0.0
        for left, right in zip(points, points[1:]):
            total += math.dist(left, right)
        return total


def geometry_to_shapely(node: Dict) -> Optional[object]:
    geometry = node.get("geometry", {})
    gtype = geometry.get("type")
    points = geometry.get("points") or geometry.get("sampledPoints") or []
    if gtype in {"Polygon", "Rect"} and len(points) >= 3:
        try:
            poly = Polygon(points)
            return poly if poly.is_valid else poly.buffer(0)
        except Exception:
            return None
    if gtype in {"LineString", "Path"} and len(points) >= 2:
        try:
            return LineString(points)
        except Exception:
            return None
    if gtype == "Point" and len(points) == 2:
        return Point(points[0], points[1])
    return None


def point_in_bbox(point: Sequence[float], bbox: Sequence[float]) -> bool:
    x, y = point
    bx, by, bw, bh = bbox
    return bx <= x <= bx + bw and by <= y <= by + bh


def bbox_center(bbox: Sequence[float]) -> List[float]:
    return [clean_float(bbox[0] + bbox[2] / 2), clean_float(bbox[1] + bbox[3] / 2)]


def bbox_key(bbox: Sequence[float], digits: int = 1) -> Tuple[float, float, float, float]:
    return tuple(round(float(value), digits) for value in bbox)  # type: ignore[return-value]


def distance_between_bboxes(left: Sequence[float], right: Sequence[float]) -> float:
    lx1, ly1, lw, lh = left
    rx1, ry1, rw, rh = right
    lx2, ly2 = lx1 + lw, ly1 + lh
    rx2, ry2 = rx1 + rw, ry1 + rh
    dx = max(rx1 - lx2, lx1 - rx2, 0)
    dy = max(ry1 - ly2, ly1 - ry2, 0)
    return math.hypot(dx, dy)
