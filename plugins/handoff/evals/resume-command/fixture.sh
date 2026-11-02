#!/usr/bin/env bash
# A git repo on branch "main" with a handoff written on branch "fix/csv-export".
set -euo pipefail
git init -q -b main .
git -c user.name=eval -c user.email=eval@example.com commit -q --allow-empty -m "init"
mkdir -p knowledge/handoffs
cat > knowledge/handoffs/CURRENT.md <<'MD'
# Handoff: CSV export timezone bug
Updated: 2026-11-01 18:30 | Branch: fix/csv-export | Last commit: a1b2c3d fix(export): use UTC dates

## Goal
Exported CSV dates are off by one day for users east of UTC.

## Done
- src/export/csv.js: format dates with toISOString instead of toLocaleDateString

## Next steps
1. Add a test in tests/export.test.js for a user in Asia/Kolkata.
2. Open the pull request.

## Open questions / blockers
- Waiting on the product team: should the CSV show the user's local date or UTC?
MD
