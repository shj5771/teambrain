"""전송 계층 테스트 — 네트워크를 타지 않고 transport를 갈아끼워 검증."""

import json
import unittest

from teambrain.reminder.config import Config
from teambrain.reminder.notifier import (
    ConsoleNotifier,
    NotifyError,
    SlackBotNotifier,
    SlackWebhookNotifier,
    build_notifier,
)


class RecordingTransport:
    def __init__(self, status=200, body='{"ok": true}'):
        self.status = status
        self.body = body
        self.calls = []

    def __call__(self, url, payload, headers):
        self.calls.append((url, payload, headers))
        return self.status, self.body


class SlackBotNotifierTest(unittest.TestCase):
    def test_posts_channel_and_text(self):
        transport = RecordingTransport()
        SlackBotNotifier("xoxb-test", transport=transport).send("C1", "안녕")

        url, payload, headers = transport.calls[0]
        self.assertEqual(url, "https://slack.com/api/chat.postMessage")
        self.assertEqual(payload, {"channel": "C1", "text": "안녕"})
        self.assertEqual(headers["Authorization"], "Bearer xoxb-test")

    def test_permanent_slack_error(self):
        transport = RecordingTransport(body=json.dumps({"ok": False, "error": "not_in_channel"}))
        with self.assertRaises(NotifyError) as ctx:
            SlackBotNotifier("xoxb-test", transport=transport).send("C1", "안녕")
        self.assertTrue(ctx.exception.permanent)
        self.assertIn("초대", str(ctx.exception))

    def test_unknown_error_is_retryable(self):
        transport = RecordingTransport(body=json.dumps({"ok": False, "error": "ratelimited"}))
        with self.assertRaises(NotifyError) as ctx:
            SlackBotNotifier("xoxb-test", transport=transport).send("C1", "안녕")
        self.assertFalse(ctx.exception.permanent)

    def test_non_json_response(self):
        transport = RecordingTransport(status=502, body="<html>bad gateway</html>")
        with self.assertRaises(NotifyError) as ctx:
            SlackBotNotifier("xoxb-test", transport=transport).send("C1", "안녕")
        self.assertFalse(ctx.exception.permanent)

    def test_missing_channel_is_permanent(self):
        with self.assertRaises(NotifyError) as ctx:
            SlackBotNotifier("xoxb-test", transport=RecordingTransport()).send("", "안녕")
        self.assertTrue(ctx.exception.permanent)

    def test_empty_token_rejected(self):
        with self.assertRaises(ValueError):
            SlackBotNotifier("")


class SlackWebhookNotifierTest(unittest.TestCase):
    def test_sends_text_only(self):
        transport = RecordingTransport(body="ok")
        SlackWebhookNotifier("https://hooks.slack.test/x", transport=transport).send("C1", "안녕")
        url, payload, _ = transport.calls[0]
        self.assertEqual(url, "https://hooks.slack.test/x")
        self.assertEqual(payload, {"text": "안녕"})

    def test_client_error_is_permanent(self):
        transport = RecordingTransport(status=404, body="no_service")
        with self.assertRaises(NotifyError) as ctx:
            SlackWebhookNotifier("https://hooks.slack.test/x", transport=transport).send("C1", "안녕")
        self.assertTrue(ctx.exception.permanent)

    def test_server_error_is_retryable(self):
        transport = RecordingTransport(status=500, body="oops")
        with self.assertRaises(NotifyError) as ctx:
            SlackWebhookNotifier("https://hooks.slack.test/x", transport=transport).send("C1", "안녕")
        self.assertFalse(ctx.exception.permanent)


class BuildNotifierTest(unittest.TestCase):
    def test_dry_run_wins(self):
        config = Config(slack_bot_token="xoxb-1", slack_webhook_url="https://hooks.slack.test/x")
        self.assertIsInstance(build_notifier(config, dry_run=True), ConsoleNotifier)

    def test_bot_token_preferred_over_webhook(self):
        config = Config(slack_bot_token="xoxb-1", slack_webhook_url="https://hooks.slack.test/x")
        self.assertIsInstance(build_notifier(config), SlackBotNotifier)

    def test_webhook_fallback(self):
        config = Config(slack_webhook_url="https://hooks.slack.test/x")
        self.assertIsInstance(build_notifier(config), SlackWebhookNotifier)

    def test_no_config_raises_with_guidance(self):
        with self.assertRaises(NotifyError) as ctx:
            build_notifier(Config())
        self.assertIn("SLACK_BOT_TOKEN", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
