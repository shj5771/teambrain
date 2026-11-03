"""한국어 시간 표현 파서 테스트."""

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from teambrain.reminder.timeparse import (
    ParseError,
    format_remaining,
    format_when,
    parse_when,
)

KST = ZoneInfo("Asia/Seoul")
# 기준 시각: 2026-07-30(목) 11:00
NOW = datetime(2026, 7, 30, 11, 0, tzinfo=KST)


def when(text, now=NOW):
    return parse_when(text, now=now).when


class AbsoluteDateTest(unittest.TestCase):
    def test_iso_date_with_clock(self):
        parsed = parse_when("2026-08-01 09:30 스프린트 회고", now=NOW)
        self.assertEqual(parsed.when, datetime(2026, 8, 1, 9, 30, tzinfo=KST))
        self.assertEqual(parsed.message, "스프린트 회고")

    def test_korean_date_with_meridiem(self):
        self.assertEqual(
            when("2026년 8월 1일 오후 4시 데모"), datetime(2026, 8, 1, 16, 0, tzinfo=KST)
        )

    def test_month_day_only_defaults_to_9am(self):
        parsed = parse_when("8월 1일 팀 회식", now=NOW)
        self.assertEqual(parsed.when, datetime(2026, 8, 1, 9, 0, tzinfo=KST))
        self.assertEqual(parsed.message, "팀 회식")

    def test_slash_date(self):
        self.assertEqual(when("8/1 09:00 팀 회식"), datetime(2026, 8, 1, 9, 0, tzinfo=KST))

    def test_month_day_rolls_to_next_year(self):
        year_end = datetime(2026, 12, 31, 10, 0, tzinfo=KST)
        self.assertEqual(
            when("1/2 신년 회의", now=year_end), datetime(2027, 1, 2, 9, 0, tzinfo=KST)
        )

    def test_invalid_dates_raise_parse_error(self):
        for text in ("2026-02-30 없는 날짜", "8월 32일 없는 날짜"):
            with self.subTest(text=text), self.assertRaises(ParseError):
                parse_when(text, now=NOW)


class RelativeDayTest(unittest.TestCase):
    def test_day_words(self):
        cases = {
            "오늘 18시 스탠드업": datetime(2026, 7, 30, 18, 0, tzinfo=KST),
            "내일 오후 3시 멘토링": datetime(2026, 7, 31, 15, 0, tzinfo=KST),
            "모레 정오 점심": datetime(2026, 8, 1, 12, 0, tzinfo=KST),
            "글피 10시 회의": datetime(2026, 8, 2, 10, 0, tzinfo=KST),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(when(text), expected)

    def test_today_past_time_is_rejected(self):
        with self.assertRaises(ParseError):
            parse_when("오늘 오전 9시 아침 스탠드업", now=NOW)

    def test_past_day_word_is_rejected(self):
        with self.assertRaises(ParseError) as ctx:
            parse_when("어제 3시 회의", now=NOW)
        self.assertIn("어제", str(ctx.exception))

    def test_past_word_inside_message_is_kept(self):
        parsed = parse_when("내일 3시 지난주 회의록 정리", now=NOW)
        self.assertEqual(parsed.when, datetime(2026, 7, 31, 15, 0, tzinfo=KST))
        self.assertEqual(parsed.message, "지난주 회의록 정리")


class WeekdayTest(unittest.TestCase):
    def test_coming_weekday(self):
        # 2026-07-30은 목요일 → "금요일"은 다음 날
        self.assertEqual(when("금요일 오후 2시 멘토링"), datetime(2026, 7, 31, 14, 0, tzinfo=KST))

    def test_same_weekday_later_today(self):
        self.assertEqual(when("목요일 15시 회의"), datetime(2026, 7, 30, 15, 0, tzinfo=KST))

    def test_same_weekday_already_past_rolls_a_week(self):
        self.assertEqual(when("목요일 10시 회의"), datetime(2026, 8, 6, 10, 0, tzinfo=KST))

    def test_next_week(self):
        self.assertEqual(when("다음주 월요일 10시 주간회의"), datetime(2026, 8, 3, 10, 0, tzinfo=KST))

    def test_week_after_next(self):
        self.assertEqual(when("다다음주 화요일 10시 회고"), datetime(2026, 8, 11, 10, 0, tzinfo=KST))

    def test_this_week(self):
        self.assertEqual(when("이번주 토요일 13시 밥"), datetime(2026, 8, 1, 13, 0, tzinfo=KST))


class RelativeTimeTest(unittest.TestCase):
    def test_minutes(self):
        self.assertEqual(when("30분 뒤 물 마시기"), datetime(2026, 7, 30, 11, 30, tzinfo=KST))

    def test_hours(self):
        self.assertEqual(when("2시간 후 산책"), datetime(2026, 7, 30, 13, 0, tzinfo=KST))

    def test_hours_and_minutes(self):
        self.assertEqual(when("1시간 30분 뒤 빨래"), datetime(2026, 7, 30, 12, 30, tzinfo=KST))

    def test_days_with_explicit_clock(self):
        self.assertEqual(when("3일 뒤 10시 리허설"), datetime(2026, 8, 2, 10, 0, tzinfo=KST))

    def test_weeks_keeps_clock(self):
        self.assertEqual(when("2주 뒤 회고"), datetime(2026, 8, 13, 11, 0, tzinfo=KST))


class ClockTest(unittest.TestCase):
    def test_bare_small_hour_is_afternoon(self):
        self.assertEqual(when("내일 3시 회의"), datetime(2026, 7, 31, 15, 0, tzinfo=KST))

    def test_bare_large_hour_is_as_written(self):
        self.assertEqual(when("내일 9시 회의"), datetime(2026, 7, 31, 9, 0, tzinfo=KST))

    def test_time_only_rolls_to_tomorrow_when_past(self):
        self.assertEqual(when("9시 30분 데일리"), datetime(2026, 7, 31, 9, 30, tzinfo=KST))

    def test_time_only_stays_today_when_future(self):
        self.assertEqual(when("15:00 데모"), datetime(2026, 7, 30, 15, 0, tzinfo=KST))

    def test_meridiem_variants(self):
        cases = {
            "8월 1일 오전 12시 자정작업": datetime(2026, 8, 1, 0, 0, tzinfo=KST),
            "8월 1일 오후 12시 점심": datetime(2026, 8, 1, 12, 0, tzinfo=KST),
            "8월 1일 밤 11시 로그정리": datetime(2026, 8, 1, 23, 0, tzinfo=KST),
            "8월 1일 밤 12시 배치": datetime(2026, 8, 1, 0, 0, tzinfo=KST),
            "8월 1일 새벽 3시 배치확인": datetime(2026, 8, 1, 3, 0, tzinfo=KST),
            "8월 1일 저녁 7시 저녁약속": datetime(2026, 8, 1, 19, 0, tzinfo=KST),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(when(text), expected)

    def test_half_hour(self):
        self.assertEqual(when("내일 3시 반 미팅"), datetime(2026, 7, 31, 15, 30, tzinfo=KST))

    def test_fixed_words(self):
        self.assertEqual(when("자정에 서버 재시작 확인"), datetime(2026, 7, 31, 0, 0, tzinfo=KST))
        self.assertEqual(when("내일 정오 점심"), datetime(2026, 7, 31, 12, 0, tzinfo=KST))

    def test_impossible_hour(self):
        with self.assertRaises(ParseError):
            parse_when("내일 25시 회의", now=NOW)


class MessageCleanupTest(unittest.TestCase):
    def test_strips_command_phrasing(self):
        parsed = parse_when("내일 오후 3시에 멘토링 준비물 챙기기 리마인드 해줘", now=NOW)
        self.assertEqual(parsed.message, "멘토링 준비물 챙기기")

    def test_strips_bot_mention_and_particles(self):
        parsed = parse_when(
            "<@U12345678> 다음주 화요일에 오전 9시 30분에 기획서 최종 점검 알려줘", now=NOW
        )
        self.assertEqual(parsed.message, "기획서 최종 점검")
        self.assertEqual(parsed.when, datetime(2026, 8, 4, 9, 30, tzinfo=KST))

    def test_time_expression_at_the_end(self):
        parsed = parse_when("회의자료 공유 8월 1일 15시", now=NOW)
        self.assertEqual(parsed.message, "회의자료 공유")
        self.assertEqual(parsed.when, datetime(2026, 8, 1, 15, 0, tzinfo=KST))

    def test_missing_message(self):
        with self.assertRaises(ParseError):
            parse_when("내일 오전 9시", now=NOW)

    def test_missing_time(self):
        with self.assertRaises(ParseError):
            parse_when("그냥 아무 내용", now=NOW)

    def test_empty_input(self):
        with self.assertRaises(ParseError):
            parse_when("   ", now=NOW)


class FormattingTest(unittest.TestCase):
    def test_format_when(self):
        self.assertEqual(
            format_when(datetime(2026, 8, 1, 15, 0, tzinfo=KST)), "2026-08-01(토) 15:00"
        )

    def test_format_remaining(self):
        target = datetime(2026, 8, 1, 15, 0, tzinfo=KST)
        self.assertEqual(format_remaining(target, NOW), "2일 4시간 뒤")
        self.assertEqual(format_remaining(NOW, NOW), "지금")
        self.assertEqual(
            format_remaining(datetime(2026, 7, 30, 11, 0, 30, tzinfo=KST), NOW), "1분 안"
        )


if __name__ == "__main__":
    unittest.main()
