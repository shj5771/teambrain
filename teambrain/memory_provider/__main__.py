"""TeamBrain wiki CLI.

    python3 -m teambrain.memory_provider status
    python3 -m teambrain.memory_provider list
    python3 -m teambrain.memory_provider show <slug>

    # curate needs Hermes' model, so run it with Hermes' Python:
    ~/.hermes/hermes-agent/venv/bin/python -m teambrain.memory_provider curate
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .store import TeamKnowledgeStore
from .wiki import TeamWiki


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m teambrain.memory_provider", description="TeamBrain team wiki")
    parser.add_argument("--store", type=Path, help="store.jsonl path (default: ~/.hermes/team_knowledge/store.jsonl)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="entries stored / waiting to be curated / wiki pages")
    sub.add_parser("list", help="list wiki pages")
    show = sub.add_parser("show", help="print one wiki page")
    show.add_argument("slug")
    sub.add_parser("curate", help="fold new entries into the wiki now (uses Hermes' model)")
    args = parser.parse_args(argv)

    wiki = TeamWiki(TeamKnowledgeStore(args.store))

    if args.cmd == "status":
        print(f"store:   {wiki.store.path}")
        print(f"entries: {len(wiki.store.read_all())}  (waiting to be curated: {wiki.pending_count()})")
        print(f"wiki:    {wiki.dir}  ({len(wiki.list_pages())} pages)")
    elif args.cmd == "list":
        pages = wiki.list_pages()
        if not pages:
            print("(no pages yet)")
        for p in pages:
            print(f"{p.slug:40}  {p.title}  [{p.updated}]")
    elif args.cmd == "show":
        page = wiki.get_page(args.slug)
        if page is None:
            print(f"no such page: {args.slug}", file=sys.stderr)
            return 1
        print(page.to_markdown())
    elif args.cmd == "curate":
        try:
            written = wiki.curate()
        except ImportError:
            print("curate needs Hermes' Python: ~/.hermes/hermes-agent/venv/bin/python -m teambrain.memory_provider curate",
                  file=sys.stderr)
            return 2
        print("updated: " + (", ".join(written) if written else "(nothing new worth recording)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
