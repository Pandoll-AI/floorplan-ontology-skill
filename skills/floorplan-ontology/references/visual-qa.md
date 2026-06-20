# Visual QA

Use this skill whenever output needs to be checked by sight: `overlay.svg`, proposal overlays, `report.html`, or debug visualizations.

## Goal

Make semantic extraction and renovation proposals visually inspectable. The user should be able to open one HTML file and understand what the pipeline believes.

## Inputs

- Original SVG.
- JSON outputs:
  - `vector_nodes.json`
  - `labels.json`
  - `entities.json`
  - `relations.json`
  - proposal JSON when applicable.
- Generated overlay/report files.

## Required Artifacts

- `overlay.svg` for extraction.
- `report.html` for extraction summary.
- `*_proposal.json` for each design proposal.
- `*_overlay.svg` for each design proposal.
- `*_report.html` for each design proposal.
- `analysis_spatial_performance.json` when spatial metrics are computed.
- `analysis_spatial_overlay.svg` when spatial metrics are computed.
- `analysis_spatial_report.html` when spatial metrics are computed.

## Color Conventions

Extraction overlays:

- Space: translucent blue.
- Wall: black.
- LineGroup: gray dashed.
- Door: orange.
- Window: sky blue.
- Fixture: purple.
- Annotation: gray.
- Needs review: red.

Proposal overlays:

- Added or new space: strong translucent fill.
- Removed wall: red dashed stroke.
- Added wall: solid red or dark stroke.
- Door swing: orange dashed arc.
- Relocated/added storage: purple.
- Flow or relocation cue: blue dashed arrow.

Spatial analysis overlays:

- Circulation graph: blue nodes/edges.
- Main shortest path: solid saturated blue.
- Bottleneck or blocked path: red.
- Ventilation path: teal/cyan arrows.
- Daylight reach: translucent yellow bands.
- Privacy exposure: purple paths/fills.
- Missing input warnings: red dashed callouts.

## QA Workflow

1. Generate all outputs through the CLI or pipeline.
2. Open or render the overlay.
3. Check for:
   - missing expected labels
   - incorrect room/entity placement
   - excessive wall candidates
   - furniture classified as walls
   - door/window candidates offset from walls
   - overlay text hiding critical geometry
   - proposal elements blocking entry or doors
   - analysis scores without visible supporting overlays
   - airflow/daylight arrows implying precision not supported by inputs
4. Fix extraction/proposal code, not the output file by hand.
5. Add or update tests for the observed failure mode.

## Useful Commands

```bash
python3 -m floorplan_ontology.cli \
  --input "Matterport Sample_FCL Floor1.svg" \
  --out out/floorplan-ontology/fcl-floor1

qlmanage -t -s 1600 \
  -o /tmp/floorplan_preview \
  out/floorplan-ontology/fcl-floor1/kitchen_pantry_overlay.svg
```

## Done Criteria

- Overlay layer is appended without damaging the source SVG.
- HTML report opens without a server.
- IDs in report match IDs in JSON and overlay titles.
- Visual issues lead to code/test changes, not manual output edits.
- Spatial metrics are always paired with visual layers and listed unknowns.
