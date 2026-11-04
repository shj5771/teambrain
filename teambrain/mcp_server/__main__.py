"""Run the TeamBrain MCP server over stdio.

    python3 -m teambrain.mcp_server            # store: ~/.hermes/team_knowledge/store.jsonl
    TEAMBRAIN_STORE=/path/store.jsonl python3 -m teambrain.mcp_server
"""

from __future__ import annotations

import logging
import sys

from .server import TeamBrainMCP


def main() -> int:
    # stdout is the protocol channel; anything else must go to stderr.
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    TeamBrainMCP().serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
