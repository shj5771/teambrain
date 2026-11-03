"""설정 로딩 테스트."""

import unittest
from pathlib import Path

from teambrain.reminder.config import (
    DEFAULT_POLL_SECONDS,
    DEFAULT_TIMEZONE,
    Config,
    ConfigError,
    load_config,
    parse_env_text,
)


class ParseEnvTextTest(unittest.TestCase):
    def test_parses_pairs_comments_and_quotes(self):
        parsed = parse_env_text(
            "\n".join(
                [
                    "# 주석",
                    "SLACK_BOT_TOKEN=xoxb-123",
                    'SLACK_DEFAULT_CHANNEL="C0ABCDEF"',
                    "export REMINDER_TIMEZONE='Asia/Seoul'",
                    "빈줄무시",
                    "",
                ]
            )
        )
        self.assertEqual(
            parsed,
            {
                "SLACK_BOT_TOKEN": "xoxb-123",
                "SLACK_DEFAULT_CHANNEL": "C0ABCDEF",
                "REMINDER_TIMEZONE": "Asia/Seoul",
            },
        )


class LoadConfigTest(unittest.TestCase):
    def load(self, env):
        return load_config(env=env, use_env_files=False)

    def test_defaults(self):
        config = self.load({})
        self.assertEqual(config.timezone_name, DEFAULT_TIMEZONE)
        self.assertEqual(config.poll_seconds, DEFAULT_POLL_SECONDS)
        self.assertFalse(config.can_send)
        self.assertEqual(config.tz.key, "Asia/Seoul")

    def test_reads_values(self):
        config = self.load(
            {
                "SLACK_BOT_TOKEN": "xoxb-1",
                "SLACK_APP_TOKEN": "xapp-1",
                "SLACK_DEFAULT_CHANNEL": "C1",
                "REMINDER_POLL_SECONDS": "5",
                "REMINDER_DB_PATH": "~/somewhere/r.db",
            }
        )
        self.assertTrue(config.can_send)
        self.assertEqual(config.poll_seconds, 5)
        self.assertEqual(config.db_path, Path.home() / "somewhere" / "r.db")

    def test_blank_values_are_ignored(self):
        self.assertIsNone(self.load({"SLACK_BOT_TOKEN": "   "}).slack_bot_token)

    def test_bad_number_raises(self):
        with self.assertRaises(ConfigError):
            self.load({"REMINDER_POLL_SECONDS": "곧바로"})

    def test_zero_poll_seconds_raises(self):
        with self.assertRaises(ConfigError):
            self.load({"REMINDER_POLL_SECONDS": "0"})

    def test_bad_timezone_raises_on_use(self):
        config = Config(timezone_name="Mars/Olympus")
        with self.assertRaises(ConfigError):
            config.tz


if __name__ == "__main__":
    unittest.main()
