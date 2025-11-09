from __future__ import annotations

import argparse
import json
from pathlib import Path

import sys

# Ensure project root is on sys.path when executed directly.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.graph_sync import reset_graph, resync_graph  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Neo4j graph maintenance helpers")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("reset", help="Clear all Person and relationship nodes from Neo4j")

    resync_parser = subparsers.add_parser("resync", help="Rebuild Neo4j from SQLite contents")
    resync_parser.add_argument(
        "--clear-first",
        action="store_true",
        help="Clear Neo4j before repopulating",
    )

    args = parser.parse_args()

    if args.command == "reset":
        stats = reset_graph()
    elif args.command == "resync":
        stats = resync_graph(clear_first=args.clear_first)
    else:  # pragma: no cover - argparse guards command set
        parser.error("Unknown command")

    print(json.dumps(stats.as_dict(), indent=2))


if __name__ == "__main__":
    main()
