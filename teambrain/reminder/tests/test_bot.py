"""봇이 받은 문장 처리 로직 테스트 (슬랙 연결 없이 `handle_text`만 검증)."""

import importlib.util
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from teambrain.reminder.bot import build_app, handle_text, run_bot
from teambrain.reminder.config import Config, ConfigError
from teambrain.reminder.store import STATUS_PENDING, Store

SLACK_BOLT_INSTALLED = importlib.util.find_spec("slack_bolt") is not None


class HandleTextTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self._tmp.name) / "r.db").init()
        self.config = Config(slack_bot_token="xoxb-1", default_channel="C1")

    def tearDown(self):
        self._tmp.cleanup()

    def handle(self, text, channel="C1", user_id="U777"):
        return handle_text(text, self.store, self.config, channel=channel, user_id=user_id)

    def test_registers_reminder_from_mention(self):
        reply = self.handle("<@UBOT123> 30분 뒤 물 마시기")

        self.assertIn("✅", reply)
        self.assertIn("물 마시기", reply)
        pending = self.store.list(status=STATUS_PENDING)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].message, "물 마시기")
        self.assertEqual(pending[0].channel, "C1")
        self.assertEqual(pending[0].created_by, "U777")
        self.assertEqual(pending[0].source, "slack")
        self.assertGreater(pending[0].due_at, datetime.now(timezone.utc))

    def test_help_when_only_mention(self):
        self.assertIn("사용법", self.handle("<@UBOT123>"))

    def test_help_keyword(self):
        self.assertIn("사용법", self.handle("<@UBOT123> 도움말"))

    def test_parse_error_returns_guidance_and_stores_nothing(self):
        reply = self.handle("<@UBOT123> 회의록 정리해줘")
        self.assertIn("⚠️", reply)
        self.assertIn("사용법", reply)
        self.assertEqual(self.store.list(status=None), [])

    def test_list_shows_only_this_channel(self):
        self.handle("<@UBOT123> 내일 10시 이 채널 일정", channel="C1")
        self.handle("<@UBOT123> 내일 11시 다른 채널 일정", channel="C2")

        reply = self.handle("<@UBOT123> 목록", channel="C1")
        self.assertIn("이 채널 일정", reply)
        self.assertNotIn("다른 채널 일정", reply)

    def test_list_when_empty(self):
        self.assertIn("없어요", self.handle("<@UBOT123> 목록"))

    def test_cancel(self):
        self.handle("<@UBOT123> 내일 10시 취소할 일정")
        reminder_id = self.store.list(status=STATUS_PENDING)[0].id

        reply = self.handle(f"<@UBOT123> 취소 {reminder_id}")
        self.assertIn("취소", reply)
        self.assertEqual(self.store.list(status=STATUS_PENDING), [])

    def test_cancel_missing_id(self):
        self.assertIn("찾을 수 없어요", self.handle("<@UBOT123> 취소 999"))

    def test_cannot_cancel_other_channels_reminder(self):
        self.handle("<@UBOT123> 내일 10시 저쪽 일정", channel="C2")
        reminder_id = self.store.list(status=STATUS_PENDING)[0].id

        reply = self.handle(f"<@UBOT123> 취소 {reminder_id}", channel="C1")
        self.assertIn("다른 채널", reply)
        self.assertEqual(len(self.store.list(status=STATUS_PENDING)), 1)

    def test_direct_message_without_mention_still_works(self):
        reply = self.handle("내일 오후 3시 멘토링 준비", channel="D1")
        self.assertIn("✅", reply)
        self.assertEqual(self.store.list(status=STATUS_PENDING)[0].channel, "D1")


class BotStartupGuardTest(unittest.TestCase):
    """봇을 켤 때 빠진 설정은 슬랙에 연결하기 전에 한국어로 알려줘야 한다."""

    def test_requires_bot_token(self):
        with self.assertRaises(ConfigError) as ctx:
            run_bot(Config())
        self.assertIn("SLACK_BOT_TOKEN", str(ctx.exception))

    def test_requires_app_token(self):
        with self.assertRaises(ConfigError) as ctx:
            run_bot(Config(slack_bot_token="xoxb-1"))
        self.assertIn("SLACK_APP_TOKEN", str(ctx.exception))

    @unittest.skipIf(SLACK_BOLT_INSTALLED, "slack_bolt 가 설치돼 있으면 확인 불가")
    def test_missing_slack_bolt_explains_how_to_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "r.db").init()
            with self.assertRaises(ConfigError) as ctx:
                build_app(Config(slack_bot_token="xoxb-1"), store)
        self.assertIn("pip3 install slack_bolt", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
