# Spatial Analysis

Use this skill when evaluating human circulation, ventilation, daylight, privacy, or functional convenience from extracted floorplan entities and relations.

## Goal

Turn the ontology graph into approximate performance metrics. Use graph theory and first-order building physics, but keep results honest: this SVG pipeline does not yet know calibrated scale, room height, material reflectance, site orientation, weather, or HVAC.

```text
Entities + relations + openings
 -> circulation graph
 -> airflow graph
 -> daylight apertures
 -> scores + warnings + analysis overlay + report
```

## Required Inputs

- Spaces with approximate polygons or bboxes.
- Doors/openings with `connects`, width, and swing state when available.
- Windows with exterior/interior status and approximate opening area.
- Scale calibration if real-world values are required.
- Optional future inputs:
  - ceiling height
  - north orientation
  - window sill/head height
  - glazing transmittance
  - exterior obstruction
  - local weather/wind/solar data

## Visualization Coupling Is Required

Every analysis metric must have a visual explanation. Do not ship a circulation, ventilation, daylight, or privacy score without an overlay layer that shows why the score exists.

Required analysis artifacts:

- `analysis_spatial_performance.json`
- `analysis_spatial_overlay.svg`
- `analysis_spatial_report.html`

Required visual layers:

- `analysis-circulation-layer`
- `analysis-ventilation-layer`
- `analysis-daylight-layer`
- `analysis-privacy-layer` when privacy is computed
- `analysis-warnings-layer`

## Circulation: Graph Network Model

Represent the plan as a weighted graph:

- Node: `Space`, `Door`, `Opening`, `EntryPoint`, `Stair`.
- Edge: walkable connection between nodes.
- Edge weight: travel distance plus penalties.

Recommended edge weight:

```text
cost = distance
     + turnPenalty
     + narrownessPenalty
     + doorPenalty
     + privacyPenalty
     + conflictPenalty
```

Useful metrics:

- Shortest path from `ENTRY` to each major space.
- Mean path length from public spaces to service/private spaces.
- Betweenness centrality for bottleneck spaces.
- Degree centrality for highly connected hubs.
- Articulation points that disconnect major zones.
- Door conflict count along frequent paths.
- Dead-end depth for storage and private rooms.

Initial scoring:

```text
accessScore = clamp(1 - normalizedShortestPathCost, 0, 1)
bottleneckRisk = normalizedBetweenness * narrownessPenalty
privacyRisk = publicToPrivatePathExposure
circulationScore = weightedMean(accessScore, 1 - bottleneckRisk, 1 - conflictRisk)
```

Circulation visualization:

- Draw nodes at space centroids and door/opening centers.
- Draw walkable edges as blue lines.
- Encode edge cost by stroke width or opacity.
- Mark shortest paths from `ENTRY` with solid blue.
- Mark bottlenecks and articulation points in red.
- Mark blocked or uncertain edges as red dashed.
- Label only high-impact nodes to avoid clutter.

## Ventilation: Airflow Graph Approximation

Do not run full Navier-Stokes CFD in the MVP. Start with an airflow graph based on openings and pressure-driven flow.

Represent:

- Node: space air volume.
- Edge: window, door, opening, leakage path.
- Edge capacity: effective opening area.
- Exterior node: outside air.

Wind-driven flow approximation:

```text
Q = Cd * A * sqrt(2 * abs(deltaP) / rho)
deltaP = 0.5 * rho * V^2 * (Cp_windward - Cp_leeward)
```

Where:

- `Q`: airflow rate, m3/s
- `Cd`: discharge coefficient, often 0.6-0.65 for openings
- `A`: effective opening area, m2
- `rho`: air density, about 1.2 kg/m3
- `V`: wind speed, m/s
- `Cp`: pressure coefficient by facade orientation

Stack effect approximation:

```text
Q_stack = Cd * A * sqrt(2 * g * H * abs(deltaT) / T)
```

Where:

- `H`: vertical height between openings, m
- `deltaT`: indoor-outdoor temperature difference, K
- `T`: absolute indoor temperature, K

Air change rate:

```text
ACH = 3600 * Q / roomVolume
```

MVP ventilation score without scale:

```text
crossVentPotential =
  exteriorOpeningCount >= 2
  and openingsAreOnDifferentSides
  and airflowGraphHasPathThroughSpace

ventilationScore = weightedMean(
  exteriorOpeningCoverage,
  crossVentPotential,
  openingPathCapacity,
  doorTransferPotential
)
```

Ventilation visualization:

- Draw exterior openings as cyan markers.
- Draw possible airflow paths as teal arrows.
- Use thicker arrows for higher effective opening capacity.
- Mark cross-ventilation paths with a continuous arrow chain.
- Mark one-sided ventilation as a loop or short arrow to exterior.
- Mark unknown operability or missing area as red/cyan dashed outlines.

## Daylight: First-Order Approximation

Do not claim precise illuminance without orientation, glazing, exterior obstruction, and scale. Start with daylight potential.

Daylight factor definition:

```text
DF = (Ein / Eout) * 100
```

Simple aperture-area estimate:

```text
Ein_avg ≈ Eout * Tvis * windowArea * utilizationFactor * maintenanceFactor / roomFloorArea
```

Where:

- `Ein_avg`: approximate average indoor illuminance
- `Eout`: outdoor horizontal illuminance
- `Tvis`: visible transmittance of glazing
- `windowArea`: glazing/opening area
- `utilizationFactor`: rough geometric efficiency factor
- `maintenanceFactor`: dirt/aging factor
- `roomFloorArea`: floor area

Useful daylight ratios:

```text
WWR = windowArea / exteriorWallArea
apertureToFloorRatio = windowArea / roomFloorArea
daylightDepth ≈ 1.5 to 2.5 * windowHeadHeight
```

MVP daylight score without scale:

```text
daylightScore = weightedMean(
  exteriorWindowPresence,
  apertureToRoomAreaProxy,
  windowDistribution,
  unobstructedDepthProxy
)
```

Daylight visualization:

- Draw exterior windows with yellow aperture markers.
- Draw daylight depth bands from windows into rooms.
- Use translucent yellow fill for expected daylight reach.
- Use darker amber where daylight is weak or blocked.
- Label rooms with daylight potential only when the label does not obscure geometry.
- Show missing orientation/glazing/obstruction as warnings, not as fake precision.

## Privacy And Functional Convenience

Use graph distance and visibility proxies:

- Public-to-private path exposure.
- Number of private spaces crossed by public routes.
- Door adjacency between noisy and quiet rooms.
- Kitchen-to-dining path cost.
- Pantry-to-kitchen path cost.
- Entry-to-living path directness.

Example:

```text
pantryConvenience = 1 - normalizedPathCost(kitchen, pantry)
kitchenDiningConvenience = 1 - normalizedPathCost(kitchen, dining)
studyPrivacy = graphDistance(entry, study) + doorBufferScore - exposureToLiving
```

Privacy and convenience visualization:

- Draw public-to-private route exposure as purple path overlays.
- Mark privacy-sensitive spaces with a low-opacity purple fill.
- Mark pantry-to-kitchen and kitchen-to-dining convenience paths when relevant.
- Use dashed lines for inferred paths that depend on uncertain openings.

## Output Shape

```json
{
  "analysisId": "analysis_spatial_performance_001",
  "status": "inferred",
  "scaleStatus": "svg_user_unit",
  "circulation": {
    "entryPathBlocked": false,
    "shortestPaths": [],
    "bottlenecks": [],
    "score": 0.74
  },
  "ventilation": {
    "method": "airflow_graph_proxy",
    "crossVentilationPotential": "medium",
    "score": 0.58,
    "unknowns": ["window operability", "wind direction", "opening area calibration"]
  },
  "daylight": {
    "method": "aperture_area_proxy",
    "score": 0.62,
    "unknowns": ["north orientation", "glazing transmittance", "exterior obstruction"]
  },
  "visualization": {
    "overlaySvg": "analysis_spatial_overlay.svg",
    "reportHtml": "analysis_spatial_report.html",
    "layers": [
      "analysis-circulation-layer",
      "analysis-ventilation-layer",
      "analysis-daylight-layer"
    ]
  }
}
```

## Done Criteria

- The graph model is explicit and reproducible.
- Scores list their formulas or proxies.
- Missing physics inputs are reported as `unknowns`.
- No result is presented as engineering-grade CFD or daylight simulation.
- Renovation proposals include before/after deltas when possible.
- Every score has a corresponding visual layer in SVG/HTML.
