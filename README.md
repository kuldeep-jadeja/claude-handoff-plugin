# handoff

Session continuity for Claude Code. Before you `/clear` or close a session, Claude writes a short handoff of the work in progress. The next session loads it automatically, so you never have to re-explain where you stopped.

## How it works

```mermaid
sequenceDiagram
    actor You
    participant S1 as Session 1
    participant F as knowledge/handoffs/
    participant S2 as Session 2
    You->>S1: "save context, I'm going to clear"
    S1->>F: handoff skill writes CURRENT.md
    You->>S1: /clear
    S1->>F: SessionEnd hook writes AUTO.md (git state, last prompts)
    F->>S2: SessionStart hook loads CURRENT.md + AUTO.md
    S2->>You: "We were fixing X; next step is Y. Continue?"
```

The same reload happens at startup, after `/clear`, and after Claude Code compacts a long conversation (a snapshot is saved just before compaction too).

## Install

```
/plugin marketplace add kuldeep-jadeja/claude-handoff-plugin
/plugin install handoff@kuldeep-jadeja
```

Restart Claude Code after installing so the hooks load. To update later: `/plugin marketplace update kuldeep-jadeja`, then restart.

## Use

| You do | What happens |
| --- | --- |
| Say "handoff", "save context" or "I'm going to clear", or run `/handoff:handoff [topic]` | Claude writes `knowledge/handoffs/CURRENT.md`. An older handoff on another topic moves to `knowledge/handoffs/archive/`. |
| `/clear`, restart, or a long session gets compacted | The next session starts with the handoff in context. Claude says in one line what was in progress and asks before resuming. |
| `/handoff:resume [name or topic]` | Reload the latest handoff, or an archived one, even if it is older than the age limit. |
| `/handoff:list` | List the current and archived handoffs, newest first, and pick one to load. |

## Example handoff

```markdown
# Handoff: Login timeout bug
Updated: 2026-11-02 18:40 | Branch: fix/login-timeout | Last commit: 3f2a91c fix(auth): compare TTL in ms

## Goal
Sessions expire after 60 seconds instead of 60 minutes.

## Done
- src/auth/session.js: isExpired() now converts the TTL to milliseconds

## Next steps
1. Add a test in tests/session.test.js for a session that is 59 minutes old.

## Decisions (and why)
- Refresh-token logic left alone: the product team is redesigning it.

## State to know
- Uncommitted: tests/session.test.js
- Running: nothing
```

## Safety and token use

- **Secrets**: the skill never writes passwords, keys or tokens, and the automatic snapshot redacts them (tokens, passwords, API keys, private keys, credentials in URLs).
- **Out of commits**: the hooks add `/knowledge/handoffs/` to `.git/info/exclude`, which is local to your clone and does not change `.gitignore`. Files you already committed stay tracked.
- **Stale handoffs**: handoffs older than 14 days are not loaded, so an old task does not steer a new one. `/handoff:resume` still loads them.
- **Other branch**: if a handoff was written on another git branch, Claude says so before resuming.
- **Token cost**: when you saved a handoff during a session, the automatic snapshot leaves out that session's prompts, since the handoff already covers them.

## What it runs, reads and writes

Everything stays on your machine. The plugin makes no network requests and sends no data anywhere.

| Part | Runs | Reads | Writes |
| --- | --- | --- | --- |
| Hooks (`hooks/hooks.json`) | `python3` (or `python`) on `scripts/handoff.py`, standard library only | `knowledge/handoffs/*.md`; the current session transcript that Claude Code passes to the hook (only your last 8 prompts, redacted); read-only `git branch`, `git status`, `git log` and `git rev-parse` | `knowledge/handoffs/AUTO.md`; one line in `.git/info/exclude` |
| `handoff` skill | Claude, with your usual permissions | `git` status and log | `knowledge/handoffs/CURRENT.md`; moves older handoffs to `knowledge/handoffs/archive/` |
| `/handoff:resume`, `/handoff:list` | Claude, with your usual permissions | `knowledge/handoffs/`, `git branch` | Nothing, unless you ask to make an archived handoff the current one |

The hooks add the handoff text to the session's context at startup, after `/clear` and after compaction. They don't change any Claude Code setting or permission.

## Requirements

- Python 3 on your PATH, as `python3` or `python` (standard library only). On Windows, install Python from python.org and tick "Add python.exe to PATH".
- A git repository is recommended (branch and commit info), but not required.

## Settings

Set these as environment variables, for example in the `env` block of `~/.claude/settings.json`:

| Variable | Default | What it does |
| --- | --- | --- |
| `HANDOFF_MAX_AGE_DAYS` | `14` | Handoffs older than this are not loaded at startup. `0` loads them at any age. |
| `HANDOFF_GIT_EXCLUDE` | `1` | Set to `0` if you want to commit your handoffs. |

## Troubleshooting

| Problem | Fix |
| --- | --- |
| The new session does not mention the handoff | Restart Claude Code after installing or updating. Check that `knowledge/handoffs/CURRENT.md` exists in the project you opened, and that it is less than 14 days old (or run `/handoff:resume`). |
| Nothing happens at all | Run `python3 --version` (or `python --version` on Windows). The hooks stay silent when Python is missing. |
| You see the hook output twice | You also have the same hooks in a project or user `settings.json`. Remove one copy. |
| Handoffs show up in `git status` | They were committed before you installed the plugin. Run `git rm -r --cached knowledge/handoffs` once. |
| You want handoffs in your repo | Set `HANDOFF_GIT_EXCLUDE=0` and delete the `/knowledge/handoffs/` line from `.git/info/exclude`. |

## Evals

`evals/` holds cases for `claude plugin eval`: the skill triggers on natural phrasing and keeps the key facts, secrets never reach the handoff, and `/handoff:resume` summarises and waits. See [evals/README.md](evals/README.md).

## Changelog

- **1.2.1**: plugin moved to the repository root; README lists everything the plugin runs, reads and writes.
- **1.2.0**: `/handoff:resume` and `/handoff:list` commands; the automatic snapshot leaves out prompts when a handoff was saved in the same session; eval suite; README with diagram, example and troubleshooting.
- **1.1.0**: reload the handoff after compaction and snapshot before it; skip handoffs older than 14 days; warn when a handoff is from another branch; keep handoffs out of commits; Windows support (`python` fallback, UTF-8 everywhere).
- **1.0.0**: first release.

## License

MIT
