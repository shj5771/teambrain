"""예약 저장소 (SQLite).

외부 서비스(구글 캘린더 등)에 의존하지 않고 우리 DB에 직접 저장한다 —
"데이터 주권"(팀 데이터는 팀 서버에만) 원칙에 맞춤.
시각은 전부 **UTC ISO 문자열**로 저장하고, 읽을 때 타임존을 붙여 되돌린다
(문자열 정렬 = 시간 정렬이 되도록 형식을 고정).
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

STATUS_PENDING = "pending"
STATUS_SENT = "sent"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

SCHEMA = """
CREATE TABLE IF NOT EXISTS reminders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    message     TEXT    NOT NULL,
    due_at      TEXT    NOT NULL,
    channel     TEXT    NOT NULL,
    created_by  TEXT,
    created_at  TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'pending',
    attempts    INTEGER NOT NULL DEFAULT 0,
    sent_at     TEXT,
    last_error  TEXT,
    source      TEXT    NOT NULL DEFAULT 'cli'
);
CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(status, due_at);
"""


def to_db(when: datetime) -> str:
    """저장용 문자열 (UTC, 초 단위)."""
    if when.tzinfo is None:
        raise ValueError("타임존 정보가 없는 시각은 저장할 수 없습니다.")
    return when.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def from_db(raw: str) -> datetime:
    parsed = datetime.fromisoformat(raw)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class Reminder:
    id: int
    message: str
    due_at: datetime
    channel: str
    created_by: str | None
    created_at: datetime
    status: str
    attempts: int
    sent_at: datetime | None
    last_error: str | None
    source: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Reminder":
        return cls(
            id=row["id"],
            message=row["message"],
            due_at=from_db(row["due_at"]),
            channel=row["channel"],
            created_by=row["created_by"],
            created_at=from_db(row["created_at"]),
            status=row["status"],
            attempts=row["attempts"],
            sent_at=from_db(row["sent_at"]) if row["sent_at"] else None,
            last_error=row["last_error"],
            source=row["source"],
        )


class Store:
    """예약 CRUD. 호출마다 커넥션을 새로 열어서 여러 스레드에서 써도 안전하다."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path).expanduser()
        self._initialized = False

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        if not self._initialized:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=5000")
            yield connection
            connection.commit()
        finally:
            connection.close()

    def init(self) -> "Store":
        with self._connect() as connection:
            connection.executescript(SCHEMA)
        self._initialized = True
        return self

    # ---- 쓰기 ----------------------------------------------------------------

    def add(
        self,
        message: str,
        due_at: datetime,
        channel: str,
        created_by: str | None = None,
        source: str = "cli",
        now: datetime | None = None,
    ) -> Reminder:
        created_at = now or datetime.now(timezone.utc)
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO reminders (message, due_at, channel, created_by, created_at,"
                " status, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    message,
                    to_db(due_at),
                    channel,
                    created_by,
                    to_db(created_at),
                    STATUS_PENDING,
                    source,
                ),
            )
            new_id = int(cursor.lastrowid)
        created = self.get(new_id)
        assert created is not None
        return created

    def mark_sent(self, reminder_id: int, sent_at: datetime | None = None) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE reminders SET status=?, sent_at=?, attempts=attempts+1, last_error=NULL"
                " WHERE id=?",
                (STATUS_SENT, to_db(sent_at or datetime.now(timezone.utc)), reminder_id),
            )

    def record_failure(self, reminder_id: int, error: str, max_attempts: int) -> str:
        """전송 실패 기록. 시도 횟수가 한계를 넘으면 `failed`로 굳히고, 아니면 `pending` 유지."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT attempts FROM reminders WHERE id=?", (reminder_id,)
            ).fetchone()
            attempts = (row["attempts"] if row else 0) + 1
            status = STATUS_FAILED if attempts >= max_attempts else STATUS_PENDING
            connection.execute(
                "UPDATE reminders SET attempts=?, last_error=?, status=? WHERE id=?",
                (attempts, error[:1000], status, reminder_id),
            )
        return status

    def give_up(self, reminder_id: int, error: str) -> None:
        """다시 시도해도 소용없는 오류(채널 없음 등)는 바로 실패로 굳힌다."""
        with self._connect() as connection:
            connection.execute(
                "UPDATE reminders SET attempts=attempts+1, last_error=?, status=? WHERE id=?",
                (error[:1000], STATUS_FAILED, reminder_id),
            )

    def cancel(self, reminder_id: int) -> bool:
        """대기 중인 예약만 취소된다. 취소했으면 True."""
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE reminders SET status=? WHERE id=? AND status=?",
                (STATUS_CANCELLED, reminder_id, STATUS_PENDING),
            )
            return cursor.rowcount > 0

    # ---- 읽기 ----------------------------------------------------------------

    def get(self, reminder_id: int) -> Reminder | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM reminders WHERE id=?", (reminder_id,)
            ).fetchone()
        return Reminder.from_row(row) if row else None

    def due(self, now: datetime, limit: int = 50) -> list[Reminder]:
        """보낼 시각이 된 대기 예약 (오래된 것부터)."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM reminders WHERE status=? AND due_at<=? ORDER BY due_at LIMIT ?",
                (STATUS_PENDING, to_db(now), limit),
            ).fetchall()
        return [Reminder.from_row(row) for row in rows]

    def list(
        self,
        status: str | None = STATUS_PENDING,
        channel: str | None = None,
        limit: int = 50,
    ) -> list[Reminder]:
        query = "SELECT * FROM reminders"
        conditions: list[str] = []
        params: list[object] = []
        if status:
            conditions.append("status=?")
            params.append(status)
        if channel:
            conditions.append("channel=?")
            params.append(channel)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY due_at LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [Reminder.from_row(row) for row in rows]

    def counts(self) -> dict[str, int]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) AS n FROM reminders GROUP BY status"
            ).fetchall()
        return {row["status"]: row["n"] for row in rows}
