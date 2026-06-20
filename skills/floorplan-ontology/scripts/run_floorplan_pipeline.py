#!/usr/bin/env python3
"""Run the bundled floorplan ontology pipeline from this skill package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from floorplan_ontology.pipeline import run_pipeline  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract ontology IR and validation reports from an SVG floorplan."
    )
    parser.add_argument("--input", required=True, help="Input SVG file path.")
    parser.add_argument("--out", required=True, help="Output directory.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = run_pipeline(args.input, args.out)
    summary = {
        "source": Path(args.input).name,
        "out": str(Path(args.out)),
        "vectorNodes": len(result["vectorNodes"]),
        "labels": len(result["labels"]),
        "entities": len(result["entities"]),
        "relations": len(result["relations"]),
        "warnings": len(result["warnings"]),
        "paths": result["paths"],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
