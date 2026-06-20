"""Export JSON, SVG overlay, HTML, and debug reports."""

from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from .geometry import clean_float


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_debug_report(path: Path, document: Dict, labels: List[Dict], vector_nodes: List[Dict], entities: List[Dict], relations: List[Dict], warnings: List[Dict]) -> None:
    tag_counts = Counter(node["sourceTag"] for node in vector_nodes)
    label_counts = Counter(label["labelType"] for label in labels)
    entity_counts = Counter(entity["type"] for entity in entities)
    raw_wall_candidate_count = sum(
        1
        for node in vector_nodes
        if any(candidate.get("category") == "wall_candidate" for candidate in node.get("categoryCandidates", []))
    )
    merged_wall_count = entity_counts.get("Wall", 0)
    line_group_count = entity_counts.get("LineGroup", 0)
    lines = [
        "# Floorplan Ontology Debug Report",
        "",
        f"- Source: `{document.get('sourceFile')}`",
        f"- ViewBox: `{document.get('viewBox')}`",
        "",
        "## SVG Tag Counts",
        "",
    ]
    for key, value in sorted(tag_counts.items()):
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Label Counts", ""])
    for key, value in sorted(label_counts.items()):
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Entity Counts", ""])
    for key, value in sorted(entity_counts.items()):
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Line Merge Summary",
            "",
            f"- Raw wall-like vector candidates: {raw_wall_candidate_count}",
            f"- Merged wall entities: {merged_wall_count}",
            f"- Grouped non-wall line clusters: {line_group_count}",
        ]
    )
    lines.extend(["", "## Labels", ""])
    for label in labels:
        lines.append(
            f"- `{label['id']}` {label['labelType']} `{label['name']}` -> `{label.get('linkedEntityId')}`"
        )
    lines.extend(["", "## Warnings", ""])
    if not warnings:
        lines.append("- None")
    else:
        for warning in warnings:
            lines.append(f"- `{warning.get('type')}` {warning.get('labelId', '')}: {warning.get('message')}")
    lines.extend(["", "## Relation Count", "", f"- {len(relations)}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_overlay_svg(path: Path, raw_svg: str, document: Dict, vector_nodes: List[Dict], labels: List[Dict], entities: List[Dict]) -> None:
    overlay = build_overlay_group(vector_nodes, labels, entities)
    if "</svg>" in raw_svg:
        output = raw_svg.replace("</svg>", overlay + "</svg>", 1)
    else:
        viewbox = " ".join(str(value) for value in document.get("viewBox", [0, 0, 1000, 1000]))
        output = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}">{overlay}</svg>'
    path.write_text(output, encoding="utf-8")


def build_overlay_group(vector_nodes: List[Dict], labels: List[Dict], entities: List[Dict]) -> str:
    node_by_id = {node["id"]: node for node in vector_nodes}
    entity_by_id = {entity["id"]: entity for entity in entities}
    lines = [
        '<g id="ontology-overlay" pointer-events="none">',
        '<style><![CDATA[',
        ".ontology-space{fill:#2f80ed;fill-opacity:.16;stroke:#2f80ed;stroke-width:3;}",
        ".ontology-wall{fill:none;stroke:#111;stroke-width:4;stroke-opacity:.65;}",
        ".ontology-linegroup{fill:none;stroke:#7b8794;stroke-width:2;stroke-opacity:.75;stroke-dasharray:5 5;}",
        ".ontology-door{fill:#f2994a;fill-opacity:.2;stroke:#f2994a;stroke-width:4;}",
        ".ontology-window{fill:#56ccf2;fill-opacity:.35;stroke:#008eb8;stroke-width:3;}",
        ".ontology-fixture{fill:#9b51e0;fill-opacity:.28;stroke:#9b51e0;stroke-width:3;}",
        ".ontology-annotation{fill:#999;fill-opacity:.18;stroke:#777;stroke-width:2;}",
        ".ontology-review{fill:none;stroke:#eb5757;stroke-width:4;stroke-dasharray:10 8;}",
        ".ontology-label{fill:#111;font-family:Arial,sans-serif;font-size:18px;font-weight:bold;}",
        ".ontology-link{stroke:#eb5757;stroke-width:2;stroke-dasharray:4 4;}",
        "]]></style>",
    ]
    for entity in entities:
        css_class = entity_css_class(entity)
        computed_shape = overlay_shape_for_computed_geometry(entity, css_class)
        if computed_shape:
            lines.append(computed_shape)
            if entity.get("type") in {"Wall", "LineGroup"}:
                continue
        for ref in entity.get("geometryRefs", []) or []:
            node = node_by_id.get(ref)
            if node:
                shape = overlay_shape_for_node(node, css_class)
                if shape:
                    lines.append(shape)
        if entity.get("status") == "needs_review" and entity.get("bbox"):
            lines.append(rect_markup(entity["bbox"], "ontology-review", entity["id"]))

    for label in labels:
        anchor = label.get("anchor")
        if not anchor:
            continue
        x, y = anchor
        lines.append(f'<circle cx="{x}" cy="{y}" r="6" fill="#eb5757" opacity=".8"><title>{html.escape(label["id"])}</title></circle>')
        lines.append(f'<text class="ontology-label" x="{x + 8}" y="{y - 8}">{html.escape(str(label.get("name") or ""))}</text>')
        linked = label.get("linkedEntityId")
        entity = entity_by_id.get(linked)
        if entity and entity.get("centroid"):
            cx, cy = entity["centroid"]
            lines.append(f'<line class="ontology-link" x1="{x}" y1="{y}" x2="{cx}" y2="{cy}"/>')
    lines.append("</g>")
    return "".join(lines)


def entity_css_class(entity: Dict) -> str:
    etype = entity.get("type")
    if etype in {"Room", "Storage", "OutdoorArea", "CirculationSpace"}:
        return "ontology-space"
    if etype == "Wall":
        return "ontology-wall"
    if etype == "LineGroup":
        return "ontology-linegroup"
    if etype == "Door":
        return "ontology-door"
    if etype == "Window":
        return "ontology-window"
    if etype == "Fixture":
        return "ontology-fixture"
    if etype == "Annotation":
        return "ontology-annotation"
    return "ontology-review"


def overlay_shape_for_computed_geometry(entity: Dict, css_class: str) -> str:
    geometry = entity.get("computedGeometry") or {}
    points = geometry.get("points") or []
    if geometry.get("type") != "LineString" or len(points) < 2:
        return ""
    title = html.escape(entity.get("id", ""))
    if len(points) == 2:
        return f'<line class="{css_class}" x1="{points[0][0]}" y1="{points[0][1]}" x2="{points[1][0]}" y2="{points[1][1]}"><title>{title}</title></line>'
    return f'<polyline class="{css_class}" points="{points_attr(points)}"><title>{title}</title></polyline>'


def overlay_shape_for_node(node: Dict, css_class: str) -> str:
    geometry = node.get("geometry", {})
    gtype = geometry.get("type")
    title = html.escape(node.get("id", ""))
    if gtype in {"Polygon", "Rect"}:
        points = geometry.get("points", [])
        if points:
            return f'<polygon class="{css_class}" points="{points_attr(points)}"><title>{title}</title></polygon>'
    if gtype == "LineString":
        points = geometry.get("points", [])
        if len(points) == 2:
            return f'<line class="{css_class}" x1="{points[0][0]}" y1="{points[0][1]}" x2="{points[1][0]}" y2="{points[1][1]}"><title>{title}</title></line>'
        if points:
            return f'<polyline class="{css_class}" points="{points_attr(points)}"><title>{title}</title></polyline>'
    if gtype == "Path":
        d = html.escape(geometry.get("pathData", ""))
        return f'<path class="{css_class}" d="{d}"><title>{title}</title></path>'
    bbox = node.get("bbox")
    if bbox:
        return rect_markup(bbox, css_class, title)
    return ""


def points_attr(points: Sequence[Sequence[float]]) -> str:
    return " ".join(f"{clean_float(point[0])},{clean_float(point[1])}" for point in points)


def rect_markup(bbox: Sequence[float], css_class: str, title: str) -> str:
    x, y, width, height = bbox
    return f'<rect class="{css_class}" x="{x}" y="{y}" width="{width}" height="{height}"><title>{html.escape(title)}</title></rect>'


def write_html_report(path: Path, overlay_svg: str, document: Dict, labels: List[Dict], entities: List[Dict], relations: List[Dict], warnings: List[Dict]) -> None:
    svg_markup = Path(overlay_svg).read_text(encoding="utf-8")
    summary = {
        "라벨": len(labels),
        "엔티티": len(entities),
        "관계": len(relations),
        "검토 필요": len(warnings),
    }
    html_text = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>평면도 온톨로지 리포트</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; color: #1f2933; background: #f6f8fa; }}
    header {{ padding: 18px 24px; background: #111827; color: white; }}
    main {{ padding: 20px 24px 40px; }}
    .summary {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 18px; }}
    .metric {{ background: white; border: 1px solid #d8dee4; border-radius: 6px; padding: 10px 14px; min-width: 120px; }}
    .metric strong {{ display: block; font-size: 24px; }}
    .svg-panel {{ background: white; border: 1px solid #d8dee4; border-radius: 6px; overflow: auto; max-height: 78vh; margin-bottom: 22px; }}
    .svg-panel svg {{ width: 100%; height: auto; display: block; }}
    section {{ background: white; border: 1px solid #d8dee4; border-radius: 6px; padding: 16px; margin-bottom: 18px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid #eaeef2; padding: 7px 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f1f5f9; position: sticky; top: 0; }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
  </style>
</head>
<body>
  <header>
    <h1>평면도 온톨로지 리포트</h1>
    <div>{html.escape(str(document.get("sourceFile")))}</div>
  </header>
  <main>
    <div class="summary">
      {''.join(f'<div class="metric"><strong>{value}</strong>{html.escape(key)}</div>' for key, value in summary.items())}
    </div>
    <div class="svg-panel">{svg_markup}</div>
    {table_section("라벨", labels, ["id", "labelType", "name", "dimensionText", "linkedEntityId", "confidence"])}
    {table_section("엔티티", entities, ["id", "type", "subtype", "name", "status", "confidence", "evidence"])}
    {table_section("관계", relations, ["id", "type", "from", "to", "confidence", "evidence"])}
    {table_section("검토 필요 항목", warnings, ["type", "labelId", "message"])}
  </main>
</body>
</html>
"""
    path.write_text(html_text, encoding="utf-8")


def table_section(title: str, rows: List[Dict], columns: List[str]) -> str:
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{cell(row.get(col))}</td>" for col in columns) + "</tr>")
    if not body:
        body.append(f'<tr><td colspan="{len(columns)}">없음</td></tr>')
    header = "".join(f"<th>{html.escape(column_title(col))}</th>" for col in columns)
    return f"<section><h2>{html.escape(title)}</h2><table><thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table></section>"


def column_title(column: str) -> str:
    return {
        "id": "내부 식별자",
        "labelType": "라벨 유형",
        "name": "이름",
        "dimensionText": "치수 텍스트",
        "linkedEntityId": "연결된 엔티티",
        "confidence": "신뢰도",
        "type": "유형",
        "subtype": "세부 유형",
        "status": "상태",
        "evidence": "근거",
        "from": "출발",
        "to": "도착",
        "labelId": "라벨 식별자",
        "message": "메시지",
    }.get(column, column)


def display_value(value: str) -> str:
    return {
        "room_name": "방 이름",
        "fixture": "설비",
        "annotation": "주석",
        "dimension": "치수",
        "Room": "방",
        "Storage": "수납 공간",
        "OutdoorArea": "외부 공간",
        "CirculationSpace": "이동 공간",
        "Wall": "벽",
        "Door": "문",
        "Window": "창문",
        "Fixture": "설비",
        "Annotation": "주석",
        "LineGroup": "선 그룹",
        "contains": "포함",
        "locatedIn": "내부에 위치",
        "boundedBy": "경계가 됨",
        "locatedOn": "위에 위치",
        "connects": "연결",
        "opensInto": "열리는 방향",
        "needs_review": "검토 필요",
    }.get(value, value)


def localized_data(value: object) -> object:
    if value is True:
        return "예"
    if value is False:
        return "아니요"
    if isinstance(value, str):
        return display_value(value)
    if isinstance(value, list):
        return [localized_data(item) for item in value]
    if isinstance(value, dict):
        return {column_title(str(key)): localized_data(val) for key, val in value.items()}
    return value


def cell(value: object) -> str:
    if value is True:
        return "예"
    if value is False:
        return "아니요"
    if isinstance(value, (list, dict)):
        return f"<code>{html.escape(json.dumps(localized_data(value), ensure_ascii=False))}</code>"
    if value is None:
        return ""
    if isinstance(value, str):
        return html.escape(display_value(value))
    return html.escape(str(value))
