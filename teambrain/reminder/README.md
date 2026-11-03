# 리마인드 알림 (Slack)

정해진 날짜/시간이 되면 슬랙으로 알림을 보내주는 기능.

```
@리마인드봇 내일 오후 3시 멘토링 준비물 챙기기
  → ✅ 2026-07-31(금) 15:00 (1일 4시간 뒤)에 알려드릴게요. (예약 #7)
  → (그 시각에) ⏰ 리마인드: 멘토링 준비물 챙기기
```

팀 일정 알림 아이디어 중
**"일정 시작 전 자동 리마인드"** 부분을 먼저 실물로 만든 것이다. 지금은 팀이 실제로
붙여본 적 있는 Slack에 먼저 붙였고, 최종 제품(Mattermost)로 옮길 지점은 아래
"나중에 Mattermost로 옮기기"에 적어 뒀다.

- **설치할 게 없다.** 예약하고 시간 되면 보내는 핵심 기능은 파이썬 표준 라이브러리만 쓴다.
  슬랙에서 봇을 멘션해서 등록받는 부분만 `slack_bolt`가 추가로 필요하다.
- **AI(LLM)를 안 쓴다.** 시간 표현 해석은 규칙 기반이라 비용이 0이고, 인터넷/크레딧이
  없어도 돌아가고, 같은 문장이면 항상 같은 결과가 나온다.

---

## 1. 1분 만에 해보기 (슬랙 설정 없이)

이 폴더가 아니라 **레포 맨 위 폴더**(`ai-powered-teamwork/`)에서 실행한다.

```bash
# 시간을 어떻게 읽었는지만 확인 (저장 안 함)
python3 -m teambrain.reminder check "내일 오후 3시 멘토링 준비물 챙기기"

# 실제로 보내보기 (아직 슬랙 연결 안 했으니 화면에만 출력)
python3 -m teambrain.reminder add "2분 뒤 이건 테스트" --to C_TEST
python3 -m teambrain.reminder run --dry-run       # Ctrl+C로 종료
```

`--dry-run`은 슬랙으로 보내는 대신 화면에 뭐가 갈지 보여준다.

---

## 2. 쓰는 방법 (명령어)

| 명령 | 하는 일 |
|---|---|
| `check "문장"` | 시간을 어떻게 읽었는지 확인만 (저장 안 함) |
| `add "문장"` | 리마인드 예약. `--to 채널`, `--by 이름` 옵션 |
| `list` | 대기 중인 예약 목록 (`--all` 전체, `--status` 상태별) |
| `cancel 3` | 3번 예약 취소 |
| `run` | **시간이 된 알림을 보내는 상시 실행** (이게 켜져 있어야 알림이 간다) |
| `bot` | 슬랙 멘션으로 등록받기 + 전송까지 한 프로세스에서 (slack_bolt 필요) |
| `doctor` | 설정이 제대로 됐는지 점검 |

모두 `python3 -m teambrain.reminder <명령>` 형태로 쓴다.

> ⚠️ **`run`(또는 `bot`)이 켜져 있는 동안만 알림이 나간다.** `add`는 예약만 하는 것.
> 컴퓨터를 끄거나 프로세스를 종료하면 그때는 안 나가고, 다시 켜면 **놓친 알림을
> "N분 늦게 전송됐어요" 표시와 함께 보낸다** (예약이 사라지지는 않는다).

---

## 3. 슬랙에 실제로 연결하기

### 3-1. 먼저: 토큰은 대화창에 붙여넣지 말 것 ⚠️

AI 코딩 도구의 대화 기록이나 이슈·채팅에 붙여넣은 토큰은 생각보다 쉽게 원격 저장소나
로그에 남는다. **토큰은 어디에도 붙여넣지 말고, 아래 `.env` 파일에
직접 편집기로 붙여넣는다.** `.env`는 `.gitignore`에 들어 있어 올라가지 않는다.

### 3-2. 방법 A — Incoming Webhook (제일 쉬움, 채널 하나 고정)

"등록은 터미널로, 알림은 특정 채널로만" 이면 이걸로 충분하다.

1. https://api.slack.com/apps → 앱 생성(From scratch) → 워크스페이스 선택
2. 왼쪽 **Incoming Webhooks** → On → **Add New Webhook to Workspace** → 채널 선택
3. 생성된 `https://hooks.slack.com/services/...` 주소를 `.env`에 넣는다

```bash
cp teambrain/reminder/env.example .env    # 레포 맨 위 폴더에
# 편집기로 .env 열어서 SLACK_WEBHOOK_URL 채우기
python3 -m teambrain.reminder doctor
```

### 3-3. 방법 B — 봇 토큰 (권장: 채널 여러 개 + 멘션으로 등록 가능)

1. https://api.slack.com/apps → **Create New App** → **From an app manifest** →
   워크스페이스 선택 → 아래 내용 붙여넣기

```yaml
display_information:
  name: 리마인드봇
features:
  bot_user:
    display_name: 리마인드봇
    always_online: true
oauth_config:
  scopes:
    bot:
      - app_mentions:read
      - chat:write
      - chat:write.public
      - im:history
      - im:read
      - im:write
settings:
  event_subscriptions:
    bot_events:
      - app_mention
      - message.im
  socket_mode_enabled: true
```

2. **Basic Information → App-Level Tokens** → Generate Token → scope `connections:write`
   → `xapp-...` 값 복사 (= `SLACK_APP_TOKEN`, 소켓 모드 연결용)
3. **OAuth & Permissions → Install to Workspace** → `xoxb-...` 값 복사 (= `SLACK_BOT_TOKEN`)
4. 알림 받을 채널에서 `/invite @리마인드봇`
5. `.env`에 토큰 두 개 + 기본 채널 ID를 넣고 실행

```bash
pip3 install slack_bolt
python3 -m teambrain.reminder doctor
python3 -m teambrain.reminder bot        # 멘션 수신 + 전송 동시에
```

채널 ID는 슬랙에서 채널 이름 클릭 → 맨 아래 `C0XXXXXXX` 형태로 나온다.
(`#채널명`도 되지만 이름을 바꾸면 깨지므로 ID를 권장.)

> 💡 **Hermes 봇과는 별도의 슬랙 앱으로 만들 것.** 같은 앱을 쓰면 멘션 하나를 두
> 프로그램이 같이 받아 서로 답한다. 리마인드봇은 별개 앱 = 별개 봇 계정으로 둔다.

### 3-4. `.env` 항목

| 이름 | 필수 | 설명 |
|---|---|---|
| `SLACK_BOT_TOKEN` | 방법 B | `xoxb-`로 시작. 여러 채널에 보낼 수 있음 |
| `SLACK_APP_TOKEN` | `bot` 명령 | `xapp-`로 시작. 멘션 수신(소켓 모드)용 |
| `SLACK_WEBHOOK_URL` | 방법 A | 채널 하나 고정 |
| `SLACK_DEFAULT_CHANNEL` | 권장 | `--to` 없이 `add` 할 때 쓸 채널 ID |
| `REMINDER_DB_PATH` | | 예약 저장 위치 (기본 `~/.teambrain/reminders.db`) |
| `REMINDER_TIMEZONE` | | 기본 `Asia/Seoul` |
| `REMINDER_POLL_SECONDS` | | 몇 초마다 확인할지 (기본 20) |

---

## 4. 읽을 수 있는 시간 표현

| 종류 | 예 |
|---|---|
| 날짜 | `2026-08-01`, `2026년 8월 1일`, `8월 1일`, `8/1` |
| 상대 날짜 | `오늘`, `내일`, `모레`, `글피` |
| 요일 | `금요일`, `이번주 금요일`, `다음주 월요일`, `다다음주 화요일` |
| 시각 | `15:00`, `15시`, `오후 3시`, `오후 3시 30분`, `3시 반`, `정오`, `자정` |
| 상대 시각 | `10분 뒤`, `2시간 후`, `1시간 30분 뒤`, `3일 뒤 10시`, `2주 뒤` |

규칙 두 가지만 기억하면 된다.

- **오전/오후를 안 붙인 `1시`~`7시`는 오후로 읽는다** (`3시` = 15:00). `8시`~`23시`는 그대로.
- **날짜만 있고 시각이 없으면 그날 오전 9시.**

헷갈리면 `check`로 먼저 확인하면 된다. 등록할 때도 답장에 "인식한 시간 표현"과
해석된 시각이 같이 나와서, 잘못 읽었으면 바로 알 수 있다.
지난 시각(`어제 3시`, 이미 지난 `오늘 9시`)은 등록되지 않고 이유를 알려준다.

---

## 5. 상시 실행 (알림을 놓치지 않으려면)

노트북에서 `run`을 켜두면 노트북이 잠들 때 같이 멈춘다
당장은 맥에서 로그인할 때 자동 실행되게 두는 정도로 충분하고, 상시 켜진 팀 서버가 있으면
거기로 옮기면 된다.

맥(launchd) 예시 — `~/Library/LaunchAgents/team.port051.reminder.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0"><dict>
  <key>Label</key><string>team.port051.reminder</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/env</string><string>python3</string>
    <string>-m</string><string>teambrain.reminder</string><string>run</string>
  </array>
  <key>WorkingDirectory</key><string>/path/to/teambrain</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/tmp/teambrain-reminder.log</string>
  <key>StandardErrorPath</key><string>/tmp/teambrain-reminder.log</string>
</dict></plist>
```

```bash
launchctl load ~/Library/LaunchAgents/team.port051.reminder.plist   # 등록
launchctl unload ~/Library/LaunchAgents/team.port051.reminder.plist # 해제
```

---

## 6. 테스트

```bash
python3 -m unittest discover -s teambrain/reminder/tests -t .
```

슬랙에 실제로 연결하지 않고 전부 검증한다(전송 계층은 가짜 transport로 대체).

---

## 7. 구조와, 나중에 Mattermost로 옮기기

```
bot.py  (슬랙 멘션 수신)  ─┐
cli.py  (터미널 등록)     ─┴→ timeparse.py → store.py (SQLite)
                                                ↑
                              scheduler.py (20초마다 확인) → notifier.py → Slack
```

- **전송만 갈아끼우면 된다.** `notifier.py`의 `Notifier`(=`send(channel, text)` 하나)
  규약을 지키는 `MattermostNotifier`를 추가하고 `build_notifier`에서 고르게 하면
  스케줄러·저장소·시간 파서는 한 줄도 안 바뀐다.
- **수신부도 마찬가지.** `bot.handle_text()`가 "문장 → 답장 문구"만 담당하는 순수 로직이라,
  Mattermost 어댑터에서도 그대로 호출할 수 있다.
- **라이선스 원칙 준수.** 메신저 서버 소스를 건드리지 않고 공개 REST API만
  호출하는 별도 프로세스다. Mattermost 플러그인 형태로 넣지 말 것.
- **저장은 우리 DB(SQLite).** 외부 캘린더 서비스에 의존하지 않아 데이터 주권 원칙과 맞다.

### 지금 범위 밖 (필요해지면 추가)

- 반복 일정(매주 월요일 10시처럼 되풀이) — 지금은 1회성 예약만
- 팀 캘린더 연동(등록된 일정에서 자동으로 리마인드 생성)
- 예약 수정(지금은 취소 후 다시 등록)
- 여러 사람에게 개별 DM 발송(지금은 등록된 채널 하나로 발송 + 등록자 멘션)
