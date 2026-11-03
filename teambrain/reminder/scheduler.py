"""시간이 된 예약을 찾아 전송하는 부분.

일부러 단순한 **폴링(주기적으로 확인)** 방식이다. 프로세스가 죽었다 살아나도
DB에 남은 예약을 다시 집어 보내므로(늦었으면 늦었다고 표시해서) 노트북이 잠들었다
깨어나는 개발 환경에서도 알림이 사라지지 않는다.
"""

from __future__ import annotations

import logging
import re
import signal
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .notifier import Notifier, NotifyError
from .store import Reminder, Store
from .timeparse import format_when

logger = logging.getLogger("teambrain.reminder")

SLACK_USER_ID_RE = re.compile(r"^[UW][A-Z0-9]{6,}$")


@dataclass(frozen=True)
class SendResult:
    reminder: Reminder
    ok: bool
    status: str
    error: str | None = None


def format_author(created_by: str | None) -> str | None:
    """슬랙 사용자 ID면 멘션으로 바꿔서 실제로 알림이 가게 한다."""
    if not created_by:
        return None
    if SLACK_USER_ID_RE.match(created_by):
        return f"<@{created_by}>"
    return created_by


def render_message(
    reminder: Reminder,
    tz: ZoneInfo,
    now: datetime | None = None,
    late_notice_seconds: int = 120,
) -> str:
    now = now or datetime.now(timezone.utc)
    lines = [f"⏰ *리마인드*: {reminder.message}"]

    footer = [f"예정 {format_when(reminder.due_at, tz)}"]
    author = format_author(reminder.created_by)
    if author:
        footer.append(f"등록 {author}")
    lines.append(" · ".join(footer))

    late_seconds = int((now - reminder.due_at).total_seconds())
    if late_seconds > late_notice_seconds:
        minutes = late_seconds // 60
        lines.append(
            f"_(예정보다 {minutes}분 늦게 전송됐어요 — 알림 서버가 꺼져 있었을 수 있습니다)_"
        )
    return "\n".join(lines)


def send_one(
    store: Store,
    notifier: Notifier,
    reminder: Reminder,
    tz: ZoneInfo,
    now: datetime | None = None,
    max_attempts: int = 5,
    late_notice_seconds: int = 120,
) -> SendResult:
    now = now or datetime.now(timezone.utc)
    text = render_message(reminder, tz, now=now, late_notice_seconds=late_notice_seconds)
    try:
        notifier.send(reminder.channel, text)
    except NotifyError as exc:
        message = str(exc)
        if exc.permanent:
            store.give_up(reminder.id, message)
            logger.error("#%s 전송 실패(재시도 안 함): %s", reminder.id, message)
            return SendResult(reminder, False, "failed", message)
        status = store.record_failure(reminder.id, message, max_attempts)
        logger.warning(
            "#%s 전송 실패(%s): %s", reminder.id, "포기" if status == "failed" else "재시도 예정", message
        )
        return SendResult(reminder, False, status, message)
    except Exception as exc:  # 예상 못 한 오류도 예약을 잃지 않게 기록만 하고 넘어간다
        message = f"{type(exc).__name__}: {exc}"
        status = store.record_failure(reminder.id, message, max_attempts)
        logger.exception("#%s 전송 중 예상치 못한 오류", reminder.id)
        return SendResult(reminder, False, status, message)

    store.mark_sent(reminder.id, now)
    logger.info("#%s 전송 완료 → %s", reminder.id, reminder.channel)
    return SendResult(reminder, True, "sent")


def run_once(
    store: Store,
    notifier: Notifier,
    tz: ZoneInfo,
    now: datetime | None = None,
    max_attempts: int = 5,
    late_notice_seconds: int = 120,
    limit: int = 50,
) -> list[SendResult]:
    """지금 보낼 것들을 한 번 훑어서 보낸다."""
    now = now or datetime.now(timezone.utc)
    results: list[SendResult] = []
    for reminder in store.due(now, limit=limit):
        results.append(
            send_one(
                store,
                notifier,
                reminder,
                tz,
                now=now,
                max_attempts=max_attempts,
                late_notice_seconds=late_notice_seconds,
            )
        )
    return results


def run_forever(
    store: Store,
    notifier: Notifier,
    tz: ZoneInfo,
    poll_seconds: int = 20,
    max_attempts: int = 5,
    late_notice_seconds: int = 120,
    stop_event: threading.Event | None = None,
    install_signal_handlers: bool = False,
) -> None:
    """멈추라고 할 때까지 계속 확인·전송한다.

    `install_signal_handlers`는 메인 스레드에서만 켜야 한다 (Ctrl+C로 곱게 종료).
    """
    stop = stop_event or threading.Event()

    if install_signal_handlers:
        def _handle(signum, _frame):  # pragma: no cover - 신호 처리
            logger.info("종료 신호(%s) 수신 — 정리 후 종료합니다.", signum)
            stop.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, _handle)

    logger.info(
        "리마인드 스케줄러 시작 (%s초마다 확인, 시간대 %s, 전송: %s)",
        poll_seconds,
        tz.key,
        notifier.describe(),
    )
    while not stop.is_set():
        try:
            run_once(
                store,
                notifier,
                tz,
                max_attempts=max_attempts,
                late_notice_seconds=late_notice_seconds,
            )
        except Exception:  # DB 잠김 등 — 루프 자체는 죽지 않게
            logger.exception("확인 주기 중 오류 (계속 실행합니다)")
        stop.wait(poll_seconds)
    logger.info("리마인드 스케줄러 종료")
