"""터미널 명령 — 슬랙 봇 설정 없이도 이 기능을 바로 써볼 수 있는 입구.

    python3 -m teambrain.reminder check "내일 오후 3시 멘토링 준비"   # 해석만 확인
    python3 -m teambrain.reminder add   "내일 오후 3시 멘토링 준비"   # 예약
    python3 -m teambrain.reminder list                              # 예약 목록
    python3 -m teambrain.reminder cancel 3                          # 취소
    python3 -m teambrain.reminder run                               # 알림 전송 상시 실행
    python3 -m teambrain.reminder doctor                            # 설정 점검
"""

from __future__ import annotations

import argparse
import logging
import sys
import unicodedata
from datetime import datetime, timezone

from .config import ConfigError, Config, find_env_files, load_config
from .notifier import NotifyError, build_notifier
from .scheduler import run_forever, run_once
from .store import STATUS_PENDING, Store
from .timeparse import ParseError, format_remaining, format_when, parse_when

STATUS_LABELS = {
    "pending": "대기",
    "sent": "전송됨",
    "failed": "실패",
    "cancelled": "취소됨",
}


def display_width(text: str) -> int:
    """한글·이모지는 터미널에서 두 칸을 차지한다 — 표를 맞추려면 이 폭으로 세야 한다."""
    return sum(2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in text)


def pad(text: str, width: int) -> str:
    return text + " " * max(1, width - display_width(text))


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _open_store(config: Config) -> Store:
    return Store(config.db_path).init()


def _resolve_channel(config: Config, requested: str | None) -> str:
    channel = requested or config.default_channel
    if not channel:
        raise ConfigError(
            "보낼 채널이 없습니다. `--to C0123ABCD` 로 지정하거나 "
            "`.env`에 SLACK_DEFAULT_CHANNEL 을 넣어주세요."
        )
    return channel


def cmd_check(args: argparse.Namespace, config: Config) -> int:
    parsed = parse_when(" ".join(args.text), tz=config.tz)
    print(f"인식한 시간 표현 : {parsed.matched}")
    print(f"보낼 시각        : {format_when(parsed.when, config.tz)} ({format_remaining(parsed.when)})")
    print(f"알림 내용        : {parsed.message}")
    print("\n(확인만 한 것이라 저장되지 않았습니다. 예약하려면 `add` 를 쓰세요.)")
    return 0


def cmd_add(args: argparse.Namespace, config: Config) -> int:
    parsed = parse_when(" ".join(args.text), tz=config.tz)
    channel = _resolve_channel(config, args.to)
    store = _open_store(config)
    reminder = store.add(
        message=parsed.message,
        due_at=parsed.when,
        channel=channel,
        created_by=args.by,
        source="cli",
    )
    print(
        f"✅ 예약 #{reminder.id} — {format_when(parsed.when, config.tz)}"
        f" ({format_remaining(parsed.when)}) 에 {channel} 로 알립니다."
    )
    print(f"   내용: {parsed.message}")
    if not config.can_send:
        print(
            "\n⚠️  아직 슬랙 전송 설정(.env)이 없어서 시간이 돼도 안 보내집니다."
            "\n   `python3 -m teambrain.reminder doctor` 로 확인해보세요."
        )
    return 0


def cmd_list(args: argparse.Namespace, config: Config) -> int:
    store = _open_store(config)
    status = None if args.all else (args.status or STATUS_PENDING)
    reminders = store.list(status=status, limit=args.limit)
    if not reminders:
        print("예약이 없습니다." if args.all else "대기 중인 예약이 없습니다.")
        return 0

    now = datetime.now(timezone.utc)
    print(f"{'번호':>4}  {pad('예정 시각', 22)}{pad('남은 시간', 18)}{pad('상태', 8)}채널")
    print("-" * 72)
    for reminder in reminders:
        remaining = format_remaining(reminder.due_at, now) if reminder.status == STATUS_PENDING else "-"
        print(
            f"{reminder.id:>4}  {pad(format_when(reminder.due_at, config.tz), 22)}"
            f"{pad(remaining, 18)}{pad(STATUS_LABELS.get(reminder.status, reminder.status), 8)}"
            f"{reminder.channel}"
        )
        print(f"      └ {reminder.message}")
        if reminder.last_error:
            print(f"        ⚠️ 마지막 오류: {reminder.last_error}")
    return 0


def cmd_cancel(args: argparse.Namespace, config: Config) -> int:
    store = _open_store(config)
    reminder = store.get(args.id)
    if reminder is None:
        print(f"#{args.id} 예약이 없습니다.", file=sys.stderr)
        return 1
    if store.cancel(args.id):
        print(f"🗑️  예약 #{args.id} 취소됨 — {reminder.message}")
        return 0
    print(
        f"#{args.id} 는 이미 '{STATUS_LABELS.get(reminder.status, reminder.status)}' 상태라 취소할 수 없습니다.",
        file=sys.stderr,
    )
    return 1


def cmd_run(args: argparse.Namespace, config: Config) -> int:
    store = _open_store(config)
    notifier = build_notifier(config, dry_run=args.dry_run)
    if args.once:
        results = run_once(
            store,
            notifier,
            config.tz,
            max_attempts=config.max_attempts,
            late_notice_seconds=config.late_notice_seconds,
        )
        sent = sum(1 for result in results if result.ok)
        print(f"확인 완료 — 보낼 것 {len(results)}건 중 {sent}건 전송.")
        return 0 if sent == len(results) else 1
    run_forever(
        store,
        notifier,
        config.tz,
        poll_seconds=args.poll or config.poll_seconds,
        max_attempts=config.max_attempts,
        late_notice_seconds=config.late_notice_seconds,
        install_signal_handlers=True,
    )
    return 0


def cmd_bot(args: argparse.Namespace, config: Config) -> int:
    from .bot import run_bot  # slack_bolt가 필요해서 이 명령을 쓸 때만 불러온다

    return run_bot(config, dry_run=args.dry_run)


def cmd_doctor(args: argparse.Namespace, config: Config) -> int:
    print("== 리마인드 기능 설정 점검 ==\n")
    env_files = find_env_files()
    print(f"· .env 파일        : {env_files[0] if env_files else '없음 (환경변수만 사용)'}")

    if config.slack_bot_token:
        send_mode = f"봇 토큰 (…{config.slack_bot_token[-4:]})"
    elif config.slack_webhook_url:
        send_mode = "Incoming Webhook (채널 고정)"
    else:
        send_mode = "❌ 없음 — SLACK_BOT_TOKEN 또는 SLACK_WEBHOOK_URL 필요"
    print(f"· 슬랙 전송 방식   : {send_mode}")
    print(f"· 기본 채널        : {config.default_channel or '❌ 없음 (SLACK_DEFAULT_CHANNEL)'}")
    print(f"· 봇 멘션 수신     : ", end="")
    if not config.slack_app_token:
        print("불가 — SLACK_APP_TOKEN(xapp-) 없음 (터미널 등록은 가능)")
    else:
        try:
            import slack_bolt  # noqa: F401

            print("가능")
        except ImportError:
            print("불가 — `pip3 install slack_bolt` 필요")

    print(f"· 시간대           : {config.timezone_name}")
    print(f"· 확인 주기        : {config.poll_seconds}초")
    print(f"· DB 파일          : {config.db_path} ({'있음' if config.db_path.exists() else '아직 없음'})")

    store = _open_store(config)
    counts = store.counts()
    summary = ", ".join(f"{STATUS_LABELS.get(k, k)} {v}건" for k, v in sorted(counts.items())) or "없음"
    print(f"· 예약 현황        : {summary}")

    now = datetime.now(config.tz)
    print(f"\n지금 시각({config.timezone_name}): {format_when(now, config.tz)}")
    if not config.can_send:
        print("\n⚠️  전송 설정이 없어 `run` 이 알림을 보내지 못합니다. README.md 3번 항목을 보세요.")
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m teambrain.reminder",
        description="특정 날짜/시간에 슬랙으로 리마인드 알림을 보내는 기능",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="자세한 로그 출력")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="시간 표현을 어떻게 읽었는지만 확인 (저장 안 함)")
    check.add_argument("text", nargs="+", help='예: "내일 오후 3시 멘토링 준비"')
    check.set_defaults(func=cmd_check)

    add = subparsers.add_parser("add", help="리마인드 예약하기")
    add.add_argument("text", nargs="+", help='예: "8월 1일 15시 회의자료 공유"')
    add.add_argument("--to", help="보낼 채널 ID 또는 #채널명 (기본: SLACK_DEFAULT_CHANNEL)")
    add.add_argument("--by", help="등록자 표시 (슬랙 사용자 ID를 넣으면 멘션됨)")
    add.set_defaults(func=cmd_add)

    listing = subparsers.add_parser("list", help="예약 목록 보기")
    listing.add_argument("--all", action="store_true", help="전송·취소된 것까지 전부")
    listing.add_argument("--status", choices=sorted(STATUS_LABELS), help="특정 상태만")
    listing.add_argument("--limit", type=int, default=50, help="최대 건수 (기본 50)")
    listing.set_defaults(func=cmd_list)

    cancel = subparsers.add_parser("cancel", help="예약 취소")
    cancel.add_argument("id", type=int, help="예약 번호 (list 로 확인)")
    cancel.set_defaults(func=cmd_cancel)

    run = subparsers.add_parser("run", help="시간이 된 알림을 보내는 상시 실행")
    run.add_argument("--once", action="store_true", help="한 번만 확인하고 종료")
    run.add_argument("--dry-run", action="store_true", help="실제 전송 없이 화면에만 출력")
    run.add_argument("--poll", type=int, help="확인 주기(초)")
    run.set_defaults(func=cmd_run)

    bot = subparsers.add_parser("bot", help="슬랙에서 봇 멘션으로 등록받기 (+ 전송까지 한 프로세스)")
    bot.add_argument("--dry-run", action="store_true", help="실제 전송 없이 화면에만 출력")
    bot.set_defaults(func=cmd_bot)

    doctor = subparsers.add_parser("doctor", help="설정이 제대로 됐는지 점검")
    doctor.set_defaults(func=cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.verbose)
    try:
        config = load_config()
        return args.func(args, config)
    except ParseError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2
    except (ConfigError, NotifyError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:  # pragma: no cover
        print("\n중단했습니다.")
        return 130
