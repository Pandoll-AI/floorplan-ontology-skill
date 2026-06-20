# Renovation Proposal

Use this skill when the user asks to change the floorplan: split a room, relocate pantry, expand kitchen, add a door, preserve entry access, or evaluate a design alternative.

## Goal

Represent design changes as an explicit operation graph, not as silent edits to the original SVG.

```text
Existing entities + user intent
 -> constraints
 -> proposed operations
 -> checks
 -> proposal JSON
 -> proposal overlay SVG
 -> proposal report HTML
```

## Supported Operation Types

- `createSpace`
- `removeSpace`
- `expandSpace`
- `shrinkSpace`
- `addWall`
- `removeWall`
- `moveWall`
- `addDoor`
- `removeDoor`
- `addWindow`
- `relocateStorage`
- `addStorageCabinet`
- `assignExistingWindow`

## Required Proposal Shape

```json
{
  "proposalId": "proposal_relocate_pantry_expand_kitchen_001",
  "title": "Convert the existing pantry into kitchen area and relocate pantry storage nearby",
  "sourceDocument": "Matterport Sample_FCL Floor1.svg",
  "sourceSpaces": ["space_kitchen", "space_pantry"],
  "operations": [],
  "checks": {},
  "assumptions": [],
  "status": "proposal_for_review"
}
```

## Constraint Checklist

Always evaluate:

- Entry path is not blocked.
- Required access to affected rooms remains.
- Existing exterior windows are not blocked unless explicitly requested.
- Door swing is represented or marked `unknown`.
- Kitchen/dining circulation is not unnecessarily narrowed.
- Wet wall, appliance, and fixture moves are marked for MEP review.
- Removed walls are marked for structural review unless confirmed non-structural.
- Proposal coordinates remain in `svg_user_unit`.
- Circulation, ventilation, daylight, and privacy deltas are computed through `spatial-analysis` when the required entities exist.

## Placement Heuristics

- Prefer using existing exterior window bands for habitable new rooms.
- Prefer compact cabinet pantry over new walk-in pantry when circulation is tight.
- Keep bedroom, bathroom, entry, and main circulation boundaries intact unless the user explicitly targets them.
- When splitting a large room, place the new door on an internal partition and keep public circulation open.
- When expanding kitchen into pantry, retain the bedroom-side boundary conceptually and remove only the kitchen-side pantry enclosure unless evidence says otherwise.

## Overlay Rules

- Show new/expanded spaces with translucent fill.
- Show added walls and doors clearly.
- Show removed walls as red dashed strokes.
- Label every proposal element with stable IDs or readable names.
- Keep the original SVG intact and append a proposal layer.
- If spatial-analysis runs, include before/after circulation, ventilation, daylight, or privacy layers in the proposal report rather than only numeric deltas.

## Done Criteria

- Proposal JSON contains operation graph and checks.
- Overlay shows exactly what changes.
- HTML report embeds the overlay and tables for operations/checks/assumptions.
- Tests assert the user’s key constraints.
- Functional analysis uses graph/physics proxy formulas and lists missing inputs.
- Functional analysis deltas are visible in overlay/report, not only JSON.
- Structural, MEP, scale, and permit uncertainty are explicitly preserved.
