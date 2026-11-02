#!/usr/bin/env python3
"""Session continuity hooks.

  handoff.py end    SessionEnd: write knowledge/handoffs/AUTO.md, a mechanical
                    snapshot (branch, git state, last prompts) of the session.
  handoff.py start  SessionStart (startup|clear): print CURRENT.md + AUTO.md so
                    they are added to the new session's context.

Must stay fast (SessionEnd hooks get a short timeout) and must never fail
loudly: every error is swallowed.
"""
import datetime
import json
import os
import re
import subprocess
import sys

ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
DIR = os.path.join(ROOT, "knowledge", "handoffs")
CURRENT = os.path.join(DIR, "CURRENT.md")
AUTO = os.path.join(DIR, "AUTO.md")
TAIL_BYTES = 8 * 1024 * 1024
MAX_PROMPTS = 8

SECRET_PATTERNS = [
    (re.compile(r"(\w+://)[^/\s:@]+:[^@\s]+@"), r"\1***:***@"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "[PRIVATE KEY]"),
    (re.compile(r"\b(ssh-(rsa|ed25519)|ecdsa-sha2-\S+) \S+"), "[SSH KEY]"),
    (re.compile(r"\b(rzp_(live|test)_|sk-|pk_|sk_|ghp_|gho_|xox[bp]-)[A-Za-z0-9_-]{6,}"), "[KEY]"),
    (re.compile(r"(?i)\b(\w*(?:password|passwd|secret|token|api[_ ]?key)\w*)\s*[:=]\s*\S+"), r"\1=[REDACTED]"),
    # No "/" in the class so file paths survive.
    (re.compile(r"\b[A-Za-z0-9+_=-]{40,}"), "[REDACTED]"),
]


def redact(text):
    for pattern, repl in SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def git(*args):
    try:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=3)
        return out.stdout.rstrip()
    except Exception:
        return ""


def last_prompts(transcript):
    """User prompts from the tail of the transcript, oldest first."""
    try:
        size = os.path.getsize(transcript)
        with open(transcript, "rb") as f:
            f.seek(max(0, size - TAIL_BYTES))
            lines = f.read().decode("utf-8", "ignore").splitlines()
    except Exception:
        return []
    prompts = []
    for line in lines:
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("type") != "user" or d.get("isMeta") or d.get("isSidechain"):
            continue
        content = d.get("message", {}).get("content")
        if isinstance(content, list):
            content = " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
        if not isinstance(content, str):
            continue
        text = re.sub(r"<pasted_content.*?</pasted_content>", "[paste]", content, flags=re.S).strip()
        if not text or text.startswith("<") or "continued from a previous conversation" in text:
            continue
        prompts.append(redact(" ".join(text.split()))[:240])
    return prompts[-MAX_PROMPTS:]


def end():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    prompts = last_prompts(data.get("transcript_path") or "")
    if not prompts:
        return  # nothing worth recording (e.g. a session that only ran /model)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    status = git("status", "--short") or "clean"
    lines = [
        "# Auto snapshot (last session end)",
        f"Ended: {now} | Reason: {data.get('reason', '?')} | Session: {data.get('session_id', '?')}",
        f"Branch: {git('branch', '--show-current')}",
        "",
        "## Uncommitted",
        "```",
        "\n".join(status.splitlines()[:30]),
        "```",
        "",
        "## Last commits",
        "```",
        git("log", "--oneline", "-5"),
        "```",
        "",
        "## Last prompts in that session",
        *[f"- {p}" for p in prompts],
        "",
    ]
    os.makedirs(DIR, exist_ok=True)
    with open(AUTO, "w") as f:
        f.write("\n".join(lines))


def start():
    parts = []
    for path, label in ((CURRENT, "Handoff written by Claude"), (AUTO, "Automatic snapshot")):
        try:
            with open(path) as f:
                body = f.read().strip()
        except OSError:
            continue
        age = datetime.datetime.now() - datetime.datetime.fromtimestamp(os.path.getmtime(path))
        days = age.days
        when = "today" if days == 0 else f"{days} day(s) ago"
        parts.append(f"### {label} ({os.path.relpath(path, ROOT)}, updated {when})\n\n{body[:6000]}")
    if not parts:
        return
    print(
        "Session continuity: previous work context follows. If relevant to the user's first message, "
        "say in one line what was in progress and confirm before resuming. Ignore it if stale or unrelated.\n\n"
        + "\n\n".join(parts)
    )


if __name__ == "__main__":
    try:
        {"end": end, "start": start}[sys.argv[1]]()
    except Exception:
        pass
