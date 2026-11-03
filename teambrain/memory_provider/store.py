"""JSONL-backed shared store for TeamBrain entries.

One flat file, shared across every Hermes profile that activates this
provider (memory.provider: teambrain). One Mattermost team per store is
assumed for now, so a flat file is sufficient — chat_id/chat_name are captured
per-entry so a future multi-team split can filter/partition without a schema
migration. See docs/visibility-rule.md.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_DEFAULT_STORE_PATH = Path.home() / ".hermes" / "team_knowledge" / "store.jsonl"
_MAX_PREFETCH_HITS = 5


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9가-힣]+", text.lower()))


class TeamKnowledgeStore:
    """Thread-safe append/read access to the shared JSONL store."""

    def __init__(self, store_path: Optional[Path] = None) -> None:
        self.path = store_path or _DEFAULT_STORE_PATH
        self._lock = threading.Lock()

    def append_entry(
        self,
        *,
        owner_user_id: str,
        owner_user_name: str,
        visibility: str,
        chat_id: str,
        chat_name: str,
        channel_type: str,
        platform: str,
        profile: str,
        session_id: str,
        thread_id: str,
        user_content: str,
        assistant_content: str,
    ) -> None:
        entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "owner": {"user_id": owner_user_id, "user_name": owner_user_name},
            "visibility": visibility,
            "chat_id": chat_id,
            "chat_name": chat_name,
            "channel_type": channel_type,
            "platform": platform,
            "profile": profile,
            "session_id": session_id,
            "thread_id": thread_id,
            "user": user_content[:2000],
            "assistant": (assistant_content or "")[:2000],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def read_all(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        entries = []
        with self._lock:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except Exception:
                    continue
        return entries

    def search(self, query: str) -> str:
        """Keyword-overlap search (MVP — no embeddings, see design note for
        why this is intentionally out of scope for now)."""
        query_tokens = _tokenize(query)
        if not query_tokens:
            return ""
        entries = self.read_all()
        scored = []
        for e in entries:
            blob = f"{e.get('user', '')} {e.get('assistant', '')}"
            overlap = query_tokens & _tokenize(blob)
            if overlap:
                scored.append((len(overlap), e))
        scored.sort(key=lambda t: t[0], reverse=True)
        hits = scored[:_MAX_PREFETCH_HITS]
        if not hits:
            return ""
        lines = ["[TeamBrain] Relevant team knowledge from other profiles/teammates:"]
        for _, e in hits:
            owner = e.get("owner", {}) or {}
            who = owner.get("user_name") or owner.get("user_id") or e.get("profile", "unknown")
            chat_name = e.get("chat_name", "")
            when = e.get("timestamp", "")
            where = f" in #{chat_name}" if chat_name else ""
            lines.append(f"- ({who}{where}, {when}) {e.get('user', '')} -> {e.get('assistant', '')}")
        return "\n".join(lines)
