# handoff

Session continuity for Claude Code. Before you `/clear` or close a session, Claude writes a short handoff of the work in progress. The next session loads it automatically, so you never have to re-explain where you stopped.

## What it does

- **`/handoff` skill**: Claude writes `knowledge/handoffs/CURRENT.md` in your project (goal, done, in progress, next steps, decisions, open questions, uncommitted files, running servers). An older handoff on a different topic is moved to `knowledge/handoffs/archive/`.
- **SessionEnd and PreCompact hooks**: write `knowledge/handoffs/AUTO.md`, a mechanical snapshot of the branch, uncommitted files, last commits and your last prompts, when a session ends and just before Claude Code compacts a long conversation. Secrets (tokens, passwords, keys, credentials in URLs) are redacted.
- **SessionStart hook** (startup, after `/clear` and after compaction): adds `CURRENT.md` and `AUTO.md` to the session's context. Claude says in one line what was in progress and asks before resuming.
  - Handoffs older than 14 days are not loaded, so an old task does not steer a new one.
  - If a handoff was written on a different git branch, Claude is told so before resuming.

## Install

```
/plugin marketplace add kuldeep-jadeja/claude-handoff-plugin
/plugin install handoff@kuldeep-jadeja
```

Restart Claude Code after installing so the hooks load.

## Use

- Say "handoff", "save context" or "I'm going to clear", or run `/handoff [topic]`.
- Then `/clear`. The new session starts with the handoff in context.

## Requirements

- Python 3 on your PATH, as `python3` or `python` (standard library only). On Windows, install Python from python.org and tick "Add python.exe to PATH".
- A git repository is recommended (branch and commit info), but not required.

## Settings

Set these as environment variables (for example in the `env` block of `~/.claude/settings.json`):

| Variable | Default | What it does |
| --- | --- | --- |
| `HANDOFF_MAX_AGE_DAYS` | `14` | Handoffs older than this are not loaded. `0` loads them at any age. |
| `HANDOFF_GIT_EXCLUDE` | `1` | Set to `0` if you want to commit your handoffs. |

## Notes

- Handoffs stay out of commits: the hooks add `/knowledge/handoffs/` to `.git/info/exclude`, which is local to your clone and does not change `.gitignore`. Files you already committed stay tracked.
- The hooks never fail loudly: if anything goes wrong, including Python being missing, they print nothing.

## Changelog

- **1.1.0**: reload the handoff after compaction and snapshot before it; skip handoffs older than 14 days; warn when a handoff is from another branch; keep handoffs out of commits; Windows support (`python` fallback, UTF-8 everywhere).
- **1.0.0**: first release.

## License

MIT
