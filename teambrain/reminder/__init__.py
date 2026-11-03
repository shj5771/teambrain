"""특정 날짜/시간에 슬랙으로 리마인드 알림을 보내는 기능.

팀 일정 알림 아이디어 중 "일정 시작 전 자동 리마인드"를
Slack에서 먼저 실물로 구현한 것. 구성:

- `timeparse` : "내일 오후 3시" 같은 한국어 표현 → 실제 시각
- `store`     : 예약을 SQLite에 저장 (자체 저장 = 데이터 주권 원칙)
- `notifier`  : 메신저로 메시지 전송 (Slack 구현 + 나중에 Mattermost 추가 가능)
- `scheduler` : 시간이 된 예약을 찾아 전송하는 상시 루프
- `cli`       : 터미널에서 등록/조회/취소/실행
- `bot`       : (선택) 슬랙에서 봇을 멘션해 등록 — slack_bolt 필요

핵심 경로(예약 → 전송)는 파이썬 표준 라이브러리만으로 동작한다.
"""

__all__ = ["timeparse", "store", "notifier", "scheduler", "config"]
