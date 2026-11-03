"""설정 로딩 — 환경변수와 `.env` 파일에서 읽는다.

우선순위: 실제 환경변수 > 가장 가까운 `.env` 파일 > 기본값.
`.env`는 `.gitignore`에 이미 들어가 있어서 GitHub에 올라가지 않는다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "Asia/Seoul"
DEFAULT_DB_PATH = Path.home() / ".teambrain" / "reminders.db"
DEFAULT_POLL_SECONDS = 20
DEFAULT_MAX_ATTEMPTS = 5
# 예정 시각보다 이만큼 넘게 늦어지면 "늦게 전송됨" 표시를 붙인다.
DEFAULT_LATE_NOTICE_SECONDS = 120


class ConfigError(RuntimeError):
    """설정이 모자라서 실행할 수 없을 때."""


def parse_env_text(text: str) -> dict[str, str]:
    """아주 단순한 `.env` 파서 (`KEY=VALUE`, `#` 주석, 따옴표 제거)."""
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def find_env_files(start: Path | None = None) -> list[Path]:
    """모듈 위치에서 위로 올라가며 `.env` 파일을 모은다 (가까운 것이 우선)."""
    start = (start or Path(__file__).resolve().parent).resolve()
    found: list[Path] = []
    for directory in [start, *start.parents]:
        candidate = directory / ".env"
        if candidate.is_file():
            found.append(candidate)
    return found


def _int_from(values: dict[str, str], key: str, default: int) -> int:
    raw = values.get(key, "").strip()
    if not raw:
        return default
    try:
        parsed = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{key} 는 숫자여야 합니다 (지금 값: {raw!r})") from exc
    if parsed <= 0:
        raise ConfigError(f"{key} 는 1 이상이어야 합니다 (지금 값: {parsed})")
    return parsed


@dataclass(frozen=True)
class Config:
    slack_bot_token: str | None = None
    slack_app_token: str | None = None
    slack_webhook_url: str | None = None
    default_channel: str | None = None
    db_path: Path = DEFAULT_DB_PATH
    timezone_name: str = DEFAULT_TIMEZONE
    poll_seconds: int = DEFAULT_POLL_SECONDS
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    late_notice_seconds: int = DEFAULT_LATE_NOTICE_SECONDS

    @property
    def tz(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.timezone_name)
        except Exception as exc:  # 잘못된 타임존 이름
            raise ConfigError(
                f"REMINDER_TIMEZONE 값이 올바른 시간대 이름이 아닙니다: {self.timezone_name!r}"
            ) from exc

    @property
    def can_send(self) -> bool:
        """실제로 슬랙에 보낼 수 있는 설정이 있는지."""
        return bool(self.slack_bot_token or self.slack_webhook_url)


def load_config(env: dict[str, str] | None = None, use_env_files: bool = True) -> Config:
    """환경변수 + `.env`를 합쳐 `Config`를 만든다."""
    values: dict[str, str] = {}
    if use_env_files:
        # 먼 곳 → 가까운 곳 순서로 덮어써서 "가까운 .env가 우선"이 되게 한다.
        for path in reversed(find_env_files()):
            try:
                values.update(parse_env_text(path.read_text(encoding="utf-8")))
            except OSError:
                continue
    values.update({k: v for k, v in (env if env is not None else os.environ).items() if v})

    db_raw = values.get("REMINDER_DB_PATH", "").strip()
    db_path = Path(db_raw).expanduser() if db_raw else DEFAULT_DB_PATH

    def clean(key: str) -> str | None:
        value = values.get(key, "").strip()
        return value or None

    return Config(
        slack_bot_token=clean("SLACK_BOT_TOKEN"),
        slack_app_token=clean("SLACK_APP_TOKEN"),
        slack_webhook_url=clean("SLACK_WEBHOOK_URL"),
        default_channel=clean("SLACK_DEFAULT_CHANNEL"),
        db_path=db_path,
        timezone_name=values.get("REMINDER_TIMEZONE", "").strip() or DEFAULT_TIMEZONE,
        poll_seconds=_int_from(values, "REMINDER_POLL_SECONDS", DEFAULT_POLL_SECONDS),
        max_attempts=_int_from(values, "REMINDER_MAX_ATTEMPTS", DEFAULT_MAX_ATTEMPTS),
        late_notice_seconds=_int_from(
            values, "REMINDER_LATE_NOTICE_SECONDS", DEFAULT_LATE_NOTICE_SECONDS
        ),
    )
