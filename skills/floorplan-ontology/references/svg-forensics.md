# SVG Forensics

Use this skill when a new SVG is introduced, when extraction quality is poor, or when line grouping/door/window detection needs improvement.

## Goal

Build a factual inventory of the SVG before interpreting it. The output should explain what the file actually contains: tags, styles, transforms, repeated patterns, text anchors, and geometry clusters.

## Inputs

- Source SVG path.
- Existing parser outputs if available:
  - `vector_nodes.json`
  - `labels.json`
  - `debug_report.md`
  - `overlay.svg`

## Workflow

1. Count raw SVG tags by type.
2. Parse CSS classes and identify dominant fill/stroke/stroke-width values.
3. Normalize transforms and verify text anchors after rotation/translation.
4. Build geometry buckets:
   - long horizontal/vertical strokes
   - thin repeated polygons
   - filled large polygons/rects
   - quadratic/arc-like paths
   - small fixture-like details
5. Detect over-fragmentation:
   - many collinear small lines
   - repeated hatch or stair lines
   - duplicated window polygons
   - detail lines that look like walls only by length
6. Produce a short risk list for downstream extraction.

## Useful Commands

```bash
python3 -m floorplan_ontology.cli \
  --input "Matterport Sample_FCL Floor1.svg" \
  --out out/floorplan-ontology/fcl-floor1

python3 - <<'PY'
from collections import Counter
import json
from pathlib import Path
nodes = json.loads(Path("out/floorplan-ontology/fcl-floor1/vector_nodes.json").read_text())["vectorNodes"]
print(Counter(node["sourceTag"] for node in nodes))
PY
```

## Output Shape

```markdown
## SVG Forensics

- Source:
- Tag counts:
- Dominant styles:
- Transform risks:
- Text anchor risks:
- Repeated line clusters:
- Door/window evidence:
- Extraction risks:
- Recommended next parser changes:
```

## Decision Rules

- If lines are numerous, group statistically before promoting walls.
- Treat repeated thin filled polygons on exterior boundaries as window candidates.
- Treat quadratic arc paths near thin leaf polygons as door candidates.
- Treat furniture, stairs, hatches, and cabinet internals as detail groups unless supported by room boundary evidence.
- Preserve raw vector nodes even when grouped; grouping is an interpretation layer, not a deletion step.

## Done Criteria

- Counts explain why extraction will be hard.
- At least one concrete parser or grouping improvement is identified when quality is poor.
- Evidence candidates include source vector IDs or stable SVG element IDs.
