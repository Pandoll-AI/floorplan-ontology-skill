# Evidence Governance

Use this meta-skill for every floorplan ontology task that makes an interpretation, creates an entity/relation, or proposes a renovation. Its purpose is to stop uncertain geometry from becoming silent truth.

## Apply When

- A label is linked to a space.
- A vector node is promoted to `Wall`, `Door`, `Window`, `Fixture`, `Space`, or `Annotation`.
- A relation such as `connects`, `opensInto`, `locatedOn`, `boundedBy`, or `contains` is created.
- A renovation operation such as `removeWall`, `expandSpace`, `createSpace`, `addDoor`, or `addStorageCabinet` is proposed.
- A user asks for a functional conclusion about circulation, daylight, ventilation, privacy, structure, or convenience.

## Required Fields

Every interpreted object should carry enough of the following fields to be auditable:

```json
{
  "id": "space_kitchen",
  "type": "Room",
  "subtype": "Kitchen",
  "confidence": 0.82,
  "status": "inferred",
  "evidence": ["label_kitchen", "vec_000245"],
  "sourceLabelId": "label_kitchen",
  "geometryRefs": ["vec_000245"],
  "assumptions": ["SVG user units are not calibrated to real-world units"]
}
```

## Status Vocabulary

- `confirmed`: Directly represented in the SVG with strong geometry and label evidence.
- `inferred`: Computed from multiple evidence sources and safe to use downstream.
- `candidate`: Plausible but not strong enough for final reasoning.
- `needs_review`: Ambiguous, visually suspicious, or dependent on missing context.
- `unknown`: The system cannot determine the value from available evidence.
- `proposal_for_review`: A design proposal, not an existing condition.

## Confidence Rules

- `0.90-1.00`: Direct label or exact SVG element evidence.
- `0.70-0.89`: Multiple agreeing geometry signals.
- `0.50-0.69`: Single plausible geometry signal or weak match.
- `<0.50`: Keep as candidate or needs review.

Do not increase confidence because a result looks useful. Confidence must follow evidence quality.

## Hard Boundaries

- Do not claim load-bearing status from this SVG alone.
- Do not claim code compliance from this SVG alone.
- Do not claim real-world dimensions until scale calibration exists.
- Do not silently overwrite original geometry with proposals.
- Do not convert a proposal into an existing entity unless the input SVG already shows it.

## Handoff Checklist

- Source labels and vector IDs are recorded.
- Geometry is in `svg_user_unit` unless explicitly calibrated.
- Uncertain relations are marked `needs_review` or `unknown`.
- Renovation checks separate geometry feasibility from structural/MEP/legal feasibility.
- Overlay/report show the same IDs that appear in JSON.
