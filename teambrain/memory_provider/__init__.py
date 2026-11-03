"""TeamBrain memory plugin — shared team-knowledge MemoryProvider.

Every Hermes profile that activates this provider (memory.provider: teambrain
in that profile's config.yaml) reads from and writes to the SAME shared
store, regardless of which profile (= which person's bot) handled the turn —
subject to the MVP visibility rule in visibility.py: only turns from a fully
open Mattermost channel are ever persisted. DMs and private channels are
never written to the shared store.

See docs/visibility-rule.md for the design rationale.

Team wiki (wiki.py): every few new entries, Hermes' own model folds the raw
store into curated Markdown topic pages (decisions, facts, how-tos) under
~/.hermes/team_knowledge/wiki/. prefetch() serves curated pages first and raw
conversations second.

Store location: ~/.hermes/team_knowledge/store.jsonl (outside any single
profile's HERMES_HOME, so profiles genuinely share it).
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Dict, List

try:
    from agent.memory_provider import MemoryProvider
except ImportError:  # outside Hermes (unit tests, CLI): plain base class
    MemoryProvider = object  # type: ignore[misc,assignment]

from .store import TeamKnowledgeStore
from .visibility import resolve_visibility, should_sync
from .names import channel_name, person_name
from .wiki import TeamWiki

logger = logging.getLogger(__name__)

# agent_context values that represent a real, primary user-facing turn.
# Cron jobs, subagents, and context-flush passes should never be written to
# the shared team store as if they were real team conversation — matches
# the convention already used by the honcho/supermemory bundled providers.
_SYNCABLE_AGENT_CONTEXTS = frozenset({"", "primary"})

# Curate the wiki once this many new entries have piled up.
# 0 disables automatic curation (run `python -m teambrain.memory_provider curate` instead).
_CURATE_EVERY = int(os.environ.get("TEAMBRAIN_CURATE_EVERY", "5") or 0)

_TOOL_SCHEMAS = [
    {
        "name": "team_wiki_list",
        "description": "List all pages in the team wiki (curated team decisions, facts, how-tos).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "team_wiki_read",
        "description": "Read one team wiki page in full by its slug (see team_wiki_list).",
        "parameters": {
            "type": "object",
            "properties": {"slug": {"type": "string", "description": "Page slug, e.g. database-choice"}},
            "required": ["slug"],
        },
    },
]


class TeamBrainMemoryProvider(MemoryProvider):
    """Shared team-knowledge provider, filtered by the MVP visibility rule."""

    def __init__(self) -> None:
        self._store = TeamKnowledgeStore()
        self._wiki = TeamWiki(self._store)
        self._curate_every = _CURATE_EVERY
        self._profile = "unknown"
        self._platform = "unknown"
        self._user_id = "unknown"
        self._user_name = "unknown"
        self._chat_id = ""
        self._chat_name = ""
        self._thread_id = ""
        self._chat_type: str | None = None
        self._agent_context = "primary"
        self._session_id = ""

    @property
    def name(self) -> str:
        return "teambrain"

    def is_available(self) -> bool:
        # Local-only, no credentials required. Still opt-in only, since
        # activation always requires memory.provider: teambrain in a
        # profile's own config.yaml.
        return True

    def initialize(self, session_id: str, **kwargs: Any) -> None:
        self._profile = str(kwargs.get("agent_identity", "unknown"))
        self._platform = str(kwargs.get("platform", "unknown"))
        self._user_id = str(kwargs.get("user_id", "unknown"))
        self._user_name = str(kwargs.get("user_name", self._user_id))
        self._chat_id = str(kwargs.get("chat_id", ""))
        self._chat_name = str(kwargs.get("chat_name", ""))
        self._thread_id = str(kwargs.get("thread_id", ""))
        # sync_turn() doesn't get chat_type/agent_context re-passed to it,
        # so both must be cached here from initialize().
        self._chat_type = kwargs.get("chat_type")
        self._agent_context = str(kwargs.get("agent_context", "primary"))
        self._session_id = session_id
        logger.info(
            "TeamBrain provider initialized: profile=%s platform=%s user=%s "
            "chat_id=%s chat_type=%s",
            self._profile, self._platform, self._user_name,
            self._chat_id, self._chat_type,
        )

    def system_prompt_block(self) -> str:
        return (
            "# TeamBrain\n"
            "You have access to a shared team knowledge store. Relevant entries "
            "from teammates (across different Hermes profiles/bots) may be "
            "injected below as [TeamBrain] context before your turn: curated "
            "team wiki pages first, then raw conversations. When you use this "
            "knowledge, say who decided it and when. Use team_wiki_list / "
            "team_wiki_read to browse the wiki. Only conversations from fully "
            "open team channels are ever captured here — direct messages and "
            "private channels are never included."
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        parts = [self._wiki.search(query), self._store.search(query, limit=3)]
        return "\n\n".join(p for p in parts if p)

    def sync_turn(
        self,
        user_content: str,
        assistant_content: str,
        *,
        session_id: str = "",
        messages: Any = None,
    ) -> None:
        if not user_content:
            return

        # Guard 1: only primary, user-facing turns (matches honcho/supermemory
        # convention — cron/subagent/flush passes never hit the shared store).
        # Cached from initialize() since sync_turn() itself doesn't receive
        # agent_context.
        if self._agent_context not in _SYNCABLE_AGENT_CONTEXTS:
            return

        # Guard 2 (the MVP rule): only fully open channels get persisted.
        if not should_sync(self._chat_type):
            return

        visibility = resolve_visibility(self._chat_type)
        self._store.append_entry(
            owner_user_id=self._user_id,
            owner_user_name=person_name(self._platform, self._user_id, self._user_name),
            visibility=visibility,
            chat_id=self._chat_id,
            chat_name=self._chat_name or channel_name(self._platform, self._chat_id),
            channel_type=str(self._chat_type),
            platform=self._platform,
            profile=self._profile,
            session_id=session_id or self._session_id,
            thread_id=self._thread_id,
            user_content=user_content,
            assistant_content=assistant_content,
        )

        self._maybe_curate_in_background()

    # -- team wiki -----------------------------------------------------------

    def _maybe_curate_in_background(self) -> None:
        if self._curate_every <= 0:
            return
        try:
            if self._wiki.pending_count() < self._curate_every:
                return
        except OSError:
            return
        threading.Thread(target=self._curate_safely, name="teambrain-wiki", daemon=True).start()

    def _curate_safely(self) -> None:
        try:
            self._wiki.curate()
        except Exception:  # never let wiki curation break a chat turn
            logger.exception("TeamBrain wiki curation failed (will retry later)")

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        if self._curate_every > 0 and self._wiki.pending_count() > 0:
            self._curate_safely()

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return _TOOL_SCHEMAS

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs: Any) -> str:
        if tool_name == "team_wiki_list":
            pages = [{"slug": p.slug, "title": p.title, "updated": p.updated} for p in self._wiki.list_pages()]
            return json.dumps({"pages": pages}, ensure_ascii=False)
        if tool_name == "team_wiki_read":
            page = self._wiki.get_page(str(args.get("slug", "")))
            if page is None:
                return json.dumps({"error": "page not found"})
            return json.dumps({"slug": page.slug, "title": page.title, "updated": page.updated,
                               "content": page.content}, ensure_ascii=False)
        return json.dumps({"error": f"unknown tool {tool_name}"})


def register(ctx) -> None:
    ctx.register_memory_provider(TeamBrainMemoryProvider())
