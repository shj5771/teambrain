"""TeamBrain MVP visibility rule.

Isolated on purpose so "the one rule" (private-channel
conversations must never surface in team-wide search) lives in exactly one
place, independently readable/testable.

Known residual gap (not fixable here): Hermes' own Mattermost adapter
(plugins/platforms/mattermost/adapter.py, _CHANNEL_TYPE_MAP) fails OPEN to
"channel" for any channel-type code it doesn't recognize. This function only
controls what TeamBrain does with the chat_type value it is handed — it
cannot see or correct a misclassification that happened upstream, inside
Hermes' own adapter. See docs/visibility-rule.md.
"""

from __future__ import annotations

# MVP: only a fully open Mattermost channel ("O" -> "channel") is
# team-shareable. Direct messages ("dm") and private channels / group DMs
# ("group") are never synced. Anything else (missing/unknown) fails closed.
_SYNCABLE_CHAT_TYPES = frozenset({"channel"})


def should_sync(chat_type: str | None) -> bool:
    """Return True if a turn from this chat_type may be written to the
    shared team-knowledge store.

    Fails closed: missing, empty, or unrecognized chat_type values all
    return False.
    """
    return chat_type in _SYNCABLE_CHAT_TYPES


def resolve_visibility(chat_type: str | None) -> str:
    """Return the visibility tag to store on an entry.

    Only ever called after should_sync() has already returned True, so this
    currently always resolves to "team". Kept as its own function (rather
    than a hardcoded literal in the caller) so a future "explicitly share
    this private note" tool-call path can set a different visibility value
    without touching the entry schema or should_sync().
    """
    return "team"
