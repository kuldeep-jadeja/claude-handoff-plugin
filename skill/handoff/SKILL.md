---
name: handoff
description: Save the current work to knowledge/handoffs/CURRENT.md so a fresh session (after /clear or a restart) can pick up where this one stopped, and reload it later. Use when the user says "handoff", "save context", "I'm going to clear", "wrap up", when a task finishes or the topic changes (save); and when the user says "resume", "where did we leave off", "continue from last time" or "load the handoff" (resume). Also lists saved handoffs.
argument-hint: "[topic] | resume [name or topic] | list | setup"
---

# Handoff (standalone skill)

Session continuity without the plugin, for Claude Code, Kiro, Antigravity or any agent that reads `SKILL.md` skills. This skill writes and reads the same files as the `handoff` plugin, so a project can switch between the two at any time.

All paths are relative to the project root (the git top level when there is one, otherwise the working directory):

- `knowledge/handoffs/CURRENT.md`: the latest handoff.
- `knowledge/handoffs/archive/`: older handoffs, never deleted.
- `knowledge/handoffs/AUTO.md`: written only by the plugin's hooks. Read it when it exists, never write it.

## Pick the mode

Argument: $ARGUMENTS

- Starts with `resume` (or the user asks to resume / continue / see where they left off): **Resume**, using the rest of the argument as the name or topic.
- `list` (or the user asks which handoffs exist): **List**.
- `setup` (or the user asks for handoffs to load automatically): **Setup**.
- Anything else, including no argument: **Save**, using the argument as the topic.

## Save

1. If `knowledge/handoffs/CURRENT.md` exists and covers a different topic or an older, finished task, move it to `knowledge/handoffs/archive/<YYYY-MM-DD-HHMM>-<slug>.md` first, where the time is its `Updated:` time and the slug comes from its title. If it is the same ongoing task, update it in place.
2. Collect facts: `git branch --show-current`, `git status --short`, `git log --oneline -5`, any dev servers or background runs still alive (ports, test shells), and what this conversation decided. Outside a git repository, write `Branch: none` and skip the git facts.
3. Write `knowledge/handoffs/CURRENT.md` using the template below. Keep it under 60 lines. Use specific file paths, commands and decisions, not narrative.
4. Never write secrets: no connection strings with passwords, API keys, tokens, or private keys. Refer to them by env var name, even if the user typed the value in this conversation.
5. Keep handoffs out of commits: inside a git repository, run `git rev-parse --git-path info/exclude` to find the exclude file. If it has no `/knowledge/handoffs/` line, append `# handoff: session handoffs stay local` and `/knowledge/handoffs/` on two new lines. This file is local to the clone; never touch `.gitignore`. Skip this step if the user said they want handoffs committed. Some tools (Claude Code among them) ask before writing inside `.git/`; if the write is refused, carry on and add one line to the reply: `Tip: add /knowledge/handoffs/ to .git/info/exclude to keep handoffs out of commits.`
6. Reply with one line: `Handoff saved to knowledge/handoffs/CURRENT.md. Safe to /clear.` If `CURRENT.md` did not exist before this save and Setup has not been done (no `## Session handoff` section in the files listed under Setup), add: `Next session, say "resume" (or run /handoff resume) to pick up from here.`

### Template
```markdown
# Handoff: <topic>
Updated: <YYYY-MM-DD HH:MM> | Branch: <branch> | Last commit: <hash subject>

## Goal
<1-2 lines: what the user is trying to achieve and why>

## Done
- <finished item, with file paths / commits>

## In progress
- <what was being changed when we stopped; exact file and function>

## Next steps
1. <the very next action a fresh session should take>
2. ...

## Decisions (and why)
- <decision>: <reason / user's words>

## Open questions / blockers
- <waiting on user, credentials, approval, etc.>

## State to know
- Uncommitted: <files or "none">
- Running: <servers, ports, background tests or "nothing">
- Tests: <which ran, results, known failures>
```

## Resume

1. Find the handoff:
   - No name or topic: read `knowledge/handoffs/CURRENT.md`, and `knowledge/handoffs/AUTO.md` if it exists, however old they are.
   - With a name or topic: look in `knowledge/handoffs/archive/` for a file whose name or `# Handoff:` title contains it (ignore case). If several match, list them and ask which one. If none match, say so and show the five newest archive files.
   - Nothing found at all: say there is no saved handoff in this project and that the user can save one by saying "handoff". Stop there.
2. Check the context: run `git branch --show-current` and compare it with the `Branch:` in the handoff header. Work out how old the handoff is from its `Updated:` line.
3. Reply in at most five short lines:
   - what was in progress (the handoff's topic and goal),
   - the very next step from "Next steps",
   - any open question or blocker it lists,
   - a warning if it was written on another branch, or is more than 14 days old,
   - then ask: "Continue from here?"
4. Do not start the work, edit files or run anything else until the user confirms.

## List

1. Find `knowledge/handoffs/CURRENT.md`, `knowledge/handoffs/AUTO.md` and `knowledge/handoffs/archive/*.md`. If there are none, say there is no saved handoff in this project and stop.
2. For each file, read only the first three lines: the topic (the `# Handoff:` title; for AUTO.md use "Automatic snapshot"), the `Updated:` (or `Ended:`) time and the `Branch:`.
3. Show a numbered list, newest first, at most 20 rows: `<n>. <topic> | <updated> | <branch> | <file>`. Mark CURRENT.md as "(current)". If there are more than 20, say how many were left out.
4. Ask which one to load. When the user picks one, read the whole file and follow Resume from step 2.
5. Only if the user asks to make the chosen file the current handoff: archive the existing `CURRENT.md` as in Save step 1, then copy the chosen file to `knowledge/handoffs/CURRENT.md`. Never delete an archived handoff.

## Setup

Without the plugin there are no hooks, so a new session does not see the handoff unless something tells the agent to look. Setup writes that instruction into the file your tool loads into every session. Use the row for the tool you are running in:

| Tool | This project | Every project | How to write it |
| :-- | :-- | :-- | :-- |
| Claude Code | `./CLAUDE.md` | `~/.claude/CLAUDE.md` | Append the block. |
| Kiro | `.kiro/steering/handoff.md` | `~/.kiro/steering/handoff.md` | New file: the block, after a frontmatter of `inclusion: always`. |
| Antigravity | `.agents/rules/handoff.md` | `~/.gemini/config/rules/handoff.md` | New file: the block, after a frontmatter of `trigger: always_on`. Without it the rule is ignored. |
| Any other tool | `./AGENTS.md` | (ask the user) | Append the block. |

1. If the file for this tool, in either scope, already contains a `## Session handoff` section, say which one and stop.
2. In one message, show the block below and ask where it should go: this project only or every project, naming the two files from the table. Do not choose for the user.
3. When the user names a place, that is their confirmation: write the block there as the table says, creating the file and its folders if needed. If they decline, change nothing.

```markdown
## Session handoff
If `knowledge/handoffs/CURRENT.md` exists and was updated in the last 14 days, read it before replying to my first message. If it relates to that message, say in one line what was in progress (and if its `Branch:` differs from the current git branch) and ask before resuming. Otherwise ignore it. When I say "handoff" or "I'm going to clear", use the handoff skill.
```

4. Reply with one line saying which file was updated and that it takes effect in the next session.
