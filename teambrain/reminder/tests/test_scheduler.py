"""전송 루프(스케줄러) 테스트 — 실제 슬랙 호출 없이 가짜 전송기로 검증."""

import logging
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from teambrain.reminder.notifier import NotifyError
from teambrain.reminder.scheduler import format_author, render_message, run_once
from teambrain.reminder.store import STATUS_FAILED, STATUS_PENDING, STATUS_SENT, Store

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 7, 30, 11, 0, tzinfo=KST)


def setUpModule():
    # 실패 경로를 일부러 여러 번 태우기 때문에, 테스트 출력이 오류 로그로 덮이지 않게 막는다.
    logging.getLogger("teambrain.reminder").disabled = True


def tearDownModule():
    logging.getLogger("teambrain.reminder").disabled = False


class FakeNotifier:
    """지정한 횟수만큼 실패하다가 성공하는 전송기."""

    def __init__(self, fail_times=0, permanent=False):
        self.sent = []
        self.fail_times = fail_times
        self.permanent = permanent
        self.attempts = 0

    def send(self, channel, text):
        self.attempts += 1
        if self.fail_times > 0:
            self.fail_times -= 1
            raise NotifyError("보내기 실패", permanent=self.permanent)
        self.sent.append((channel, text))

    def describe(self):
        return "가짜 전송기"


class ExplodingNotifier:
    def send(self, channel, text):
        raise RuntimeError("예상 못 한 오류")

    def describe(self):
        return "터지는 전송기"


class SchedulerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self._tmp.name) / "r.db").init()

    def tearDown(self):
        self._tmp.cleanup()

    def add(self, minutes, message="회의 준비", channel="C1", created_by=None):
        return self.store.add(
            message=message,
            due_at=NOW + timedelta(minutes=minutes),
            channel=channel,
            created_by=created_by,
        )

    def test_sends_due_and_skips_future(self):
        due = self.add(-1, message="지금 보낼 것")
        future = self.add(60, message="아직")
        notifier = FakeNotifier()

        results = run_once(self.store, notifier, KST, now=NOW)

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].ok)
        self.assertEqual(len(notifier.sent), 1)
        self.assertIn("지금 보낼 것", notifier.sent[0][1])
        self.assertEqual(notifier.sent[0][0], "C1")
        self.assertEqual(self.store.get(due.id).status, STATUS_SENT)
        self.assertEqual(self.store.get(future.id).status, STATUS_PENDING)

    def test_transient_failure_stays_pending_and_retries_later(self):
        reminder = self.add(-1)
        notifier = FakeNotifier(fail_times=1)

        first = run_once(self.store, notifier, KST, now=NOW, max_attempts=5)
        self.assertFalse(first[0].ok)
        self.assertEqual(self.store.get(reminder.id).status, STATUS_PENDING)

        second = run_once(self.store, notifier, KST, now=NOW, max_attempts=5)
        self.assertTrue(second[0].ok)
        self.assertEqual(self.store.get(reminder.id).status, STATUS_SENT)
        self.assertEqual(self.store.get(reminder.id).attempts, 2)

    def test_gives_up_after_max_attempts(self):
        reminder = self.add(-1)
        notifier = FakeNotifier(fail_times=99)

        for _ in range(2):
            run_once(self.store, notifier, KST, now=NOW, max_attempts=2)

        loaded = self.store.get(reminder.id)
        self.assertEqual(loaded.status, STATUS_FAILED)
        self.assertEqual(loaded.attempts, 2)
        # 실패로 굳은 뒤에는 더 시도하지 않는다
        run_once(self.store, notifier, KST, now=NOW, max_attempts=2)
        self.assertEqual(notifier.attempts, 2)

    def test_permanent_failure_gives_up_immediately(self):
        reminder = self.add(-1)
        notifier = FakeNotifier(fail_times=99, permanent=True)

        run_once(self.store, notifier, KST, now=NOW, max_attempts=5)

        self.assertEqual(self.store.get(reminder.id).status, STATUS_FAILED)
        self.assertEqual(notifier.attempts, 1)

    def test_unexpected_error_does_not_lose_reminder(self):
        reminder = self.add(-1)
        run_once(self.store, ExplodingNotifier(), KST, now=NOW, max_attempts=5)
        loaded = self.store.get(reminder.id)
        self.assertEqual(loaded.status, STATUS_PENDING)
        self.assertIn("RuntimeError", loaded.last_error)


class RenderTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self._tmp.name) / "r.db").init()

    def tearDown(self):
        self._tmp.cleanup()

    def build(self, minutes=0, created_by=None):
        return self.store.add(
            message="멘토링 준비물 챙기기",
            due_at=NOW + timedelta(minutes=minutes),
            channel="C1",
            created_by=created_by,
        )

    def test_includes_message_and_scheduled_time(self):
        text = render_message(self.build(), KST, now=NOW)
        self.assertIn("멘토링 준비물 챙기기", text)
        self.assertIn("2026-07-30(목) 11:00", text)
        self.assertNotIn("늦게", text)

    def test_mentions_slack_author(self):
        text = render_message(self.build(created_by="U12345678"), KST, now=NOW)
        self.assertIn("<@U12345678>", text)

    def test_plain_author_is_not_mentioned(self):
        text = render_message(self.build(created_by="홍길동"), KST, now=NOW)
        self.assertIn("홍길동", text)
        self.assertNotIn("<@", text)

    def test_late_delivery_is_flagged(self):
        reminder = self.build(minutes=-30)
        text = render_message(reminder, KST, now=NOW, late_notice_seconds=120)
        self.assertIn("30분 늦게", text)

    def test_format_author(self):
        self.assertEqual(format_author("U12345678"), "<@U12345678>")
        self.assertEqual(format_author("cli"), "cli")
        self.assertIsNone(format_author(None))


if __name__ == "__main__":
    unittest.main()
