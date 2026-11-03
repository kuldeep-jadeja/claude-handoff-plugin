---
name: resume
description: Reload the latest session handoff (knowledge/handoffs/CURRENT.md), or an archived one, and get ready to continue the work it describes. Use when the user says "resume", "where did we leave off", "continue from last time" or "load the handoff".
argument-hint: "[archive file name or topic]"
---

Reload a saved handoff and get ready to continue the work it describes.

Argument (whatever the user typed after the command, may be empty): $ARGUMENTS

1. Find the handoff:
   - No argument: read `knowledge/handoffs/CURRENT.md` and `knowledge/handoffs/AUTO.md` (whichever exist), however old they are.
   - With an argument: look in `knowledge/handoffs/archive/` for a file whose name or `# Handoff:` title contains the argument (ignore case). If several match, list them and ask which one. If none match, say so and show the five newest archive files.
   - Nothing found at all: say there is no saved handoff in this project and that the user can save one by asking for a handoff (the `handoff` skill). Stop there.
2. Check the context: run `git branch --show-current` and compare it with the `Branch:` in the handoff header. Note how old the handoff is from its `Updated:` line.
3. Reply in at most five short lines:
   - what was in progress (the handoff's topic and goal),
   - the very next step from "Next steps",
   - any open question or blocker it lists,
   - a warning if it was written on another branch, or is more than 14 days old,
   - then ask: "Continue from here?"
4. Do not start the work, edit files or run anything else until the user confirms.
