"""메시지 전송 계층.

메신저별 구현을 `Notifier` 하나로 감싸 둔 이유: 지금은 Slack이지만 최종 제품은
Mattermost이므로, 나중에 `MattermostNotifier`만 추가하면 스케줄러·저장소는
한 줄도 안 바뀌게 하기 위함. Slack 호출은 `slack_sdk` 없이 표준 라이브러리(urllib)로
직접 REST API를 부른다 — 설치 없이 바로 돌아가게.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable, Protocol

SLACK_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"
DEFAULT_TIMEOUT_SECONDS = 10

# 다시 시도해도 결과가 같은 Slack 오류 → 재시도하지 않고 바로 실패 처리한다.
PERMANENT_SLACK_ERRORS = {
    "channel_not_found": "채널을 찾을 수 없습니다. 채널 ID가 맞는지 확인해주세요.",
    "not_in_channel": "봇이 그 채널에 없습니다. 채널에서 `/invite @봇이름` 으로 초대해주세요.",
    "is_archived": "보관된(archived) 채널입니다.",
    "invalid_auth": "봇 토큰이 유효하지 않습니다. SLACK_BOT_TOKEN을 다시 확인해주세요.",
    "not_authed": "봇 토큰이 비어 있습니다.",
    "account_inactive": "봇 계정이 비활성 상태입니다.",
    "token_revoked": "봇 토큰이 폐기되었습니다. 새로 발급해주세요.",
    "missing_scope": "봇 권한(scope)이 부족합니다. `chat:write` 권한을 추가해주세요.",
    "msg_too_long": "메시지가 너무 깁니다.",
    "no_text": "보낼 내용이 비어 있습니다.",
}

Transport = Callable[[str, dict, dict], tuple[int, str]]
"""(url, payload, headers) -> (HTTP 상태코드, 응답 본문). 테스트에서 갈아끼우는 지점."""


class NotifyError(RuntimeError):
    """전송 실패. `permanent=True`면 재시도해도 소용없는 종류."""

    def __init__(self, message: str, permanent: bool = False):
        super().__init__(message)
        self.permanent = permanent


class Notifier(Protocol):
    def send(self, channel: str, text: str) -> None: ...
    def describe(self) -> str: ...


def http_post_json(url: str, payload: dict, headers: dict) -> tuple[int, str]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:  # 4xx/5xx
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 429:
            retry_after = exc.headers.get("Retry-After", "?")
            raise NotifyError(f"Slack 요청 제한(429). {retry_after}초 후 재시도 필요.") from exc
        return exc.code, body
    except urllib.error.URLError as exc:  # 네트워크 자체가 안 될 때
        raise NotifyError(f"네트워크 오류: {exc.reason}") from exc


class SlackBotNotifier:
    """봇 토큰(`xoxb-`)으로 아무 채널에나 보낼 수 있는 방식 — 권장."""

    def __init__(self, token: str, transport: Transport = http_post_json):
        if not token:
            raise ValueError("SLACK_BOT_TOKEN 이 필요합니다.")
        self._token = token
        self._transport = transport

    def send(self, channel: str, text: str) -> None:
        if not channel:
            raise NotifyError("보낼 채널이 지정되지 않았습니다.", permanent=True)
        status, body = self._transport(
            SLACK_POST_MESSAGE_URL,
            {"channel": channel, "text": text},
            {"Authorization": f"Bearer {self._token}"},
        )
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            raise NotifyError(f"Slack 응답을 해석할 수 없습니다 (HTTP {status}): {body[:200]}")
        if parsed.get("ok"):
            return
        code = str(parsed.get("error", "unknown_error"))
        hint = PERMANENT_SLACK_ERRORS.get(code)
        raise NotifyError(
            f"Slack 전송 실패({code})" + (f" — {hint}" if hint else ""),
            permanent=hint is not None,
        )

    def describe(self) -> str:
        return "Slack 봇 토큰 (chat.postMessage)"


class SlackWebhookNotifier:
    """Incoming Webhook 방식 — 설정이 제일 쉽지만 **채널이 하나로 고정**된다."""

    def __init__(self, webhook_url: str, transport: Transport = http_post_json):
        if not webhook_url:
            raise ValueError("SLACK_WEBHOOK_URL 이 필요합니다.")
        self._url = webhook_url
        self._transport = transport

    def send(self, channel: str, text: str) -> None:
        status, body = self._transport(self._url, {"text": text}, {})
        if status == 200 and body.strip() in ("ok", ""):
            return
        raise NotifyError(
            f"Slack 웹훅 전송 실패 (HTTP {status}): {body[:200]}",
            permanent=status in (400, 403, 404),
        )

    def describe(self) -> str:
        return "Slack Incoming Webhook (채널 고정)"


class ConsoleNotifier:
    """실제로 안 보내고 화면에만 출력 — 시험용(`--dry-run`)."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send(self, channel: str, text: str) -> None:
        self.sent.append((channel, text))
        print(f"[dry-run] → {channel}\n{text}\n")

    def describe(self) -> str:
        return "화면 출력만 (실제 전송 없음)"


def build_notifier(config, dry_run: bool = False) -> Notifier:
    """설정을 보고 알맞은 전송기를 만든다. 봇 토큰이 있으면 그쪽을 먼저 쓴다."""
    if dry_run:
        return ConsoleNotifier()
    if config.slack_bot_token:
        return SlackBotNotifier(config.slack_bot_token)
    if config.slack_webhook_url:
        return SlackWebhookNotifier(config.slack_webhook_url)
    raise NotifyError(
        "슬랙 전송 설정이 없습니다. `.env`에 SLACK_BOT_TOKEN(권장) 또는 "
        "SLACK_WEBHOOK_URL 중 하나를 넣어주세요. (시험만 해보려면 --dry-run)",
        permanent=True,
    )
