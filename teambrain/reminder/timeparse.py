"""한국어 시간 표현 → 실제 시각(datetime) 변환.

예) "내일 오후 3시 멘토링 준비"  →  (2026-07-31 15:00 KST, "멘토링 준비")

**LLM을 쓰지 않는다.** 규칙(정규식)만 써서 (1) 비용이 안 들고 (2) 네트워크가 없어도
돌고 (3) 같은 입력이면 항상 같은 결과가 나와 테스트가 가능하기 때문이다.
대신 인식 결과를 사람에게 되돌려 보여줘서(`format_when`) 잘못 읽었으면 바로 알 수 있게 한다.

지원하는 표현
- 절대 날짜: `2026-08-01`, `2026년 8월 1일`, `8월 1일`, `8/1`
- 상대 날짜: `오늘`, `내일`, `모레`, `글피`
- 요일:      `금요일`, `이번주 금요일`, `다음주 월요일`, `다다음주 화요일`
- 시각:      `15:00`, `15시`, `오후 3시`, `오후 3시 30분`, `3시 반`, `정오`, `자정`
- 상대 시각: `10분 뒤`, `2시간 후`, `1시간 30분 뒤`, `3일 뒤 10시`, `2주 뒤`

주의: 오전/오후를 안 붙인 `1시`~`7시`는 **오후로 해석**한다(한국어 일상 관용).
`8시`~`23시`는 그대로 본다. 날짜만 있고 시각이 없으면 그날 **오전 9시**.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
DEFAULT_HOUR = 9
WEEKDAY_NAMES = "월화수목금토일"

# 시간 표현 뒤에 붙는 조사 — 표현의 일부로 같이 먹어치워서 본문에 안 남게 한다.
_TAIL = r"(?:\s*(?:에|에는|까지|쯤|경|부터))?"
# 오전/오후는 있을 때만 뒤 공백을 함께 먹는다. `\s*`를 앞에 두면 매치 구간이 앞 공백까지
# 번져서 날짜 구간과 겹쳐 버려지는 문제가 생긴다("2026-08-01 09:30" → 시각 유실).
_MERIDIEM = r"(?:(?P<mer>오전|오후|아침|저녁|밤|낮|새벽)\s*)?"

REL_RE = re.compile(
    r"(?:(?P<weeks>\d+)\s*주(?:일)?)?\s*"
    r"(?:(?P<days>\d+)\s*일)?\s*"
    r"(?:(?P<hours>\d+)\s*시간)?\s*"
    r"(?:(?P<minutes>\d+)\s*분)?\s*"
    r"(?:뒤|후|있다가)" + _TAIL
)
YMD_RE = re.compile(
    r"(?P<y>\d{4})\s*(?:[-./]|년)\s*(?P<m>\d{1,2})\s*(?:[-./]|월)\s*(?P<d>\d{1,2})(?:\s*일)?" + _TAIL
)
MD_RE = re.compile(r"(?<![\d:.])(?P<m>\d{1,2})\s*(?:/|월)\s*(?P<d>\d{1,2})(?:\s*일)?" + _TAIL)
DAYWORD_RE = re.compile(r"(?P<word>내일모레|모레|글피|내일|낼|오늘|금일)" + _TAIL)
WEEKDAY_RE = re.compile(
    r"(?:(?P<week>이번\s*주|금주|다음\s*주|차주|담주|다다음\s*주)\s*)?"
    r"(?P<wd>[월화수목금토일])\s*요일" + _TAIL
)
HHMM_RE = re.compile(_MERIDIEM + r"(?P<h>\d{1,2})\s*:\s*(?P<mi>\d{2})" + _TAIL)
HOUR_RE = re.compile(
    _MERIDIEM + r"(?P<h>\d{1,2})\s*시(?!간)"
    r"\s*(?:(?P<mi>\d{1,2})\s*분|(?P<half>반))?" + _TAIL
)
FIXED_TIME_RE = re.compile(r"(?P<word>정오|자정)" + _TAIL)
# 이미 지난 날을 가리키는 말 — 조용히 오늘로 해석해버리면 안 되므로 따로 잡아 알려준다.
PAST_DAYWORD_RE = re.compile(r"어제|어저께|그제|그저께|지난\s*주|저번\s*주|작년|지난달|저번달")

DAYWORD_OFFSETS = {"오늘": 0, "금일": 0, "내일": 1, "낼": 1, "모레": 2, "내일모레": 2, "글피": 3}
_AM_WORDS = {"오전", "아침", "새벽"}
_PM_WORDS = {"오후", "저녁", "밤", "낮"}

# 본문 끝에 흔히 붙는 "알려줘/리마인드 해줘" 류 — 알림 내용에서 덜어낸다.
_NOISE_SUFFIXES = (
    "리마인드 해줘",
    "리마인드해줘",
    "리마인드 해주세요",
    "리마인드해주세요",
    "알려주세요",
    "알려줘요",
    "알려줘",
    "알람 해줘",
    "알림 보내줘",
    "보내주세요",
    "보내줘",
    "말해줘",
    "해주세요",
    "해줘",
    "부탁해요",
    "부탁해",
    "리마인더",
    "리마인드",
    "알림",
    "알람",
    "라고",
    "이라고",
    "좀",
)
_NOISE_PREFIXES = ("리마인더", "리마인드", "알림", "알람", "-", ":", "·")


class ParseError(ValueError):
    """시간 표현을 읽어내지 못했을 때. 메시지는 사용자에게 그대로 보여줄 수 있는 한국어."""


@dataclass(frozen=True)
class Parsed:
    when: datetime
    """알림을 보낼 시각 (타임존 정보 포함)."""
    message: str
    """알림 본문 (시간 표현을 덜어낸 나머지)."""
    matched: str
    """시간 표현으로 인식한 원문 조각 — 사용자 확인용."""


def _spans_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _first_rel(text: str) -> re.Match[str] | None:
    """상대 표현(`~뒤`) 중 실제로 숫자가 붙은 첫 매치."""
    for match in REL_RE.finditer(text):
        if any(match.group(name) for name in ("weeks", "days", "hours", "minutes")):
            return match
    return None

def _earliest(
    text: str, patterns: list[tuple[str, re.Pattern[str]]], taken: list[tuple[int, int]]
) -> tuple[str, re.Match[str]] | None:
    """이미 쓴 구간(taken)과 겹치지 않는 매치 중 가장 앞선 것."""
    best: tuple[str, re.Match[str]] | None = None
    for kind, pattern in patterns:
        for match in pattern.finditer(text):
            span = match.span()
            if any(_spans_overlap(span, used) for used in taken):
                continue
            if best is None or span[0] < best[1].start():
                best = (kind, match)
            break
    return best


def _time_of(kind: str, match: re.Match[str]) -> tuple[int, int]:
    """시각 매치 → (시, 분). 24시간제로 정규화."""
    if kind == "fixed":
        return (12, 0) if match.group("word") == "정오" else (0, 0)

    groups = match.groupdict()
    hour = int(match.group("h"))
    minute = int(groups["mi"]) if groups.get("mi") else 0
    if groups.get("half"):
        minute = 30
    meridiem = groups.get("mer")

    if meridiem in _AM_WORDS:
        if hour == 12:
            hour = 0
    elif meridiem in _PM_WORDS:
        if hour < 12:
            hour += 12
        if meridiem == "밤" and hour == 12:  # "밤 12시" = 자정
            hour = 0
    elif 1 <= hour <= 7:
        # 오전/오후 없는 1~7시는 오후로 본다 ("3시에 회의" → 15:00)
        hour += 12

    if hour > 23 or minute > 59:
        raise ParseError(f"시각을 읽을 수 없습니다: {match.group().strip()!r}")
    return hour, minute


def _resolve_weekday(match: re.Match[str], today: date) -> tuple[date, bool]:
    """요일 표현 → 날짜. 두 번째 값은 '지났으면 다음 주로 밀어도 되는지'."""
    target = WEEKDAY_NAMES.index(match.group("wd"))
    week = (match.group("week") or "").replace(" ", "")
    monday = today - timedelta(days=today.weekday())
    if week in ("다음주", "차주", "담주"):
        return monday + timedelta(days=7 + target), False
    if week == "다다음주":
        return monday + timedelta(days=14 + target), False
    if week in ("이번주", "금주"):
        return monday + timedelta(days=target), False
    # 수식어 없는 "금요일" → 오늘 포함 가장 가까운 그 요일, 이미 지났으면 다음 주
    return today + timedelta(days=(target - today.weekday()) % 7), True


def _leading_past_word(text: str, spans: list[tuple[int, int]]) -> str | None:
    """시간 표현 바로 앞에 붙은 과거 표현("어제 3시")만 찾아낸다.

    본문 안에 그냥 언급된 경우("내일 3시 지난주 회의록 정리")는 걸러내지 않는다.
    """
    if not spans:
        return None
    first_start = min(start for start, _ in spans)
    for match in PAST_DAYWORD_RE.finditer(text):
        if match.start() >= first_start:
            break
        if not text[match.end() : first_start].strip():
            return match.group()
    return None


def _clean_message(text: str, spans: list[tuple[int, int]]) -> str:
    """시간 표현 구간을 지우고, 붙어 있는 명령어투를 덜어낸다."""
    chars = list(text)
    for start, end in sorted(spans, reverse=True):
        chars[start:end] = " "
    message = re.sub(r"\s+", " ", "".join(chars)).strip()
    message = re.sub(r"^<@[A-Z0-9]+>\s*", "", message).strip()

    changed = True
    while changed and message:
        changed = False
        for suffix in _NOISE_SUFFIXES:
            if message.endswith(suffix) and len(message) > len(suffix):
                message = message[: -len(suffix)].strip()
                changed = True
        for prefix in _NOISE_PREFIXES:
            if message.startswith(prefix) and len(message) > len(prefix):
                message = message[len(prefix) :].strip()
                changed = True
    return message.strip(" ,·-:")


def parse_when(
    text: str,
    now: datetime | None = None,
    tz: ZoneInfo = KST,
    default_hour: int = DEFAULT_HOUR,
) -> Parsed:
    """문장에서 시각과 알림 본문을 뽑아낸다.

    Raises:
        ParseError: 시간 표현이 없거나, 이미 지난 시각이거나, 본문이 비었을 때.
    """
    if not text or not text.strip():
        raise ParseError("내용이 비어 있습니다. 예: `내일 오후 3시 멘토링 준비물 챙기기`")

    now = (now or datetime.now(tz)).astimezone(tz)
    today = now.date()
    spans: list[tuple[int, int]] = []

    rel = _first_rel(text)
    if rel:
        spans.append(rel.span())

    day = _earliest(
        text,
        [("ymd", YMD_RE), ("md", MD_RE), ("word", DAYWORD_RE), ("weekday", WEEKDAY_RE)],
        spans,
    )
    if day:
        spans.append(day[1].span())

    clock = _earliest(text, [("hhmm", HHMM_RE), ("hour", HOUR_RE), ("fixed", FIXED_TIME_RE)], spans)
    if clock:
        spans.append(clock[1].span())

    if not (rel or day or clock):
        raise ParseError(
            "언제 알려줄지 시간을 못 찾았습니다. "
            "예: `내일 오후 3시`, `8월 1일 15시`, `30분 뒤`, `다음주 월요일 10시`"
        )

    past_word = _leading_past_word(text, spans)
    if past_word:
        raise ParseError(
            f"'{past_word}' 처럼 지난 시점으로는 예약할 수 없습니다. 미래 시각으로 알려주세요."
        )

    weekly_rollable = False
    if rel:
        delta = timedelta(
            weeks=int(rel.group("weeks") or 0),
            days=int(rel.group("days") or 0),
            hours=int(rel.group("hours") or 0),
            minutes=int(rel.group("minutes") or 0),
        )
        day_only = not (rel.group("hours") or rel.group("minutes"))
        if clock and day_only:
            # "3일 뒤 10시" — 날짜는 상대, 시각은 명시
            hour, minute = _time_of(*clock)
            when = datetime.combine(
                (now + delta).date(), datetime.min.time(), tzinfo=tz
            ).replace(hour=hour, minute=minute)
        else:
            when = now + delta
    elif day:
        kind, match = day
        if kind == "ymd":
            try:
                target = date(int(match.group("y")), int(match.group("m")), int(match.group("d")))
            except ValueError as exc:
                raise ParseError(f"그런 날짜는 없습니다: {match.group().strip()!r}") from exc
        elif kind == "md":
            month, dom = int(match.group("m")), int(match.group("d"))
            try:
                target = date(today.year, month, dom)
            except ValueError as exc:
                raise ParseError(f"그런 날짜는 없습니다: {match.group().strip()!r}") from exc
            if target < today:  # "1/2"를 12월에 말하면 내년
                target = date(today.year + 1, month, dom)
        elif kind == "word":
            target = today + timedelta(days=DAYWORD_OFFSETS[match.group("word")])
        else:
            target, weekly_rollable = _resolve_weekday(match, today)
        hour, minute = _time_of(*clock) if clock else (default_hour, 0)
        when = datetime.combine(target, datetime.min.time(), tzinfo=tz).replace(
            hour=hour, minute=minute
        )
    else:
        assert clock is not None
        hour, minute = _time_of(*clock)
        when = datetime.combine(today, datetime.min.time(), tzinfo=tz).replace(
            hour=hour, minute=minute
        )
        if when <= now:  # 오늘 그 시각이 지났으면 내일
            when += timedelta(days=1)

    if weekly_rollable and when <= now:
        when += timedelta(days=7)

    if when <= now:
        raise ParseError(
            f"{format_when(when)} 은(는) 이미 지난 시각입니다. 미래 시각으로 알려주세요."
        )

    message = _clean_message(text, spans)
    if not message:
        raise ParseError(
            "무엇을 알려드릴지 내용도 같이 적어주세요. 예: `내일 오후 3시 멘토링 준비물 챙기기`"
        )

    matched = " ".join(text[start:end].strip() for start, end in sorted(spans))
    return Parsed(when=when.replace(second=0, microsecond=0), message=message, matched=matched)


def format_when(when: datetime, tz: ZoneInfo | None = None) -> str:
    """사람이 읽는 형식: `2026-08-01(토) 15:00`."""
    local = when.astimezone(tz) if tz else when
    return f"{local:%Y-%m-%d}({WEEKDAY_NAMES[local.weekday()]}) {local:%H:%M}"


def format_remaining(when: datetime, now: datetime | None = None) -> str:
    """남은 시간: `2일 3시간 뒤`."""
    now = now or datetime.now(when.tzinfo or KST)
    seconds = int((when - now).total_seconds())
    if seconds <= 0:
        return "지금"
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    parts = [f"{days}일" if days else "", f"{hours}시간" if hours else "", f"{minutes}분" if minutes else ""]
    text = " ".join(part for part in parts if part)
    return f"{text} 뒤" if text else "1분 안"
