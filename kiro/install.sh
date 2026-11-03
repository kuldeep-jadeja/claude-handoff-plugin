#!/usr/bin/env bash
# Install the handoff skills and hooks for Kiro (macOS and Linux).
#
#   curl -fsSL https://raw.githubusercontent.com/kuldeep-jadeja/claude-handoff-plugin/main/kiro/install.sh | bash
#   curl -fsSL .../kiro/install.sh | bash -s -- --project     also add the hooks to this project
#   bash kiro/install.sh --uninstall                            remove everything it installed
#
# Writes only these files:
#   ~/.kiro/handoff/handoff.py                 the hook script (Python 3, standard library only)
#   ~/.kiro/skills/handoff{,-resume,-list}/    the three skills
#   ~/.kiro/hooks/handoff.json                 global hooks (Kiro CLI)
#   ./.kiro/hooks/handoff.json                 project hooks, only with --project (Kiro IDE)
set -euo pipefail

RAW="${HANDOFF_RAW:-https://raw.githubusercontent.com/kuldeep-jadeja/claude-handoff-plugin/main}"
KIRO="${KIRO_HOME:-$HOME/.kiro}"
SKILLS="handoff handoff-resume handoff-list"
PROJECT=0
UNINSTALL=0
for arg in "$@"; do
  case "$arg" in
    --project) PROJECT=1 ;;
    --uninstall) UNINSTALL=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

if [ "$UNINSTALL" = 1 ]; then
  rm -rf "$KIRO/handoff"
  for s in $SKILLS; do rm -rf "$KIRO/skills/$s"; done
  rm -f "$KIRO/hooks/handoff.json"
  [ -f .kiro/hooks/handoff.json ] && rm -f .kiro/hooks/handoff.json && echo "Removed .kiro/hooks/handoff.json from this project."
  echo "Handoff removed from $KIRO. Saved handoffs in knowledge/handoffs/ were left alone."
  exit 0
fi

PY=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 6))' 2>/dev/null; then
    PY="$candidate"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Python 3 is needed for the hooks. Install it, then run this again." >&2
  exit 1
fi

# Use the files next to this script when run from a clone, otherwise download them.
HERE=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
  HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  [ -f "$HERE/scripts/handoff.py" ] || HERE=""
fi
fetch() { # fetch <repo path> <destination>
  mkdir -p "$(dirname "$2")"
  if [ -n "$HERE" ]; then cp "$HERE/$1" "$2"; else curl -fsSL "$RAW/$1" -o "$2"; fi
}

fetch scripts/handoff.py "$KIRO/handoff/handoff.py"
for s in $SKILLS; do fetch "kiro/skills/$s/SKILL.md" "$KIRO/skills/$s/SKILL.md"; done

write_hooks() { # write_hooks <destination>
  "$PY" - "$PY" "$KIRO/handoff/handoff.py" "$1" <<'PYEOF'
import json, os, sys
py, script, dest = sys.argv[1:4]
def cmd(mode):
    return f'{py} -I "{script}" --client kiro {mode}'
hooks = {
    "version": "v1",
    "hooks": [
        {"name": "handoff-load", "description": "Load the last handoff into the new session",
         "trigger": "SessionStart", "action": {"type": "command", "command": cmd("start")}, "timeout": 10},
        {"name": "handoff-remember-prompt", "description": "Remember the prompt (redacted) for the automatic snapshot",
         "trigger": "UserPromptSubmit", "action": {"type": "command", "command": cmd("prompt")}, "timeout": 10},
        {"name": "handoff-snapshot", "description": "Write knowledge/handoffs/AUTO.md when the agent stops",
         "trigger": "Stop", "action": {"type": "command", "command": cmd("stop")}, "timeout": 10},
    ],
}
os.makedirs(os.path.dirname(dest), exist_ok=True)
with open(dest, "w", encoding="utf-8") as f:
    json.dump(hooks, f, indent=2)
    f.write("\n")
PYEOF
}

write_hooks "$KIRO/hooks/handoff.json"
echo "Installed the handoff skills and hooks in $KIRO."
if [ "$PROJECT" = 1 ]; then
  write_hooks ".kiro/hooks/handoff.json"
  echo "Added .kiro/hooks/handoff.json to $(pwd)."
else
  echo "Kiro IDE: run this again with --project inside each project to add the hooks there."
fi
echo "Restart Kiro or open a new chat. Say \"handoff\" to save, \"resume\" to pick up."
