---
type: llm
---

The reply should summarise a saved handoff and ask before doing anything.

PASS if the reply contains all four:
1. The topic: the CSV export timezone bug (dates off by one day).
2. The next step: adding a test for an Asia/Kolkata user in tests/export.test.js.
3. The open question for the product team (local date or UTC).
4. A question asking the user whether to continue.

Repeating what the handoff lists as already done (for example that src/export/csv.js now uses toISOString) is part of a summary and is fine.

FAIL if any of the four is missing, or if the reply says it changed files or ran commands itself in this session.
