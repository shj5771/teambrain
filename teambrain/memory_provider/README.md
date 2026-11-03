# TeamBrain memory provider

Hermes `memory-provider` plugin implementing TeamBrain's "① 팀 공유 지식 레이어"
Every Hermes profile that sets `memory: {provider: teambrain}`
in its own `config.yaml` reads from and writes to one shared store, filtered by
a single MVP visibility rule.

Design rationale, the visibility rule, known limitations, and what's
explicitly out of scope for now: see
`docs/visibility-rule.md`.

## Layout

- `__init__.py` — `TeamBrainMemoryProvider` (the `MemoryProvider` implementation) + `register(ctx)`
- `store.py` — shared JSONL store (schema, read/append, keyword-overlap search)
- `visibility.py` — the one MVP rule (`should_sync`) in its own module
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
