# TeamBrain

**팀원 각자의 AI를, 팀 하나의 AI처럼.**

> Turn your teammates' separate AI agents into one team brain: what the team discusses with its bots in public channels is recorded as shared team memory, and every teammate's agent can use it. DMs and private channels are never shared.

## 왜 필요한가

팀원마다 AI 봇을 쓰면 AI도 사람 수만큼 따로 놉니다. 동연의 봇이 들은 결정을 운호의 봇은 모르고, 같은 설명을 봇마다 반복해야 합니다.

TeamBrain을 쓰면 **팀 채널에서 봇과 나눈 대화가 팀의 기억으로 기록**되고, 누구의 봇이든 그 기억을 꺼내 답합니다.

```
#개발 채널    동연 → @동연봇  "DB는 Postgres로 가자. 이유는 ..."
                              ↓  TeamBrain이 팀 기억에 기록

일주일 뒤     운호 → @운호봇  "우리 DB 뭐 쓰기로 했지?"
              @운호봇        "동연님이 #개발에서 Postgres로 정했어요. 이유는 ..."

DM            홍재 → @홍재봇  (개인적인 대화)
                              ✗  팀 기억에 절대 기록되지 않음
```

## 무엇을 해주나요

| 기능 | 설명 |
|---|---|
| **팀 대화 기록** | 공개 채널에서 봇과 나눈 대화를 팀 공유 저장소에 자동으로 기록합니다. |
| **팀 위키 자동 정리** | 쌓인 대화를 AI가 결정 사항·주제별 Markdown 문서로 정리합니다. 누가·어디서·언제 말했는지 남기고, 결정이 바뀌면 이전 결정을 "변경 이력"으로 보존합니다. |
| **팀 기억으로 답하기** | 어떤 팀원의 봇이든, 답하기 전에 정리된 위키를 먼저, 원본 대화를 다음으로 찾아 참고합니다. |
| **프라이버시 기본값** | DM·그룹 DM·비공개 채널, 그리고 판단이 애매한 대화는 기록하지 않습니다. → [규칙 설명](docs/visibility-rule.md) |
| **데이터 주권** | 외부 서비스 없이 팀 서버의 파일 하나에 저장됩니다. |

## 현재 상태와 로드맵

TeamBrain은 초기 버전(MVP)입니다.

**지금 되는 것**
- [x] 공개 채널 대화만 골라 팀 기억에 기록
- [x] 팀원별 봇이 팀 기억을 검색해 답변에 활용 (키워드 기반, 한국어 조사 대응)
- [x] **팀 위키 자동 정리**: 대화 → 주제별 문서, 출처 표기, 결정 변경 이력 보존

**앞으로 할 것**
- [ ] **위키를 메신저에서 보기**: 위키 변경 사항을 채널에 알리고, 메신저에서 바로 열람
- [ ] **의미 기반 검색**: "DB"로 기록된 대화를 "데이터베이스"로 물어도 찾기
- [ ] **비공개 채널 단위 공유**: 같은 비공개 채널 멤버끼리만 공유
- [ ] **사람끼리 나눈 대화 기록**: 지금은 봇과 나눈 대화만 기록됨

## 필요한 것

- **[Hermes Agent](https://github.com/NousResearch/hermes-agent)**: TeamBrain은 Hermes의 메모리 플러그인으로 동작합니다. 팀원마다 Hermes 봇(프로필)을 하나씩 둡니다.
- **팀 메신저**: Hermes가 연결할 수 있는 메신저.
  - ✅ **Mattermost**에서 검증됐습니다.
  - ⚠️ 다른 메신저(Slack, Discord 등)는 아직 검증하지 않았습니다. 공개 채널/DM 구분값이 올바르게 넘어오는지 확인하기 전에는 프라이버시 규칙을 보장할 수 없습니다.

## 설치

```bash
git clone https://github.com/shj5771/teambrain.git
mkdir -p ~/.hermes/plugins
ln -s "$(pwd)/teambrain/teambrain/memory_provider" ~/.hermes/plugins/teambrain
```

팀 기억을 같이 쓸 **각 팀원 프로필의** `config.yaml`에 추가:

```yaml
memory:
  provider: teambrain
```

```bash
hermes gateway restart
```

팀 기억은 `~/.hermes/team_knowledge/store.jsonl`에, 정리된 위키는 `~/.hermes/team_knowledge/wiki/`에 쌓입니다. 위키 정리는 Hermes에 설정된 AI 모델을 그대로 쓰므로 키를 따로 넣을 필요가 없습니다. 팀원들의 봇이 **같은 서버에서** 돌아야 같은 기억을 공유합니다.

자세한 내용: [`teambrain/memory_provider/README.md`](teambrain/memory_provider/README.md)

### 메신저가 아직 없다면

자체 호스팅 메신저를 바로 띄울 수 있는 예시 설정이 [`deploy/`](deploy/)에 있습니다 (공식 Mattermost 이미지, 수정 없이 사용).

```bash
cd deploy && cp .env.example .env   # POSTGRES_PASSWORD를 실제 값으로
docker compose up -d                # → http://localhost:8065
```

## 함께 들어 있는 것

- [`teambrain/reminder/`](teambrain/reminder/): "내일 오후 3시에 알려줘"를 알아듣는 리마인드 봇 (현재 Slack)
- [`landing/`](landing/): 소개 웹페이지

## 개발

Python 코드는 **표준 라이브러리만으로** 돌아가는 것을 원칙으로 합니다.

```bash
python3 -m unittest discover -s teambrain/memory_provider/tests -t .   # 팀 기억·위키 테스트
python3 -m unittest discover -s teambrain/reminder/tests -t .          # 리마인더 테스트
cd landing && npm install && npm run dev                         # 랜딩 페이지
```

## 보안

취약점은 공개 이슈 대신 [`SECURITY.md`](SECURITY.md)의 방법으로 알려 주세요. 알려진 한계도 거기에 정리돼 있습니다.

## 라이선스

TeamBrain 코드는 [Apache License 2.0](LICENSE)을 따릅니다.

TeamBrain은 Hermes Agent(MIT)와 Mattermost(AGPL v3 / Apache 2.0)를 포함하거나 수정하지 않으며, 공개된 플러그인 인터페이스와 API로만 연동합니다. 각 상표는 소유자에게 있으며, TeamBrain은 이들 프로젝트와 제휴 관계가 아닙니다. 자세한 내용은 [`NOTICE`](NOTICE)를 참고하세요.

---

Port_051 · SW Maestro 17기
