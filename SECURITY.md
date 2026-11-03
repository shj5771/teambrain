# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems.
Use GitHub's private vulnerability reporting ("Security" tab → "Report a vulnerability") on this repository.

## Known limitation: channel-type classification

TeamBrain only writes conversations from **fully public channels** to the shared team store.
DMs, group DMs, private channels and unknown values are never stored (fail-closed).
See [`docs/visibility-rule.md`](docs/visibility-rule.md).

TeamBrain decides this from the `chat_type` value that the Hermes Mattermost adapter passes in.
That adapter currently maps **unrecognized** Mattermost channel-type codes to `"channel"` (fail-open).
If Mattermost ever introduced a new private channel type, the adapter could label it as public before TeamBrain sees it,
and TeamBrain could not detect that.

Today Mattermost only uses the four known types (`O`, `P`, `D`, `G`), so this does not happen in practice,
but keep it in mind when upgrading Mattermost or Hermes.
