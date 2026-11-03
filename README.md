# TeamBrain

> 팀 메신저에서 AI 봇을 멘션하기만 하면, 팀의 지식이 저절로 쌓이고 팀원 모두의 AI가 그 지식을 함께 쓰는 협업 레이어.
>
> A team-knowledge layer: mention an AI bot in your self-hosted team chat, and what the team discusses in public channels becomes shared context for every teammate's personal AI.

## 무엇을 하나요

- **팀원마다 개인 AI**: 팀원은 각자 자기 봇(개인 학습 에이전트)을 가집니다. 봇은 대화를 기억하고 그 사람에게 맞춰집니다.
- **팀 공유 지식**: 공개 채널에서 나눈 대화는 팀 공유 저장소에 쌓이고, 누구의 봇이든 답하기 전에 이 저장소에서 관련 내용을 찾아 참고합니다.
- **프라이버시 기본값**: DM과 비공개 채널 대화는 **절대 공유 저장소에 저장되지 않습니다**. 애매한 경우도 저장하지 않습니다. → [`docs/visibility-rule.md`](docs/visibility-rule.md)
- **데이터 주권**: 메신저 서버와 저장소가 모두 팀이 직접 운영하는 서버에 있습니다.

## 구조

```
Mattermost (공식 이미지, 수정 없이 사용)        ← 팀이 쓰는 메신저, 자체 호스팅
        │ 공개 REST / WebSocket API
Hermes Agent (공식 배포판)                      ← 팀원별 개인 AI 엔진
        │ memory-provider 플러그인 인터페이스
★ TeamBrain (이 저장소) ★
  teambrain/memory_provider   팀 공유 지식 저장·검색 + 공개 범위 규칙
  teambrain/reminder          날짜/시간 리마인드 봇 (현재 Slack, Mattermost 이식 예정)
```

TeamBrain은 Mattermost나 Hermes의 소스를 수정하거나 포함하지 않습니다. 각자 공식 배포판을 설치하고, TeamBrain은 공개된 API와 플러그인 인터페이스로만 연결합니다.

## 빠른 시작

### 1. Mattermost 띄우기

```bash
cd deploy
cp .env.example .env        # POSTGRES_PASSWORD를 실제 값으로 바꾸기
docker compose up -d        # → http://localhost:8065
```

### 2. Hermes 설치 + Mattermost 연결

[Hermes Agent](https://github.com/NousResearch/hermes-agent) 공식 문서대로 설치하고, `~/.hermes/.env`에 `MATTERMOST_URL`, `MATTERMOST_TOKEN`(팀원별 봇 계정 토큰)을 설정합니다.

### 3. TeamBrain 플러그인 연결

```bash
mkdir -p ~/.hermes/plugins
ln -s "$(pwd)/teambrain/memory_provider" ~/.hermes/plugins/teambrain
```

각 팀원 프로필의 `config.yaml`:

```yaml
memory:
  provider: teambrain
```

```bash
hermes gateway restart
```

자세한 내용: [`teambrain/memory_provider/README.md`](teambrain/memory_provider/README.md)

### 리마인드 봇

```bash
python3 -m teambrain.reminder --help
```

자세한 내용: [`teambrain/reminder/README.md`](teambrain/reminder/README.md)

## 개발

Python 코드는 **표준 라이브러리만으로** 돌아가는 것을 원칙으로 합니다.

```bash
# 리마인더 테스트
python3 -m unittest discover -s teambrain/reminder/tests -t .

# 랜딩 페이지
cd landing && npm install && npm run dev
```

## 보안

취약점은 공개 이슈 대신 [`SECURITY.md`](SECURITY.md)에 적힌 방법으로 알려 주세요. 알려진 한계도 거기에 정리돼 있습니다.

## 라이선스

TeamBrain 자체 코드는 [Apache License 2.0](LICENSE)을 따릅니다.

함께 쓰는 소프트웨어는 각자의 라이선스를 따르며, 이 저장소에 포함돼 있지 않습니다.
- Mattermost: 서버 AGPL v3 (일부 Apache 2.0). TeamBrain은 수정하지 않은 공식 이미지를 API로만 사용합니다.
- Hermes Agent: MIT

"Mattermost"와 "Hermes"는 각 소유자의 상표입니다. TeamBrain은 이들 프로젝트와 제휴하거나 공식 승인을 받은 프로젝트가 아닙니다.

---

Port_051 · SW Maestro 17기
