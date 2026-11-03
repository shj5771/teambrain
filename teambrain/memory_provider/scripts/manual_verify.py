#!/usr/bin/env python3
"""Standalone verification for the TeamBrain MVP visibility rule.

No pytest required — run directly with the Hermes venv's Python (needs
`agent.memory_provider` importable, i.e. Hermes' own package):

    ~/.hermes/hermes-agent/venv/bin/python3 teambrain/memory_provider/scripts/manual_verify.py

Fabricates initialize()/sync_turn() calls across every chat_type Hermes can
hand us (including an absent and an unrecognized value, to probe the
fail-closed path) and asserts that only the fully-open-channel case's marker
string survives into prefetch().
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from teambrain.memory_provider import TeamBrainMemoryProvider  # noqa: E402

# (chat_type, marker) — "thread"/None cases probe values a future platform
# (or an unrecognized Mattermost code) might hand us; both must fail closed.
CASES = [
    ("channel", "MARKER_OPEN_CHANNEL_7f3a"),
    ("dm", "MARKER_SECRET_DM_9c1b"),
    ("group", "MARKER_PRIVATE_CHANNEL_2e88"),
    (None, "MARKER_MISSING_CHATTYPE_4d02"),
    ("thread", "MARKER_UNKNOWN_CHATTYPE_66aa"),
]


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        store_path = Path(tmp) / "store.jsonl"

        for i, (chat_type, marker) in enumerate(CASES):
            provider = TeamBrainMemoryProvider()
            provider._store.path = store_path  # scratch path, not the real shared store
            provider.initialize(
                session_id=f"test-session-{i}",
                platform="mattermost",
                agent_identity=f"profile-{i}",
                user_id=f"user-{i}",
                user_name=f"tester-{i}",
                chat_id=f"chat-{i}",
                chat_name=f"chan-{i}",
                chat_type=chat_type,
                agent_context="primary",
            )
            provider.sync_turn(f"remember this: {marker}", f"ack: {marker}")

        verifier = TeamBrainMemoryProvider()
        verifier._store.path = store_path
        verifier.initialize(
            session_id="verify",
            platform="mattermost",
            agent_identity="verifier",
            chat_type="channel",
        )
        result = verifier.prefetch("remember this")

        open_marker = CASES[0][1]
        ok = True

        if open_marker not in result:
            print(f"FAIL: expected open-channel marker {open_marker!r} to appear in prefetch, but it did not.")
            print(f"prefetch() returned:\n{result}")
            ok = False

        for chat_type, marker in CASES[1:]:
            if marker in result:
                print(f"FAIL: marker {marker!r} from chat_type={chat_type!r} leaked into prefetch(). This must never sync.")
                ok = False

        if ok:
            print("PASS: only the open-channel entry synced; dm/group/missing/unknown chat_type all stayed private.")
            return 0
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
