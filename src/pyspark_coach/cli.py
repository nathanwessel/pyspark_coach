"""Customer-side CLI for local static inspection. Never uploads notebook source."""

import argparse
import json
import sys
from pathlib import Path

from pyspark_coach.analyzer import inspect_notebook


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect a PySpark notebook locally; output metadata-only JSON")
    parser.add_argument("notebook", type=Path, help="Local .py or .ipynb notebook")
    parser.add_argument("--pretty", action="store_true", help="Indent JSON output")
    args = parser.parse_args(argv)
    try:
        signals = inspect_notebook(args.notebook)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        # Avoid dumping raw source or filesystem details into shared logs.
        print(f"Inspection failed: {type(exc).__name__}", file=sys.stderr)
        return 2
    print(json.dumps(signals.model_dump(), indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
