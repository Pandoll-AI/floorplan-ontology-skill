#!/usr/bin/env python3
"""Validate expected floorplan ontology outputs from a pipeline run."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REQUIRED_FILES = [
    "vector_nodes.json",
    "labels.json",
    "entities.json",
    "relations.json",
    "debug_report.md",
    "overlay.svg",
    "report.html",
    "study_room_proposal.json",
    "study_room_overlay.svg",
    "study_room_report.html",
    "kitchen_pantry_proposal.json",
    "kitchen_pantry_overlay.svg",
    "kitchen_pantry_report.html",
    "zoned_living_kitchen_dining_proposal.json",
    "zoned_living_kitchen_dining_overlay.svg",
    "zoned_living_kitchen_dining_report.html",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate floorplan ontology output directory.")
    parser.add_argument("--out", required=True, help="Output directory from run_floorplan_pipeline.py.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    out_dir = Path(args.out)
    missing = [name for name in REQUIRED_FILES if not (out_dir / name).exists()]
    if missing:
        for name in missing:
            print(f"missing: {name}", file=sys.stderr)
        raise SystemExit(1)

    html_reports = [
        "report.html",
        "study_room_report.html",
        "kitchen_pantry_report.html",
        "zoned_living_kitchen_dining_report.html",
    ]
    for name in html_reports:
        text = (out_dir / name).read_text(encoding="utf-8")
        if '<div class="svg-panel"><svg' not in text:
            print(f"html report does not embed inline SVG: {name}", file=sys.stderr)
            raise SystemExit(1)
        for disallowed in ("<img", "<object", "<embed", "<iframe"):
            if disallowed in text:
                print(f"html report contains external/embed tag {disallowed}: {name}", file=sys.stderr)
                raise SystemExit(1)

    print(f"ok: {out_dir}")


if __name__ == "__main__":
    main()
