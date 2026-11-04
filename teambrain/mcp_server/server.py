"""TeamBrain MCP server — the team memory for any MCP client (Claude Code,
Claude Desktop, Cursor, ...), not just Hermes bots.

Speaks MCP over stdio (newline-delimited JSON-RPC 2.0). Standard library only.

Reads the same store + wiki the Hermes plugin writes, so a teammate can ask
"우리 DB 뭐 쓰기로 했지?" from their editor and get the answer the team's bots
recorded in the messenger.

Privacy: read-only by default. An MCP client gives no signal about whether a
conversation is public or private, so — following the same fail-closed rule as
the Hermes plugin — nothing is ever recorded automatically. The one write tool,
`team_remember`, is exposed only when TEAMBRAIN_MCP_ALLOW_WRITE=1, and records
only the note text the user explicitly asked to share.
"""

from __future__ import annotations

import getpass
import json
import os
import sys
from typing import Any, Callable, Dict, List, Optional, TextIO

from teambrain.memory_provider.store import TeamKnowledgeStore
from teambrain.memory_provider.wiki import TeamWiki

SERVER_NAME = "teambrain"
SERVER_VERSION = "0.1.0"
SUPPORTED_PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")

_MAX_NOTE_CHARS = 2000

_READ_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "team_search",
        "description": (
            "Search the team's shared memory: curated wiki pages first, then raw "
            "conversations teammates had with their bots in public channels. Use this "
            "before answering questions about past team decisions, conventions or facts, "
            "and say who decided it and where."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "What to look for, in natural language."}},
            "required": ["query"],
        },
    },
    {
        "name": "team_wiki_list",
        "description": "List the team wiki pages (slug, title, last updated).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "team_wiki_read",
        "description": "Read one team wiki page in full by its slug (see team_wiki_list).",
        "inputSchema": {
            "type": "object",
            "properties": {"slug": {"type": "string"}},
            "required": ["slug"],
        },
    },
]

_WRITE_TOOL: Dict[str, Any] = {
    "name": "team_remember",
    "description": (
        "Share a note with the whole team's memory. Only call this when the user "
        "explicitly asks to share something with the team. Never include secrets, "
        "personal matters or content from private conversations. Everything recorded "
        "here is visible to every teammate."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "note": {"type": "string", "description": "The decision/fact to share, in the user's words."},
            "topic": {"type": "string", "description": "Optional short topic, e.g. 'DB 선택'."},
        },
        "required": ["note"],
    },
}


def _writes_enabled() -> bool:
    return os.environ.get("TEAMBRAIN_MCP_ALLOW_WRITE", "").strip().lower() in {"1", "true", "yes"}


def _author() -> str:
    name = os.environ.get("TEAMBRAIN_USER", "").strip()
    if name:
        return name
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


class ToolError(Exception):
    """Reported to the client as a tool result with isError=true."""


class TeamBrainMCP:
    def __init__(self, store: Optional[TeamKnowledgeStore] = None, allow_write: Optional[bool] = None) -> None:
        self.store = store or TeamKnowledgeStore()
        self.wiki = TeamWiki(self.store)
        self.allow_write = _writes_enabled() if allow_write is None else allow_write

    # -- tools ---------------------------------------------------------------

    def tools(self) -> List[Dict[str, Any]]:
        return _READ_TOOLS + ([_WRITE_TOOL] if self.allow_write else [])

    def call_tool(self, name: str, args: Dict[str, Any]) -> str:
        handlers: Dict[str, Callable[[Dict[str, Any]], str]] = {
            "team_search": self._search,
            "team_wiki_list": self._wiki_list,
            "team_wiki_read": self._wiki_read,
        }
        if self.allow_write:
            handlers["team_remember"] = self._remember
        handler = handlers.get(name)
        if handler is None:
            raise ToolError(f"unknown tool: {name}")
        return handler(args or {})

    def _search(self, args: Dict[str, Any]) -> str:
        query = str(args.get("query", "")).strip()
        if not query:
            raise ToolError("query is required")
        parts = [p for p in (self.wiki.search(query, limit=3), self.store.search(query)) if p]
        return "\n\n".join(parts) if parts else "No team memory matches this query."

    def _wiki_list(self, _args: Dict[str, Any]) -> str:
        pages = [{"slug": p.slug, "title": p.title, "updated": p.updated} for p in self.wiki.list_pages()]
        return json.dumps({"pages": pages}, ensure_ascii=False)

    def _wiki_read(self, args: Dict[str, Any]) -> str:
        page = self.wiki.get_page(str(args.get("slug", "")))
        if page is None:
            raise ToolError("no such page")
        return json.dumps({"slug": page.slug, "title": page.title, "updated": page.updated,
                           "content": page.content}, ensure_ascii=False)

    def _remember(self, args: Dict[str, Any]) -> str:
        note = str(args.get("note", "")).strip()
        if not note:
            raise ToolError("note is required")
        if len(note) > _MAX_NOTE_CHARS:
            raise ToolError(f"note is too long (max {_MAX_NOTE_CHARS} characters)")
        topic = str(args.get("topic", "")).strip()[:120]
        who = _author()
        self.store.append_entry(
            owner_user_id=who, owner_user_name=who, visibility="team",
            chat_id="", chat_name="", channel_type="explicit-share", platform="mcp",
            profile=who, session_id="", thread_id="",
            user_content=f"[{topic}] {note}" if topic else note,
            assistant_content="",
        )
        return "Shared with the team memory. It will appear in the wiki after the next curation."

    # -- JSON-RPC ------------------------------------------------------------

    def handle(self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle one JSON-RPC message; returns the response, or None for notifications."""
        method = msg.get("method")
        msg_id = msg.get("id")
        if msg_id is None:  # notification (e.g. notifications/initialized)
            return None
        params = msg.get("params") or {}
        try:
            if method == "initialize":
                requested = params.get("protocolVersion")
                result: Dict[str, Any] = {
                    "protocolVersion": requested if requested in SUPPORTED_PROTOCOLS else SUPPORTED_PROTOCOLS[0],
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                    "instructions": (
                        "TeamBrain is the team's shared memory. Before answering questions about "
                        "past team decisions or conventions, call team_search and say who decided "
                        "it and where."
                    ),
                }
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": self.tools()}
            elif method == "tools/call":
                try:
                    text = self.call_tool(str(params.get("name", "")), params.get("arguments") or {})
                    result = {"content": [{"type": "text", "text": text}], "isError": False}
                except ToolError as exc:
                    result = {"content": [{"type": "text", "text": str(exc)}], "isError": True}
            else:
                return _error(msg_id, -32601, f"method not found: {method}")
        except Exception as exc:  # never let one bad request kill the server
            return _error(msg_id, -32603, f"internal error: {exc}")
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def serve(self, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> None:
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                _write(stdout, _error(None, -32700, "parse error"))
                continue
            if not isinstance(msg, dict):
                _write(stdout, _error(None, -32600, "invalid request"))
                continue
            response = self.handle(msg)
            if response is not None:
                _write(stdout, response)


def _error(msg_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _write(stdout: TextIO, obj: Dict[str, Any]) -> None:
    stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    stdout.flush()
