# Ontology Extraction

Use this skill when implementing or changing extraction of labels, vector nodes, entities, and relations from an SVG floorplan.

## Goal

Convert SVG geometry into a stable, auditable intermediate representation:

```text
SVG -> VectorNode -> LabelEntity -> SpatialEntity -> Relation
```

## Inputs

- Source SVG.
- SVG forensics notes.
- Existing pipeline outputs.
- Target ontology vocabulary.

## Core Entities

- `Room`
- `Storage`
- `OutdoorArea`
- `CirculationSpace`
- `Wall`
- `LineGroup`
- `Door`
- `Window`
- `Fixture`
- `Annotation`

## Core Relations

- `contains`
- `locatedIn`
- `boundedBy`
- `locatedOn`
- `connects`
- `opensInto`
- `adjacentTo`
- `hasLabel`
- `admitsLightTo`
- `admitsAirTo`
- `walkableTo`

## Workflow

1. Preserve every supported SVG element as a `VectorNode`.
2. Expand CSS class styles into computed styles.
3. Apply transforms to geometry and text anchors.
4. Merge `text` and `tspan` into normalized labels.
5. Split room names from dimension text.
6. Separate room/storage/outdoor labels from fixtures and annotations.
7. Classify vector candidates by geometry and style.
8. Group over-fragmented lines before wall promotion.
9. Promote entities only with evidence and confidence.
10. Build relations from labels, geometry proximity, opening evidence, and containment.
11. Export JSON, debug report, overlay, and HTML.

## Label Rules

- Normalize typographic quotes to ASCII quotes.
- Parse labels like `LIVING ROOM24'4" x 18'0"` into `name` and `dimensionText`.
- Treat `FP`, `DW`, appliance labels, logos, area notes, and disclaimers as non-space labels.
- Preserve label orientation; rotated labels often mark narrow storage spaces.

## Geometry Rules

- Large filled surfaces can be space candidates, but labels decide semantic name.
- Long black strokes are wall candidates, not necessarily walls.
- Thin repeated light polygons near exterior boundaries are window candidates.
- Door inference needs swing arc and/or leaf evidence.
- Furniture, cabinets, stairs, and hatches should become `Fixture` or `LineGroup`, not walls.
- Analysis-ready spaces should expose approximate floor area, exterior boundary contact, and opening references when available.
- Analysis-ready openings should expose approximate width/area, exterior/interior status, and operability status when available.

## Testing Rules

Tests should cover:

- SVG tag counts.
- Label extraction and dimension split.
- Annotation exclusion.
- Entity type existence.
- Line grouping reduction.
- Door/window status fields.
- Required output file generation.

## Done Criteria

- Raw vector counts match source expectations.
- Important labels are extracted and typed.
- Entities include confidence/status/evidence where interpretation is involved.
- Relations use the shared vocabulary.
- Ambiguous outputs are visible in overlay/report.
