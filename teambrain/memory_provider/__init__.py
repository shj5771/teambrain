"""TeamBrain memory plugin — shared team-knowledge MemoryProvider.

Every Hermes profile that activates this provider (memory.provider: teambrain
in that profile's config.yaml) reads from and writes to the SAME shared
store, regardless of which profile (= which person's bot) handled the turn —
subject to the MVP visibility rule in visibility.py: only turns from a fully
open Mattermost channel are ever persisted. DMs and private channels are
never written to the shared store.

See docs/visibility-rule.md for the design rationale.

Store location: ~/.hermes/team_knowledge/store.jsonl (outside any single
profile's HERMES_HOME, so profiles genuinely share it).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from agent.memory_provider import MemoryProvider

from .store import TeamKnowledgeStore
from .visibility import resolve_visibility, should_sync

logger = logging.getLogger(__name__)

# agent_context values that represent a real, primary user-facing turn.
# Cron jobs, subagents, and context-flush passes should never be written to
# the shared team store as if they were real team conversation — matches
# the convention already used by the honcho/supermemory bundled providers.
_SYNCABLE_AGENT_CONTEXTS = frozenset({"", "primary"})


class TeamBrainMemoryProvider(MemoryProvider):
    """Shared team-knowledge provider, filtered by the MVP visibility rule."""

    def __init__(self) -> None:
        self._store = TeamKnowledgeStore()
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
            "injected below as [TeamBrain] context before your turn. Only "
            "conversations from fully open team channels are ever captured here "
            "— direct messages and private channels are never included."
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        return self._store.search(query)

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
            owner_user_name=self._user_name,
            visibility=visibility,
            chat_id=self._chat_id,
            chat_name=self._chat_name,
            channel_type=str(self._chat_type),
            platform=self._platform,
            profile=self._profile,
            session_id=session_id or self._session_id,
            thread_id=self._thread_id,
            user_content=user_content,
            assistant_content=assistant_content,
        )

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return []


def register(ctx) -> None:
    ctx.register_memory_provider(TeamBrainMemoryProvider())
