"""Pipeline orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from .entities import build_entities_and_relations, strip_private_shapes
from .exporters import (
    write_debug_report,
    write_html_report,
    write_json,
    write_overlay_svg,
)
from .renovation import (
    write_kitchen_pantry_outputs,
    write_study_room_outputs,
    write_zoned_living_kitchen_dining_outputs,
)
from .svg_parser import SvgParser


def run_pipeline(input_path: str, out_dir: str) -> Dict[str, object]:
    source = Path(input_path)
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)

    parsed = SvgParser(source).parse()
    document = parsed["document"]
    vector_nodes = parsed["vectorNodes"]
    labels = parsed["labels"]
    raw_svg = parsed["rawSvg"]

    entities, relations, warnings = build_entities_and_relations(vector_nodes, labels)
    clean_entities = strip_private_shapes(entities)

    paths = {
        "vector_nodes": output / "vector_nodes.json",
        "labels": output / "labels.json",
        "entities": output / "entities.json",
        "relations": output / "relations.json",
        "debug_report": output / "debug_report.md",
        "overlay_svg": output / "overlay.svg",
        "report_html": output / "report.html",
    }

    write_json(paths["vector_nodes"], {"document": document, "vectorNodes": vector_nodes})
    write_json(paths["labels"], {"document": document, "labels": labels})
    write_json(paths["entities"], {"document": document, "entities": clean_entities})
    write_json(paths["relations"], {"document": document, "relations": relations, "warnings": warnings})
    write_debug_report(paths["debug_report"], document, labels, vector_nodes, clean_entities, relations, warnings)
    write_overlay_svg(paths["overlay_svg"], raw_svg, document, vector_nodes, labels, clean_entities)
    write_html_report(paths["report_html"], str(paths["overlay_svg"]), document, labels, clean_entities, relations, warnings)
    paths.update(write_study_room_outputs(output, raw_svg, document, clean_entities, vector_nodes))
    paths.update(write_kitchen_pantry_outputs(output, raw_svg, document, clean_entities, labels, vector_nodes))
    paths.update(write_zoned_living_kitchen_dining_outputs(output, raw_svg, document, clean_entities, labels, vector_nodes))

    return {
        "document": document,
        "vectorNodes": vector_nodes,
        "labels": labels,
        "entities": clean_entities,
        "relations": relations,
        "warnings": warnings,
        "paths": {key: str(value) for key, value in paths.items()},
    }
