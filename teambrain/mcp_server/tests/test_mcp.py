"""MCP server tests — standard library only.

    python3 -m unittest discover -s teambrain/mcp_server/tests -t .
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from teambrain.mcp_server import TeamBrainMCP
from teambrain.memory_provider.store import TeamKnowledgeStore
from teambrain.memory_provider.wiki import WikiPage

REPO_ROOT = Path(__file__).resolve().parents[3]


def call(server: TeamBrainMCP, method: str, params=None, msg_id=1):
    return server.handle({"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}})


def tool(server: TeamBrainMCP, name: str, **arguments):
    result = call(server, "tools/call", {"name": name, "arguments": arguments})["result"]
    return result["content"][0]["text"], result["isError"]


class MCPTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store_path = Path(self._tmp.name) / "store.jsonl"
        self.store = TeamKnowledgeStore(self.store_path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def server(self, allow_write=False) -> TeamBrainMCP:
        return TeamBrainMCP(self.store, allow_write=allow_write)


class TestProtocol(MCPTestCase):
    def test_initialize_echoes_supported_version(self):
        result = call(self.server(), "initialize", {"protocolVersion": "2025-03-26"})["result"]
        self.assertEqual(result["protocolVersion"], "2025-03-26")
        self.assertEqual(result["serverInfo"]["name"], "teambrain")
        self.assertIn("tools", result["capabilities"])

    def test_initialize_unknown_version_falls_back(self):
        result = call(self.server(), "initialize", {"protocolVersion": "1999-01-01"})["result"]
        self.assertEqual(result["protocolVersion"], "2025-06-18")

    def test_notifications_get_no_reply(self):
        self.assertIsNone(self.server().handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_unknown_method(self):
        self.assertEqual(call(self.server(), "nope")["error"]["code"], -32601)

    def test_serve_loop_handles_garbage(self):
        stdin = io.StringIO('not json\n\n{"jsonrpc":"2.0","id":7,"method":"ping"}\n')
        stdout = io.StringIO()
        self.server().serve(stdin, stdout)
        replies = [json.loads(l) for l in stdout.getvalue().splitlines()]
        self.assertEqual(replies[0]["error"]["code"], -32700)
        self.assertEqual(replies[1], {"jsonrpc": "2.0", "id": 7, "result": {}})


class TestReadTools(MCPTestCase):
    def test_read_only_by_default(self):
        names = [t["name"] for t in call(self.server(allow_write=None), "tools/list")["result"]["tools"]]
        self.assertEqual(names, ["team_search", "team_wiki_list", "team_wiki_read"])
        text, is_error = tool(self.server(), "team_remember", note="x")
        self.assertTrue(is_error)
        self.assertEqual(self.store.read_all(), [])

    def test_search_returns_wiki_then_raw(self):
        server = self.server()
        server.wiki.write_page(WikiPage("db", "DB 선택", "Postgres로 결정 — 지민, #dev"))
        self.store.append_entry(
            owner_user_id="u1", owner_user_name="지민", visibility="team", chat_id="c", chat_name="dev",
            channel_type="channel", platform="mattermost", profile="jimin", session_id="s", thread_id="",
            user_content="DB는 Postgres로 가자", assistant_content="좋아요",
        )
        text, is_error = tool(server, "team_search", query="DB 뭐 쓰기로 했지")
        self.assertFalse(is_error)
        self.assertLess(text.index("DB 선택"), text.index("DB는 Postgres로 가자"))

    def test_search_no_match_and_empty_query(self):
        self.assertIn("No team memory", tool(self.server(), "team_search", query="점심 메뉴")[0])
        self.assertTrue(tool(self.server(), "team_search", query=" ")[1])

    def test_wiki_list_and_read(self):
        server = self.server()
        server.wiki.write_page(WikiPage("db", "DB 선택", "Postgres"))
        listing = json.loads(tool(server, "team_wiki_list")[0])
        self.assertEqual(listing["pages"][0]["slug"], "db")
        self.assertEqual(json.loads(tool(server, "team_wiki_read", slug="db")[0])["content"], "Postgres")
        self.assertTrue(tool(server, "team_wiki_read", slug="../../etc/passwd")[1])


class TestWriteTool(MCPTestCase):
    def test_remember_records_only_the_note(self):
        os.environ["TEAMBRAIN_USER"] = "서준"
        try:
            server = self.server(allow_write=True)
            self.assertIn("team_remember", [t["name"] for t in server.tools()])
            text, is_error = tool(server, "team_remember", note="배포는 매주 화요일", topic="배포")
        finally:
            del os.environ["TEAMBRAIN_USER"]
        self.assertFalse(is_error)
        [entry] = self.store.read_all()
        self.assertEqual(entry["user"], "[배포] 배포는 매주 화요일")
        self.assertEqual(entry["assistant"], "")
        self.assertEqual(entry["owner"]["user_name"], "서준")
        self.assertEqual(entry["platform"], "mcp")

    def test_remember_rejects_empty_and_huge(self):
        server = self.server(allow_write=True)
        self.assertTrue(tool(server, "team_remember", note="")[1])
        self.assertTrue(tool(server, "team_remember", note="x" * 5000)[1])
        self.assertEqual(self.store.read_all(), [])


class TestStdioEndToEnd(MCPTestCase):
    def test_real_process_roundtrip(self):
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ]
        env = {**os.environ, "TEAMBRAIN_STORE": str(self.store_path)}
        env.pop("TEAMBRAIN_MCP_ALLOW_WRITE", None)
        proc = subprocess.run(
            [sys.executable, "-m", "teambrain.mcp_server"], cwd=REPO_ROOT, env=env,
            input="".join(json.dumps(r) + "\n" for r in requests), capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        replies = [json.loads(l) for l in proc.stdout.splitlines()]
        self.assertEqual([r["id"] for r in replies], [1, 2])
        self.assertEqual(len(replies[1]["result"]["tools"]), 3)


if __name__ == "__main__":
    unittest.main()
