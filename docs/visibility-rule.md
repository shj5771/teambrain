# 팀 지식 공유 범위(visibility) 규칙

> 코드: `teambrain/memory_provider/visibility.py`

## 규칙

Hermes의 memory-provider `initialize()`에 전달되는 `chat_type` 값(`"channel"`/`"dm"`/`"group"`)을 기준으로,
**`chat_type == "channel"`(완전 공개 Mattermost 채널)일 때만 팀 공유 저장소(`~/.hermes/team_knowledge/store.jsonl`)에
기록**한다. `"dm"`(다이렉트 메시지), `"group"`(그룹 DM 또는 비공개 채널), 값이 없거나 모르는 값은 전부 **저장하지 않는다(fail-closed)**.

이 값은 추측한 게 아니다. **Mattermost가 이미 구분해 저장해 둔 실제 채널 타입(D/G/P/O)**을
Hermes의 Mattermost 어댑터(`_CHANNEL_TYPE_MAP`)가 그대로 넘겨준 것이다.

추가로, 예약 작업(cron)·서브에이전트·컨텍스트 정리처럼 실제 사용자 대화가 아닌 턴도 저장하지 않는다.

## 왜 이 규칙인가

목표 기준은 "비공개 채널·DM 대화는 팀 검색에 절대 뜨지 않는다"이다. 위 규칙은 Hermes 코어를 수정하지 않고,
Mattermost API를 추가로 호출하지도 않고, 이미 넘어오는 값만으로 이 기준을 만족한다.

## 검토했지만 채택하지 않은 대안

**Mattermost 검색 API에 맡기기**: 팀원 각자의 **개인 Mattermost 계정 토큰**으로 검색하면,
그 사람이 볼 수 없는 채널은 결과에서 자동으로 빠진다. `chat_type`보다 정확한 권한 처리가 되는 셈이다.
다만 팀원마다 개인 토큰을 따로 발급하고 보관해야 해서 "팀원별 봇 계정" 방식과 준비 과정이 달라진다.
나중에 다시 검토할 수 있다.

## 알려진 한계

Hermes의 Mattermost 어댑터는 모르는 채널 타입 코드를 받으면 `_CHANNEL_TYPE_MAP.get(raw, "channel")`로
**"channel"(공개 채널)로 간주한다(fail-open)**. 이 플러그인은 넘겨받은 값만 볼 수 있어서,
그 앞 단계에서 잘못 분류된 것까지는 잡지 못한다. 자세한 내용은 [`SECURITY.md`](../SECURITY.md)를 참고하자.

## 아직 지원하지 않는 것

- 여러 Mattermost 팀/워크스페이스: 항목마다 `chat_id`/`chat_name`을 이미 기록하고 있어서, 나중에 스키마를 바꾸지 않고 필터만 추가하면 된다.
- 비공개 채널 멤버끼리만 공유: 지금은 비공개 채널 대화를 아예 공유하지 않는다.
- 임베딩/벡터 검색: 지금은 키워드 겹침 점수로만 찾는다.
