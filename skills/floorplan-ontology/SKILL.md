---
name: floorplan-ontology
description: Parse and reason over SVG floorplans, especially Matterport-style residential SVGs. Use when Codex needs to extract vector nodes, labels, spaces, walls, doors, windows, fixtures, ontology relations, renovation proposals, movement/airflow overlays, or inline-SVG HTML validation reports from an SVG floorplan.
---

# Floorplan Ontology

Use this skill to turn an SVG floorplan into ontology-style JSON plus visual QA artifacts. The bundled Python pipeline is self-contained under `scripts/` and generates JSON, overlay SVG, and Korean inline-SVG HTML reports.

## Quick Start

Install runtime dependencies if they are not already available:

```bash
python3 -m pip install -r scripts/requirements.txt
```

Run the bundled pipeline:

```bash
python3 scripts/run_floorplan_pipeline.py \
  --input "/absolute/path/to/floorplan.svg" \
  --out "/absolute/path/to/out/floorplan-ontology"
```

Validate generated outputs:

```bash
python3 scripts/validate_outputs.py \
  --out "/absolute/path/to/out/floorplan-ontology"
```

## Required Workflow

1. Preserve the source SVG. Do not rewrite the original input unless the user explicitly asks.
2. Run `scripts/run_floorplan_pipeline.py` for extraction and report generation.
3. Inspect at least `debug_report.md`, `report.html`, and the task-specific proposal report when making claims.
4. Prefer the inline-SVG HTML reports for human review. The HTML must include the SVG as `<svg>...</svg>`, not through `<img>`, `<object>`, `<embed>`, or `<iframe>`.
5. Treat renovation outputs as inferred proposals, not structural, legal, MEP, or permit decisions.

## Output Contract

The default pipeline writes:

- `vector_nodes.json`: SVG element ids, tags, geometry, bbox, centroid, style, category candidates.
- `labels.json`: merged text labels, label type, room names, dimensions, anchor, linked entity.
- `entities.json`: Space, Wall, Door, Window, Fixture, Annotation, and line-group entities.
- `relations.json`: contains, locatedIn, boundedBy, locatedOn, connects, opensInto.
- `debug_report.md`: counts, merge summary, labels, warnings.
- `overlay.svg`: original SVG plus ontology overlay.
- `report.html`: Korean static report with inline SVG and summary tables.
- `study_room_*`: proposal for splitting a study room from living space.
- `kitchen_pantry_*`: proposal for converting pantry to kitchen and relocating pantry storage.
- `zoned_living_kitchen_dining_*`: proposal separating kitchen, dining, and living zones with movement and airflow overlays.

## Interpretation Rules

- Keep machine-readable JSON ids and codes stable.
- In user-facing HTML or explanations, translate booleans to readable language such as `예` and `아니요`.
- Expand internal tags such as `low_sliding_openings` into natural-language explanations.
- Mark uncertain door/window/flow inference as review-needed instead of overclaiming.
- For movement analysis, route arrows through explicit doors or openings.
- For ventilation analysis, show whole-floor qualitative airflow coverage unless the user asks for a narrower view.

## References

Load only the reference needed for the current task:

- `references/03-processing-pipeline.md`: end-to-end extraction workflow.
- `references/04-intermediate-representation.md`: JSON/IR structure.
- `references/05-extraction-strategy.md`: SVG preprocessing, labels, walls, doors, windows.
- `references/06-analysis-modules.md`: movement graph, airflow, daylight, structural heuristics.
- `references/07-validation-and-roadmap.md`: validation artifacts and future MVP stages.
- `references/svg-forensics.md`: low-level SVG inspection workflow.
- `references/ontology-extraction.md`: entity/relation extraction rules.
- `references/spatial-analysis.md`: graph, airflow, daylight, and spatial reasoning.
- `references/renovation-proposal.md`: proposal generation and caution rules.
- `references/visual-qa.md`: overlay and HTML QA rules.
- `references/evidence-governance.md`: confidence, evidence, and review status rules.

## Common Commands

Run on the Matterport sample from a repo root:

```bash
python3 scripts/run_floorplan_pipeline.py \
  --input "Matterport Sample_FCL Floor1.svg" \
  --out "out/floorplan-ontology/fcl-floor1"
```

Check for raw machine codes leaking into reports:

```bash
rg "True|False|low_sliding_openings|window operability" out/floorplan-ontology/fcl-floor1/*.html
```
