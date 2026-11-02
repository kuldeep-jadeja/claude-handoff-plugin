# handoff

Session continuity for Claude Code. Before you `/clear` or close a session, Claude writes a short handoff of the work in progress. The next session loads it automatically, so you never have to re-explain where you stopped.

## What it does

- **`/handoff` skill**: Claude writes `knowledge/handoffs/CURRENT.md` in your project (goal, done, in progress, next steps, decisions, open questions, uncommitted files, running servers). An older handoff on a different topic is moved to `knowledge/handoffs/archive/`.
- **SessionEnd hook**: writes `knowledge/handoffs/AUTO.md`, a mechanical snapshot of the branch, uncommitted files, last commits and your last prompts. Secrets (tokens, passwords, keys, credentials in URLs) are redacted.
- **SessionStart hook** (startup and after `/clear`): adds `CURRENT.md` and `AUTO.md` to the new session's context. Claude says in one line what was in progress and asks before resuming.

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

- `python3` on your PATH (used by the hooks; standard library only).
- A git repository is recommended (branch and commit info), but not required.

## Notes

- Handoffs are plain Markdown in your project. Add `knowledge/handoffs/` to `.gitignore` if you do not want them committed.
- The hooks never fail loudly: if anything goes wrong they print nothing.

## License

MIT
