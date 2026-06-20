# 중간 표현 구조

## 목적

중간 표현, 즉 IR은 SVG와 온톨로지 사이의 안정적인 데이터 계약이다. 초기부터 RDF나 OWL로 직접 변환하면 도면 해석의 불확실성과 디버깅 정보가 손실되기 쉽다.

따라서 먼저 JSON 기반 IR을 정의하고, 이후 JSON-LD, RDF, graph DB로 확장한다.

## 최상위 구조

```json
{
  "document": {},
  "vectorNodes": [],
  "labels": [],
  "entities": [],
  "relations": [],
  "analysis": {},
  "provenance": {}
}
```

## Document

```json
{
  "id": "doc_matterport_sample_fcl_floor1",
  "sourceFile": "Matterport Sample_FCL Floor1.svg",
  "sourceType": "svg",
  "viewBox": [0, 0, 2896, 2048],
  "coordinateSystem": {
    "origin": "top_left",
    "xAxis": "right",
    "yAxis": "down",
    "unit": "svg_user_unit"
  },
  "floor": {
    "name": "FLOOR 1",
    "level": 1
  }
}
```

## VectorNode

`VectorNode`는 SVG의 도형 또는 텍스트 앵커를 정규화한 원자 단위다.

```json
{
  "id": "vec_000123",
  "sourceElementId": "svg_el_000123",
  "sourceTag": "polygon",
  "geometryType": "polygon",
  "geometry": {
    "type": "Polygon",
    "points": [[2024.77, 980.42], [2024.77, 1465.01]]
  },
  "bbox": [842.45, 145.75, 1212.93, 1485.65],
  "centroid": [1489.2, 950.4],
  "metrics": {
    "area": 1045832.4,
    "length": null,
    "aspectRatio": 1.23
  },
  "style": {
    "fill": "#d9cabf",
    "stroke": "#000",
    "strokeWidth": 0.72
  },
  "zOrder": 42,
  "categoryCandidates": [
    {
      "category": "space_surface_candidate",
      "confidence": 0.74,
      "evidence": ["large_filled_polygon"]
    }
  ]
}
```

## LabelEntity

```json
{
  "id": "label_living_room",
  "sourceElementId": "svg_text_0016",
  "rawText": "LIVING ROOM24'4\" x 18'0\"",
  "normalizedText": "LIVING ROOM 24'4\" x 18'0\"",
  "labelType": "room_label",
  "name": "LIVING ROOM",
  "dimensionText": "24'4\" x 18'0\"",
  "anchor": [1616.83, 1170.46],
  "bbox": [1616.83, 1150.0, 180.0, 45.0],
  "orientationDegrees": 0,
  "style": {
    "fontSize": 20.84,
    "fontFamily": "Verdana"
  },
  "linkedEntityId": "space_living_room",
  "confidence": 0.92
}
```

## SpatialEntity

```json
{
  "id": "space_living_room",
  "type": "Room",
  "subtype": "LivingSpace",
  "labelIds": ["label_living_room"],
  "name": "LIVING ROOM",
  "dimensions": {
    "raw": "24'4\" x 18'0\"",
    "widthFeet": 24.333,
    "depthFeet": 18.0
  },
  "geometryRefs": ["vec_000123"],
  "computedGeometry": {
    "type": "Polygon",
    "source": "inferred_from_surface"
  },
  "bbox": [1233.46, 873.88, 783.83, 587.3],
  "centroid": [1620.0, 1170.0],
  "contains": ["fixture_fireplace_001"],
  "boundedBy": ["wall_001", "wall_002"],
  "status": "inferred",
  "confidence": 0.86
}
```

## Door Entity

```json
{
  "id": "door_001",
  "type": "Door",
  "geometryRefs": ["vec_000240", "vec_000241"],
  "locatedOn": "wall_012",
  "connects": ["space_entry", "space_living_room"],
  "hingePoint": [1365.72, 1628.07],
  "swingArc": {
    "geometryRef": "vec_000241",
    "radius": 79.13,
    "startAngle": 180,
    "endAngle": 270
  },
  "opensInto": "space_entry",
  "swingDirection": "clockwise",
  "clearWidth": {
    "value": 79.13,
    "unit": "svg_user_unit"
  },
  "status": "inferred",
  "confidence": 0.71
}
```

## Window Entity

```json
{
  "id": "window_001",
  "type": "Window",
  "geometryRefs": ["vec_000310", "vec_000311", "vec_000312"],
  "locatedOn": "wall_022",
  "adjacentTo": ["space_kitchen", "exterior"],
  "width": {
    "value": 65.8,
    "unit": "svg_user_unit"
  },
  "openable": "unknown",
  "openingDirection": "unknown",
  "daylightSource": true,
  "ventilationSource": true,
  "status": "inferred",
  "confidence": 0.67
}
```

## Relation

```json
{
  "id": "rel_00001",
  "type": "connects",
  "from": "door_001",
  "to": ["space_entry", "space_living_room"],
  "confidence": 0.78,
  "evidence": ["door_between_two_space_boundaries"]
}
```

## AnalysisResult

```json
{
  "circulation": {
    "graph": {
      "nodes": ["space_entry", "space_living_room", "space_kitchen"],
      "edges": [
        {
          "from": "space_entry",
          "to": "space_living_room",
          "via": "door_001"
        }
      ]
    },
    "findings": []
  },
  "ventilation": {
    "potentialPaths": [],
    "scores": {}
  },
  "daylight": {
    "spaceScores": {}
  }
}
```

## Provenance

모든 추론에는 근거를 남긴다.

```json
{
  "createdBy": "floorplan-ontology-pipeline",
  "pipelineVersion": "0.1.0",
  "sourceHash": "sha256:...",
  "steps": [
    {
      "name": "extract_labels",
      "version": "0.1.0",
      "timestamp": "2026-06-20T00:00:00+09:00"
    }
  ]
}
```

