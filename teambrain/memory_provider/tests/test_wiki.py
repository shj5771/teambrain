"""Team wiki tests — standard library only, no Hermes or real LLM needed.

    python3 -m unittest discover -s teambrain/memory_provider/tests -t .
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from teambrain.memory_provider import TeamBrainMemoryProvider
from teambrain.memory_provider.store import TeamKnowledgeStore
from teambrain.memory_provider.wiki import TeamWiki, WikiPage, parse_llm_pages, safe_slug


def add_entry(store: TeamKnowledgeStore, user: str, assistant: str = "ok", who: str = "동연", chat: str = "dev") -> None:
    store.append_entry(
        owner_user_id=who, owner_user_name=who, visibility="team", chat_id="c1", chat_name=chat,
        channel_type="channel", platform="mattermost", profile=who, session_id="s", thread_id="",
        user_content=user, assistant_content=assistant,
    )


class FakeLLM:
    """Records prompts and returns canned replies in order."""

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.calls: list[list[dict]] = []

    def __call__(self, messages):
        self.calls.append(messages)
        return self.replies.pop(0) if self.replies else '{"pages": []}'


def reply(*pages: dict) -> str:
    return json.dumps({"pages": list(pages)}, ensure_ascii=False)


class WikiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = TeamKnowledgeStore(Path(self._tmp.name) / "store.jsonl")
        self.wiki = TeamWiki(self.store)

    def tearDown(self) -> None:
        self._tmp.cleanup()


class TestCurate(WikiTestCase):
    def test_creates_page_from_entries(self):
        add_entry(self.store, "DB는 Postgres로 가자. JSON 지원 때문에")
        llm = FakeLLM(reply({"slug": "database-choice", "title": "DB 선택", "content": "**Postgres** — 동연, #dev"}))

        self.assertEqual(self.wiki.curate(llm), ["database-choice"])
        page = self.wiki.get_page("database-choice")
        self.assertEqual(page.title, "DB 선택")
        self.assertIn("Postgres", page.content)
        self.assertIn("DB는 Postgres로 가자", llm.calls[0][1]["content"])

    def test_only_new_entries_are_sent_next_time(self):
        add_entry(self.store, "첫 번째 결정")
        self.wiki.curate(FakeLLM())
        add_entry(self.store, "두 번째 결정")
        llm = FakeLLM()
        self.wiki.curate(llm)
        prompt = llm.calls[0][1]["content"]
        self.assertIn("두 번째 결정", prompt)
        self.assertNotIn("첫 번째 결정", prompt)
        self.assertEqual(self.wiki.pending_count(), 0)

    def test_nothing_pending_means_no_llm_call(self):
        llm = FakeLLM()
        self.assertEqual(self.wiki.curate(llm), [])
        self.assertEqual(llm.calls, [])

    def test_existing_pages_are_given_to_llm_for_updates(self):
        self.wiki.write_page(WikiPage("database-choice", "DB 선택", "Postgres"))
        add_entry(self.store, "DB를 MySQL로 바꾸자")
        llm = FakeLLM()
        self.wiki.curate(llm)
        self.assertIn("slug: database-choice", llm.calls[0][1]["content"])

    def test_llm_failure_keeps_entries_for_retry(self):
        add_entry(self.store, "결정 A")

        def broken(_messages):
            raise RuntimeError("provider down")

        with self.assertRaises(RuntimeError):
            self.wiki.curate(broken)
        self.assertEqual(self.wiki.pending_count(), 1)

    def test_batches_large_backlogs(self):
        for i in range(5):
            add_entry(self.store, f"항목 {i}")
        llm = FakeLLM()
        self.wiki.curate(llm, batch_size=2)
        self.assertEqual(len(llm.calls), 3)
        self.assertEqual(self.wiki.pending_count(), 0)


class TestSafety(WikiTestCase):
    def test_llm_slug_cannot_escape_wiki_dir(self):
        add_entry(self.store, "x")
        evil = reply({"slug": "../../.ssh/authorized_keys", "title": "t", "content": "c"},
                     {"slug": "/etc/passwd", "title": "t2", "content": "c"})
        written = self.wiki.curate(FakeLLM(evil))
        for slug in written:
            self.assertRegex(slug, r"^[a-z0-9-]+$")
        files = {p.resolve().parent for p in self.wiki.dir.glob("*.md")}
        self.assertEqual(files, {self.wiki.dir.resolve()})

    def test_safe_slug(self):
        self.assertEqual(safe_slug("Database Choice"), "database-choice")
        self.assertTrue(safe_slug("데이터베이스", "데이터베이스").startswith("page-"))
        self.assertTrue(safe_slug("..", "x").startswith("page-"))

    def test_parse_tolerates_fences_and_garbage(self):
        self.assertEqual(parse_llm_pages("not json"), [])
        self.assertEqual(parse_llm_pages(""), [])
        fenced = '```json\n{"pages": [{"slug": "a", "title": "A", "content": "x"}]}\n```'
        self.assertEqual(parse_llm_pages(fenced)[0]["title"], "A")
        self.assertEqual(parse_llm_pages('{"pages": [{"slug": "a", "title": "", "content": "x"}]}'), [])


class TestSearchAndPages(WikiTestCase):
    def test_roundtrip_markdown(self):
        page = WikiPage("db", "DB 선택", "본문\n\n## 변경 이력\n- 이전: MySQL", "2026-11-03")
        self.wiki.write_page(page)
        self.assertEqual(self.wiki.get_page("db"), page)

    def test_search_prefers_title_match(self):
        self.wiki.write_page(WikiPage("db", "DB 선택", "Postgres 사용"))
        self.wiki.write_page(WikiPage("misc", "기타", "DB 얘기 잠깐"))
        result = self.wiki.search("DB 뭐 쓰기로 했지")
        self.assertLess(result.index("DB 선택"), result.index("기타"))

    def test_search_no_match(self):
        self.wiki.write_page(WikiPage("db", "DB 선택", "Postgres"))
        self.assertEqual(self.wiki.search("점심 메뉴"), "")


class TestProviderIntegration(WikiTestCase):
    def make_provider(self, chat_type="channel") -> TeamBrainMemoryProvider:
        provider = TeamBrainMemoryProvider()
        provider._store = self.store
        provider._wiki = self.wiki
        provider._curate_every = 0  # no background thread in tests
        provider.initialize("s", platform="mattermost", agent_identity="운호", user_name="운호",
                            chat_type=chat_type, chat_name="dev")
        return provider

    def test_prefetch_puts_wiki_before_raw(self):
        self.wiki.write_page(WikiPage("db", "DB 선택", "Postgres로 결정"))
        add_entry(self.store, "DB는 Postgres로 가자")
        result = self.make_provider().prefetch("DB 뭐 쓰기로 했지")
        self.assertLess(result.index("[TeamBrain wiki]"), result.index("[TeamBrain] Related raw"))

    def test_private_turns_never_reach_wiki_prompt(self):
        self.make_provider("dm").sync_turn("SECRET_DM 내 연봉은", "ok")
        self.make_provider("group").sync_turn("SECRET_PRIVATE 비공개 채널", "ok")
        self.make_provider("channel").sync_turn("공개: 회의는 매주 월요일", "ok")
        llm = FakeLLM()
        self.wiki.curate(llm)
        prompt = llm.calls[0][1]["content"]
        self.assertIn("회의는 매주 월요일", prompt)
        self.assertNotIn("SECRET", prompt)

    def test_wiki_tools(self):
        self.wiki.write_page(WikiPage("db", "DB 선택", "Postgres"))
        provider = self.make_provider()
        names = [t["name"] for t in provider.get_tool_schemas()]
        self.assertEqual(names, ["team_wiki_list", "team_wiki_read"])
        listing = json.loads(provider.handle_tool_call("team_wiki_list", {}))
        self.assertEqual(listing["pages"][0]["slug"], "db")
        page = json.loads(provider.handle_tool_call("team_wiki_read", {"slug": "db"}))
        self.assertEqual(page["content"], "Postgres")
        self.assertIn("error", json.loads(provider.handle_tool_call("team_wiki_read", {"slug": "../x"})))


if __name__ == "__main__":
    unittest.main()
