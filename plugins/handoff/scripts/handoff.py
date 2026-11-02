#!/usr/bin/env python3
"""Session continuity hooks for the handoff plugin.

  handoff.py end         SessionEnd: write knowledge/handoffs/AUTO.md, a mechanical
                         snapshot (branch, git state, last prompts) of the session.
  handoff.py precompact  PreCompact: the same snapshot, taken just before Claude Code
                         compacts the conversation.
  handoff.py start       SessionStart (startup|clear|compact): print CURRENT.md and
                         AUTO.md so they are added to the session's context.

Environment (all optional):
  HANDOFF_MAX_AGE_DAYS   handoffs older than this are not loaded (default 14).
  HANDOFF_GIT_EXCLUDE    set to 0 to stop adding knowledge/handoffs/ to .git/info/exclude.

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
REL_DIR = "knowledge/handoffs"
DIR = os.path.join(ROOT, *REL_DIR.split("/"))
CURRENT = os.path.join(DIR, "CURRENT.md")
AUTO = os.path.join(DIR, "AUTO.md")
TAIL_BYTES = 8 * 1024 * 1024
MAX_PROMPTS = 8
MAX_BODY = 6000
EXCLUDE_LINE = "/" + REL_DIR + "/"


def env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


MAX_AGE_DAYS = env_int("HANDOFF_MAX_AGE_DAYS", 14)

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
        out = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=3,
        )
        return out.stdout.rstrip() if out.returncode == 0 else ""
    except Exception:
        return ""


def read_input():
    """The hook's JSON input from stdin ({} when run by hand)."""
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return {}
        return json.load(sys.stdin)
    except Exception:
        return {}


def ensure_git_exclude():
    """Keep handoffs out of commits: add the folder to .git/info/exclude (local only)."""
    if os.environ.get("HANDOFF_GIT_EXCLUDE", "1") == "0":
        return
    try:
        path = git("rev-parse", "--git-path", "info/exclude")
        if not path:
            return  # not a git repository
        if not os.path.isabs(path):
            path = os.path.join(ROOT, path)
        try:
            with open(path, encoding="utf-8") as f:
                existing = f.read()
        except OSError:
            existing = ""
        if any(line.strip() in (EXCLUDE_LINE, REL_DIR, REL_DIR + "/") for line in existing.splitlines()):
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write("# handoff plugin: session handoffs stay local\n" + EXCLUDE_LINE + "\n")
    except Exception:
        pass


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


def snapshot(reason_override=None):
    data = read_input()
    prompts = last_prompts(data.get("transcript_path") or "")
    if not prompts:
        return  # nothing worth recording (e.g. a session that only ran /model)
    reason = reason_override or data.get("reason", "?")
    if reason_override == "compact" and data.get("trigger"):
        reason = f"compact ({data['trigger']})"
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    status = git("status", "--short") or "clean"
    lines = [
        "# Auto snapshot (last session end)",
        f"Ended: {now} | Reason: {reason} | Session: {data.get('session_id', '?')}",
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
    ensure_git_exclude()
    with open(AUTO, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def handoff_branch(body):
    m = re.search(r"\bBranch:\s*([^\s|]+)", body)
    return m.group(1) if m else ""


def start():
    data = read_input()
    source = data.get("source", "startup")
    if os.path.isdir(DIR):
        ensure_git_exclude()
    branch = git("branch", "--show-current")
    parts, skipped = [], []
    for path, label in ((CURRENT, "Handoff written by Claude"), (AUTO, "Automatic snapshot")):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                body = f.read().strip()
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        if not body:
            continue
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
        days = (datetime.datetime.now() - datetime.datetime.fromtimestamp(mtime)).days
        if MAX_AGE_DAYS > 0 and days > MAX_AGE_DAYS:
            skipped.append(f"{rel} ({days} days old)")
            continue
        when = "today" if days == 0 else f"{days} day(s) ago"
        notes = []
        theirs = handoff_branch(body)
        if branch and theirs and theirs != branch:
            notes.append(f"written on branch {theirs}, current branch is {branch}")
        if len(body) > MAX_BODY:
            body = body[:MAX_BODY] + f"\n\n[truncated; read {rel} for the rest]"
        header = f"### {label} ({rel}, updated {when}"
        header += f"; NOTE: {'; '.join(notes)})" if notes else ")"
        parts.append(f"{header}\n\n{body}")
    if not parts:
        if skipped and source != "compact":
            print(
                "Session continuity: older handoffs were not loaded because they are stale: "
                + ", ".join(skipped)
                + ". Mention this only if the user asks about earlier work."
            )
        return
    if source == "compact":
        intro = (
            "Session continuity: the conversation was just compacted. The latest handoff follows "
            "for reference; the compaction summary is more recent where they differ."
        )
    else:
        intro = (
            "Session continuity: previous work context follows. If relevant to the user's first message, "
            "say in one line what was in progress and confirm before resuming. Ignore it if stale or unrelated. "
            "If a NOTE says it was written on another branch, mention that before resuming."
        )
    print(intro + "\n\n" + "\n\n".join(parts))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "start":
        start()
    elif mode == "end":
        snapshot()
    elif mode == "precompact":
        snapshot("compact")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
