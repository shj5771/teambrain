# TeamBrain MCP server

팀 기억을 **MCP를 지원하는 어떤 AI 도구에서든** 쓸 수 있게 해 주는 서버입니다 (Claude Code, Claude Desktop, Cursor 등).
메신저 봇들이 쌓은 팀 기억과 위키를 편집기 안에서 바로 찾아볼 수 있습니다.

```
나 (Claude Code에서) > 우리 DB 뭐 쓰기로 했지?
Claude  [team_search 호출]
        지민님이 #dev에서 PostgreSQL로 정했어요. JSON 컬럼과 전문 검색이 필요해서예요. (2026-11-03)
```

표준 라이브러리만 사용하고 추가 설치는 필요 없습니다 (Python 3.10+).

## 도구

| 도구 | 하는 일 | 기본값 |
|---|---|---|
| `team_search` | 위키를 먼저, 그다음 원본 대화를 찾아서 돌려줍니다 | 켜짐 |
| `team_wiki_list` | 위키 문서 목록 | 켜짐 |
| `team_wiki_read` | 위키 문서 하나를 전부 읽기 | 켜짐 |
| `team_remember` | 사용자가 **명시적으로** 공유를 요청한 메모 하나를 팀 기억에 남깁니다 | **꺼짐** (`TEAMBRAIN_MCP_ALLOW_WRITE=1`일 때만) |

### 왜 기본이 읽기 전용인가

메신저에서는 "공개 채널인지"를 보고 기록 여부를 정합니다 ([규칙](../../docs/visibility-rule.md)).
그런데 MCP 클라이언트는 그런 정보를 주지 않습니다. 그래서 같은 원칙(판단할 수 없으면 기록하지 않는다)에 따라
**대화는 절대 자동으로 기록하지 않습니다.** 쓰기를 켜더라도 저장되는 건 사용자가 공유하라고 한 메모 한 줄뿐이고,
AI의 답변이나 대화 맥락은 저장되지 않습니다.

## 연결하기

경로는 이 레포를 받은 위치로 바꾸세요.

**Claude Code**

```bash
claude mcp add teambrain -e PYTHONPATH=/path/to/teambrain -- python3 -m teambrain.mcp_server
```

**Claude Desktop / Cursor** (`claude_desktop_config.json`, `.cursor/mcp.json` 등)

```json
{
  "mcpServers": {
    "teambrain": {
      "command": "python3",
      "args": ["-m", "teambrain.mcp_server"],
      "env": { "PYTHONPATH": "/path/to/teambrain" }
    }
  }
}
```

### 환경 변수

| 변수 | 뜻 | 기본값 |
|---|---|---|
| `TEAMBRAIN_STORE` | 팀 기억 파일 위치 (위키는 그 옆 `wiki/`) | `~/.hermes/team_knowledge/store.jsonl` |
| `TEAMBRAIN_MCP_ALLOW_WRITE` | `1`이면 `team_remember` 도구를 켭니다 | 꺼짐 |
| `TEAMBRAIN_USER` | `team_remember`로 남길 때 기록될 이름 | 컴퓨터 사용자 이름 |

## 지금의 한계

- **같은 컴퓨터의 팀 기억 파일만 읽습니다.** stdio 방식이라, 팀 기억이 서버에 있다면 그 서버에서 쓰거나
  `TEAMBRAIN_STORE`를 공유 폴더로 지정해야 합니다. 원격 접속(HTTP) 지원은 로드맵에 있습니다.
- `team_remember`로 남긴 메모는 다음 위키 정리 때 위키에 반영됩니다. 위키 정리는 Hermes 플러그인이 합니다.

## 테스트

```bash
python3 -m unittest discover -s teambrain/mcp_server/tests -t .
```
