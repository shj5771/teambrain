"""(선택) 슬랙에서 봇을 멘션해 리마인드를 등록받는 부분.

    @리마인드봇 내일 오후 3시 멘토링 준비물 챙기기
    @리마인드봇 목록
    @리마인드봇 취소 3

이 부분만 `slack_bolt`가 필요하다(`pip3 install slack_bolt`). 없거나 앱 토큰이 없으면
터미널(`add`)로 등록하고 `run`으로 전송하는 방식은 그대로 쓸 수 있다.

이 프로세스 하나가 (1) 멘션 수신 (2) 시간 되면 전송 을 같이 한다 —
전송은 백그라운드 스레드에서 `scheduler.run_forever`가 담당.
"""

from __future__ import annotations

import logging
import re
import threading

from .config import Config, ConfigError
from .notifier import build_notifier
from .scheduler import run_forever
from .store import STATUS_PENDING, Store
from .timeparse import ParseError, format_remaining, format_when, parse_when

logger = logging.getLogger("teambrain.reminder")

MENTION_RE = re.compile(r"<@[A-Z0-9]+>")
CANCEL_RE = re.compile(r"^(?:취소|cancel)\s*#?(?P<id>\d+)\s*$", re.IGNORECASE)
LIST_RE = re.compile(r"^(?:목록|리스트|예약목록|예약\s*목록|list)\s*$", re.IGNORECASE)
HELP_RE = re.compile(r"^(?:도움|도움말|사용법|help|\?)\s*$", re.IGNORECASE)

HELP_TEXT = (
    "*리마인드 사용법*\n"
    "· 등록: `@나 내일 오후 3시 멘토링 준비물 챙기기`\n"
    "· 목록: `@나 목록`   · 취소: `@나 취소 3`\n"
    "\n읽을 수 있는 시간 표현: `내일 오후 3시`, `8월 1일 15시`, `2026-08-01 09:30`, "
    "`30분 뒤`, `3일 뒤 10시`, `다음주 월요일 10시`, `금요일 오후 2시`\n"
    "_날짜만 적으면 그날 오전 9시, 오전/오후 없는 1~7시는 오후로 봅니다._"
)


def handle_text(
    text: str,
    store: Store,
    config: Config,
    channel: str,
    user_id: str | None = None,
) -> str:
    """봇이 받은 문장 하나를 처리하고 답장 문구를 돌려준다 (전송은 하지 않음)."""
    body = MENTION_RE.sub(" ", text or "").strip()

    if not body or HELP_RE.match(body):
        return HELP_TEXT

    cancel_match = CANCEL_RE.match(body)
    if cancel_match:
        reminder_id = int(cancel_match.group("id"))
        reminder = store.get(reminder_id)
        if reminder is None:
            return f"#{reminder_id} 예약을 찾을 수 없어요. `목록`으로 번호를 확인해주세요."
        if reminder.channel != channel:
            return f"#{reminder_id} 는 다른 채널에서 등록된 예약이라 여기서는 취소할 수 없어요."
        if store.cancel(reminder_id):
            return f"🗑️ 예약 #{reminder_id} 취소했어요 — {reminder.message}"
        return f"#{reminder_id} 는 이미 처리된 예약이라 취소할 수 없어요."

    if LIST_RE.match(body):
        reminders = store.list(status=STATUS_PENDING, channel=channel, limit=10)
        if not reminders:
            return "이 채널에 대기 중인 리마인드가 없어요."
        lines = ["*대기 중인 리마인드*"]
        for reminder in reminders:
            lines.append(
                f"· #{reminder.id} {format_when(reminder.due_at, config.tz)}"
                f" ({format_remaining(reminder.due_at)}) — {reminder.message}"
            )
        return "\n".join(lines)

    try:
        parsed = parse_when(body, tz=config.tz)
    except ParseError as exc:
        return f"⚠️ {exc}\n\n{HELP_TEXT}"

    reminder = store.add(
        message=parsed.message,
        due_at=parsed.when,
        channel=channel,
        created_by=user_id,
        source="slack",
    )
    return (
        f"✅ {format_when(parsed.when, config.tz)} ({format_remaining(parsed.when)})에"
        f" 알려드릴게요. (예약 #{reminder.id})\n"
        f"· 내용: {parsed.message}\n"
        f"· 인식한 시간 표현: {parsed.matched}"
    )


def build_app(config: Config, store: Store):
    """slack_bolt 앱을 만들어 이벤트 핸들러를 붙인다."""
    try:
        from slack_bolt import App
    except ImportError as exc:  # pragma: no cover - 설치 여부에 따라 달라짐
        raise ConfigError(
            "슬랙에서 봇 멘션을 받으려면 slack_bolt 가 필요합니다: `pip3 install slack_bolt`\n"
            "(설치 없이 쓰려면 터미널에서 `add` 로 등록하고 `run` 으로 전송하세요.)"
        ) from exc

    app = App(token=config.slack_bot_token, raise_error_for_unhandled_request=False)

    @app.event("app_mention")
    def on_mention(event, say):  # pragma: no cover - 슬랙 연결 필요
        reply = handle_text(
            event.get("text", ""),
            store,
            config,
            channel=event["channel"],
            user_id=event.get("user"),
        )
        say(text=reply, thread_ts=event.get("thread_ts") or event.get("ts"))

    @app.event("message")
    def on_direct_message(event, say):  # pragma: no cover - 슬랙 연결 필요
        # 봇 자기 말/수정·삭제 이벤트는 무시하고, 1:1 DM만 처리한다.
        if event.get("bot_id") or event.get("subtype") or event.get("channel_type") != "im":
            return
        reply = handle_text(
            event.get("text", ""),
            store,
            config,
            channel=event["channel"],
            user_id=event.get("user"),
        )
        say(text=reply)

    return app


def run_bot(config: Config, dry_run: bool = False) -> int:
    """봇(멘션 수신) + 스케줄러(전송)를 한 프로세스에서 함께 돌린다."""
    if not config.slack_bot_token:
        raise ConfigError("SLACK_BOT_TOKEN(`xoxb-`로 시작) 이 필요합니다. README.md 3번 항목 참고.")
    if not config.slack_app_token:
        raise ConfigError(
            "SLACK_APP_TOKEN(`xapp-`로 시작) 이 필요합니다 — 소켓 모드 연결용. README.md 3번 항목 참고."
        )

    store = Store(config.db_path).init()
    notifier = build_notifier(config, dry_run=dry_run)
    # build_app이 slack_bolt 미설치를 먼저 걸러 친절한 안내를 띄운다 — 그 뒤에 어댑터를 불러온다.
    app = build_app(config, store)

    from slack_bolt.adapter.socket_mode import SocketModeHandler

    stop_event = threading.Event()
    sender = threading.Thread(
        target=run_forever,
        args=(store, notifier, config.tz),
        kwargs={
            "poll_seconds": config.poll_seconds,
            "max_attempts": config.max_attempts,
            "late_notice_seconds": config.late_notice_seconds,
            "stop_event": stop_event,
        },
        name="reminder-sender",
        daemon=True,
    )
    sender.start()

    logger.info("슬랙 봇 시작 (소켓 모드). Ctrl+C 로 종료.")
    handler = SocketModeHandler(app, config.slack_app_token)
    try:
        handler.start()
    except KeyboardInterrupt:  # pragma: no cover
        logger.info("종료 요청 — 정리 중")
    finally:
        stop_event.set()
        sender.join(timeout=5)
    return 0
