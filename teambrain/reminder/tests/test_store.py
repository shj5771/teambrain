"""예약 저장소(SQLite) 테스트."""

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from teambrain.reminder.store import (
    STATUS_CANCELLED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SENT,
    Store,
)

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 7, 30, 11, 0, tzinfo=KST)


class StoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        # 하위 폴더까지 자동 생성되는지도 함께 확인
        self.store = Store(Path(self._tmp.name) / "nested" / "reminders.db").init()

    def tearDown(self):
        self._tmp.cleanup()

    def add(self, minutes, message="테스트", channel="C1", **kwargs):
        return self.store.add(
            message=message, due_at=NOW + timedelta(minutes=minutes), channel=channel, **kwargs
        )

    def test_add_and_get_roundtrip(self):
        created = self.add(10, message="물 마시기", created_by="U123", source="slack")
        loaded = self.store.get(created.id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.message, "물 마시기")
        self.assertEqual(loaded.channel, "C1")
        self.assertEqual(loaded.created_by, "U123")
        self.assertEqual(loaded.source, "slack")
        self.assertEqual(loaded.status, STATUS_PENDING)
        self.assertEqual(loaded.attempts, 0)
        self.assertIsNone(loaded.sent_at)
        # 타임존이 달라도 같은 순간으로 되돌아온다
        self.assertEqual(loaded.due_at, NOW + timedelta(minutes=10))

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.store.get(999))

    def test_due_only_returns_reached_and_pending(self):
        past = self.add(-5, message="지난 것")
        future = self.add(30, message="아직")
        cancelled = self.add(-10, message="취소된 것")
        self.store.cancel(cancelled.id)

        due_ids = [reminder.id for reminder in self.store.due(NOW)]
        self.assertIn(past.id, due_ids)
        self.assertNotIn(future.id, due_ids)
        self.assertNotIn(cancelled.id, due_ids)

    def test_due_is_ordered_oldest_first(self):
        later = self.add(-1, message="나중")
        earlier = self.add(-30, message="먼저")
        self.assertEqual([r.id for r in self.store.due(NOW)], [earlier.id, later.id])

    def test_mark_sent(self):
        reminder = self.add(-1)
        self.store.mark_sent(reminder.id, NOW)
        loaded = self.store.get(reminder.id)
        self.assertEqual(loaded.status, STATUS_SENT)
        self.assertEqual(loaded.sent_at, NOW)
        self.assertEqual(loaded.attempts, 1)
        self.assertEqual(self.store.due(NOW), [])

    def test_record_failure_keeps_pending_until_max_attempts(self):
        reminder = self.add(-1)
        self.assertEqual(self.store.record_failure(reminder.id, "일시 오류", 3), STATUS_PENDING)
        self.assertEqual(self.store.record_failure(reminder.id, "일시 오류", 3), STATUS_PENDING)
        self.assertEqual(self.store.record_failure(reminder.id, "일시 오류", 3), STATUS_FAILED)
        loaded = self.store.get(reminder.id)
        self.assertEqual(loaded.attempts, 3)
        self.assertEqual(loaded.last_error, "일시 오류")

    def test_give_up_marks_failed_immediately(self):
        reminder = self.add(-1)
        self.store.give_up(reminder.id, "채널 없음")
        loaded = self.store.get(reminder.id)
        self.assertEqual(loaded.status, STATUS_FAILED)
        self.assertEqual(loaded.last_error, "채널 없음")

    def test_cancel_twice_returns_false(self):
        reminder = self.add(10)
        self.assertTrue(self.store.cancel(reminder.id))
        self.assertFalse(self.store.cancel(reminder.id))
        self.assertEqual(self.store.get(reminder.id).status, STATUS_CANCELLED)

    def test_cancel_sent_reminder_returns_false(self):
        reminder = self.add(-1)
        self.store.mark_sent(reminder.id, NOW)
        self.assertFalse(self.store.cancel(reminder.id))

    def test_list_filters(self):
        pending_here = self.add(10, channel="C1")
        pending_there = self.add(20, channel="C2")
        sent = self.add(30, channel="C1")
        self.store.mark_sent(sent.id, NOW)

        pending_ids = [r.id for r in self.store.list(status=STATUS_PENDING)]
        self.assertCountEqual(pending_ids, [pending_here.id, pending_there.id])
        self.assertEqual(
            [r.id for r in self.store.list(status=STATUS_PENDING, channel="C1")], [pending_here.id]
        )
        self.assertEqual(len(self.store.list(status=None)), 3)

    def test_counts(self):
        self.add(10)
        sent = self.add(-1)
        self.store.mark_sent(sent.id, NOW)
        self.assertEqual(self.store.counts(), {STATUS_PENDING: 1, STATUS_SENT: 1})

    def test_naive_datetime_is_rejected(self):
        with self.assertRaises(ValueError):
            self.store.add(message="x", due_at=datetime(2026, 8, 1, 9, 0), channel="C1")


if __name__ == "__main__":
    unittest.main()
