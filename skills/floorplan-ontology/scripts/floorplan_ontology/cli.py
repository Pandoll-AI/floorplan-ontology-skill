"""Command-line interface for the floorplan ontology pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract ontology-style IR from a Matterport SVG floorplan.")
    parser.add_argument("--input", required=True, help="Input SVG file path.")
    parser.add_argument("--out", required=True, help="Output directory.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    result = run_pipeline(args.input, args.out)
    summary = {
        "source": Path(args.input).name,
        "out": args.out,
        "vectorNodes": len(result["vectorNodes"]),
        "labels": len(result["labels"]),
        "entities": len(result["entities"]),
        "relations": len(result["relations"]),
        "warnings": len(result["warnings"]),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

