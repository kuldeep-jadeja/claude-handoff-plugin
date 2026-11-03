---
name: list
description: List the session handoffs saved in this project (current and archived, newest first) and load the one the user picks. Use when the user asks which handoffs exist or wants an older one.
---

Show the user the handoffs saved in this project and let them pick one to load.

1. Find the files: `knowledge/handoffs/CURRENT.md`, `knowledge/handoffs/AUTO.md` and `knowledge/handoffs/archive/*.md`. If there are none, say there is no saved handoff in this project and that the user can save one by asking for a handoff. Stop there.
2. For each file, read only the first three lines to get the topic (the `# Handoff:` title; for AUTO.md use "Automatic snapshot") and the `Updated:` (or `Ended:`) time and `Branch:`.
3. Show a numbered list, newest first, at most 20 rows, one per line: `<n>. <topic> | <updated> | <branch> | <file>`. Mark CURRENT.md as "(current)". If there are more than 20, say how many were left out.
4. Ask which one to load.
5. When the user picks one:
   - Read the whole file and continue exactly as `/handoff:resume` does: summarise what was in progress and the next step, warn about another branch or an old date, and ask before starting work.
   - Only if the user asks to make it the current handoff: first move the existing `CURRENT.md` to `knowledge/handoffs/archive/<YYYY-MM-DD-HHMM>-<slug>.md` (as the `handoff` skill does), then copy the chosen file to `knowledge/handoffs/CURRENT.md`. Never delete an archived handoff.
