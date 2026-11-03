# TeamBrain memory provider

Hermes `memory-provider` plugin implementing TeamBrain's "① 팀 공유 지식 레이어"
Every Hermes profile that sets `memory: {provider: teambrain}`
in its own `config.yaml` reads from and writes to one shared store, filtered by
a single MVP visibility rule.

Design rationale, the visibility rule, known limitations, and what's
explicitly out of scope for now: see
`docs/visibility-rule.md`.

## Team wiki

Every few new entries (default 5, `TEAMBRAIN_CURATE_EVERY`; `0` = off), Hermes'
own configured model folds the raw store into curated Markdown topic pages:
decisions, project facts, how-tos — each fact attributed (who / channel / date),
and changed decisions kept under a "변경 이력" (change history) section.

- Pages: `~/.hermes/team_knowledge/wiki/<slug>.md` (plain Markdown, readable by humans)
- `prefetch()` injects matching wiki pages first, then raw conversations
- Bots get two tools: `team_wiki_list`, `team_wiki_read`
- No extra API key: uses Hermes' model. To use a cheaper one only for this:
  ```yaml
  auxiliary:
    teambrain_wiki:
      model: <model id>
  ```

Store location: `~/.hermes/team_knowledge/store.jsonl` by default; set
`TEAMBRAIN_STORE=/path/to/store.jsonl` to move it (the wiki lives next to it).

CLI:

```bash
python3 -m teambrain.memory_provider status        # entries / waiting / pages
python3 -m teambrain.memory_provider list
python3 -m teambrain.memory_provider show <slug>
~/.hermes/hermes-agent/venv/bin/python -m teambrain.memory_provider curate   # curate now
```

## Layout

- `__init__.py` — `TeamBrainMemoryProvider` (the `MemoryProvider` implementation) + `register(ctx)`
- `store.py` — shared JSONL store (schema, read/append, keyword-overlap search)
- `visibility.py` — the one MVP rule (`should_sync`) in its own module
- `wiki.py` — LLM curation of the store into topic pages + wiki search
- `__main__.py` — wiki CLI
- `tests/` — `python3 -m unittest discover -s teambrain/memory_provider/tests -t .` (no Hermes needed)
- `scripts/manual_verify.py` — standalone verification (no pytest required)

## Installing into a Hermes profile

```bash
mkdir -p ~/.hermes/plugins
ln -s /path/to/teambrain/teambrain/memory_provider ~/.hermes/plugins/teambrain
```

Then add to that profile's `~/.hermes/config.yaml`:

```yaml
memory:
  provider: teambrain
```

Restart the gateway (`hermes gateway restart`) for the change to take effect.
