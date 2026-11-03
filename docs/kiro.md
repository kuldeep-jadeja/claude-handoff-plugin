# Handoff for Kiro

Kiro gets the same skills and hooks as the other tools, installed by a script. Kiro hooks have to point at the script by its full path, which a one-click power can't do, so the installer writes them for you.

## Install

macOS / Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/kuldeep-jadeja/claude-handoff-plugin/main/kiro/install.sh | bash
```

Windows (PowerShell):

```powershell
irm https://raw.githubusercontent.com/kuldeep-jadeja/claude-handoff-plugin/main/kiro/install.ps1 | iex
```

That writes:

| File | What it is |
| :-- | :-- |
| `~/.kiro/handoff/handoff.py` | The hook script (Python 3, standard library only). |
| `~/.kiro/skills/handoff/`, `handoff-resume/`, `handoff-list/` | The skills, for the IDE and the CLI. |
| `~/.kiro/hooks/handoff.json` | Global hooks, which the Kiro CLI loads in every project. |

**Kiro IDE:** the IDE reads hooks from the project's `.kiro/hooks/`. From each project folder where you want the handoff loaded automatically, run:

```bash
curl -fsSL https://raw.githubusercontent.com/kuldeep-jadeja/claude-handoff-plugin/main/kiro/install.sh | bash -s -- --project
```

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/kuldeep-jadeja/claude-handoff-plugin/main/kiro/install.ps1))) -Project
```

This adds `.kiro/hooks/handoff.json` to the project. Commit it if your team uses the handoff too, or leave it untracked. When global and project hooks both run, the script still loads the handoff only once per session.

From a clone of this repository, `bash kiro/install.sh` uses the local files instead of downloading them.

**Update:** run the installer again. **Remove:** `bash kiro/install.sh --uninstall` (PowerShell: `-Uninstall`), from a project folder to also remove its `.kiro/hooks/handoff.json`. Saved handoffs in `knowledge/handoffs/` stay.

## What you get

| Component | What it does |
| :-- | :-- |
| `/handoff` skill | Saves `knowledge/handoffs/CURRENT.md`. Also runs when you say "handoff", "save context" or "I'm going to clear". |
| `/handoff-resume` skill | Reloads the latest or an archived handoff, warns about another branch, and asks before working. |
| `/handoff-list` skill | Lists handoffs, newest first, and loads the one you pick. |
| `SessionStart` hook | Adds the handoff to the context of each new session. |
| `UserPromptSubmit` hook | Remembers your prompt, redacted, for the automatic snapshot. Prints nothing, so it adds nothing to the prompt. |
| `Stop` hook | Writes the automatic snapshot `knowledge/handoffs/AUTO.md` when the agent finishes. |

Hooks run `python3 -I ~/.kiro/handoff/handoff.py --client kiro start|prompt|stop`. The prompts for the snapshot are kept in a small state file in your temp folder (`handoff-state/`), never in the project.

## Differences from Claude Code

- Kiro has no compaction or `/clear` events, so the handoff is loaded when a new session starts.
- The automatic snapshot is refreshed after every agent turn, not once at the end.
- Kiro skills are not grouped under a plugin name, so they are called `/handoff-resume` and `/handoff-list` (`/handoff:resume` and `/handoff:list` in Claude Code and Antigravity).

## Tested

Kiro IDE 1.0.337 on Linux (2026-11-03): after the installer, `/handoff`, `/handoff-resume` and `/handoff-list` appear in the chat's slash menu.

Kiro CLI 2.37.1: not run end to end yet (the test account had no model access). The installer and hook script were checked with simulated Kiro hook input:

| Check | Result |
| :-- | :-- |
| `install.sh --project` writes the skills, the script, global and project hooks | ✅ |
| `start` prints the handoff; a second `start` in the same session prints nothing | ✅ |
| `prompt` prints nothing and stores the prompt with the token redacted | ✅ |
| `stop` writes `AUTO.md` and adds `/knowledge/handoffs/` to `.git/info/exclude` | ✅ |
