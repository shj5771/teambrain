"""Best-effort display names for channels and people.

Hermes hands the memory provider a channel *id* but not always its name, and a
username rather than the person's display name. For readable wiki attribution
("— 지민, #dev") we look them up through Mattermost's public REST API with the
bot token Hermes already has in its environment (MATTERMOST_URL /
MATTERMOST_TOKEN). Read-only, cached, short timeout; any failure just returns
the fallback. Standard library only.
"""

from __future__ import annotations

import json
import os
import urllib.request
from functools import lru_cache
from typing import Optional

_TIMEOUT = 3.0


def _get(path: str) -> Optional[dict]:
    base = os.environ.get("MATTERMOST_URL", "").rstrip("/")
    token = os.environ.get("MATTERMOST_TOKEN", "")
    if not base or not token:
        return None
    req = urllib.request.Request(f"{base}/api/v4{path}", headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


@lru_cache(maxsize=512)
def channel_name(platform: str, chat_id: str) -> str:
    if platform != "mattermost" or not chat_id:
        return ""
    data = _get(f"/channels/{chat_id}") or {}
    return str(data.get("name") or data.get("display_name") or "")


@lru_cache(maxsize=512)
def person_name(platform: str, user_id: str, fallback: str) -> str:
    if platform != "mattermost" or not user_id:
        return fallback
    data = _get(f"/users/{user_id}") or {}
    full = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
    return str(data.get("nickname") or full or data.get("username") or fallback)
