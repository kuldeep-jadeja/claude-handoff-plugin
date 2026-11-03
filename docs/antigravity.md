# Handoff for Google Antigravity

The repository is also an Antigravity plugin. Its manifest is `.antigravity-plugin/plugin.json`, which Antigravity reads ahead of the Claude Code files in the same repository.

## Install

Antigravity CLI:

```bash
agy plugin install https://github.com/kuldeep-jadeja/claude-handoff-plugin
agy plugin list            # shows handoff with 3 skills (handoff, list, resume) and 1 hook
```

Antigravity IDE or App without the CLI: clone the repository into the global plugins folder, which every Antigravity surface reads:

```bash
git clone https://github.com/kuldeep-jadeja/claude-handoff-plugin ~/.gemini/config/plugins/handoff
```

For one project only, clone it into `.agents/plugins/handoff` inside that project instead.

Plugins and hooks need a recent Antigravity release: the CLI from 1.4, and an IDE or App from the 2.x line. Older IDE builds (1.x, such as 1.23) load neither, and read skills only from `~/.gemini/antigravity/skills/`. There, copy the [standalone skill](../README.md#-just-the-skill-any-tool) to `~/.gemini/antigravity/skills/handoff/SKILL.md`, or update the IDE.

**Update:** `agy plugin uninstall handoff` then install again, or `git pull` in the cloned folder.
**Remove:** `agy plugin uninstall handoff`, or delete the folder. Saved handoffs in `knowledge/handoffs/` stay.

## What you get

| Component | File | What it does |
| :-- | :-- | :-- |
| `/handoff:handoff` skill | `skills/handoff/SKILL.md` | Saves `knowledge/handoffs/CURRENT.md`. Also runs when you say "handoff", "save context" or "I'm going to clear". |
| `/handoff:resume` skill | `skills/resume/SKILL.md` | Reloads the latest or an archived handoff, warns about another branch, and asks before working. Also runs when you say "resume". |
| `/handoff:list` skill | `skills/list/SKILL.md` | Lists handoffs, newest first, and loads the one you pick. |
| `SessionStart` hook | `hooks.json` | Adds the handoff to the context of each new conversation (as a system message). |
| `Stop` hook | `hooks.json` | Writes the automatic snapshot `knowledge/handoffs/AUTO.md` when the agent finishes. |

Hooks run `python3 ./scripts/handoff.py --client antigravity start|stop` from the plugin folder (falling back to `python`). The script finds your project through the `workspacePaths` Antigravity passes to the hook, and reads your prompts from the conversation's `transcript.jsonl`. It prints JSON, as Antigravity requires, and an empty `{}` when there is nothing to add.

## Differences from Claude Code

- Antigravity has no compaction or `/clear` events, so the handoff is loaded when a new conversation starts.
- The automatic snapshot is written when the agent stops, so it is refreshed after every turn rather than once at the end.
- The skills are the same files, with the same names, as in Claude Code.

## Tested

With Antigravity CLI 1.4.12 on Linux (2026-11-03), in a fresh git repository:

| Check | Result |
| :-- | :-- |
| `agy plugin validate --strict .` | passes |
| Saying "I'm going to clear the session now, save a handoff" writes `CURRENT.md` in the template, without the password from the prompt | ✅ |
| A new conversation has the handoff in context (asked without reading files, it quotes the title) | ✅ |
| `Stop` writes `AUTO.md` with the real prompt; `/knowledge/handoffs/` is added to `.git/info/exclude` | ✅ |
| `/handoff:resume` on another branch gives the next step, the branch warning, and asks before working | ✅ |
| `/handoff:list` lists `CURRENT.md` and `AUTO.md`, newest first | ✅ |
