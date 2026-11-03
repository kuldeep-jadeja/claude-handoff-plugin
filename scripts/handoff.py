#!/usr/bin/env python3
"""Session continuity hooks for the handoff plugin (Claude Code, Kiro, Antigravity).

  handoff.py [--client NAME] start       SessionStart: print CURRENT.md and AUTO.md so
                                         they are added to the session's context.
  handoff.py end                         Claude Code SessionEnd: write
                                         knowledge/handoffs/AUTO.md, a mechanical snapshot
                                         (branch, git state, last prompts) of the session.
  handoff.py precompact                  Claude Code PreCompact: the same snapshot, taken
                                         just before the conversation is compacted.
  handoff.py --client kiro prompt        Kiro UserPromptSubmit: remember the prompt
                                         (redacted) for the snapshot. Prints nothing.
  handoff.py --client NAME stop          Kiro and Antigravity Stop / SessionEnd: write
                                         the AUTO.md snapshot.

NAME is claude (default), kiro or antigravity. It selects where the project root
comes from, where the session's prompts come from, and the output format
(Antigravity wants JSON on stdout; the others take plain text).

Environment (all optional):
  HANDOFF_MAX_AGE_DAYS   handoffs older than this are not loaded (default 14).
  HANDOFF_GIT_EXCLUDE    set to 0 to stop adding knowledge/handoffs/ to .git/info/exclude.

Must stay fast (hooks get short timeouts) and must never fail loudly: every
error is swallowed.
"""
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

REL_DIR = "knowledge/handoffs"
TAIL_BYTES = 8 * 1024 * 1024
MAX_PROMPTS = 8
MAX_BODY = 6000
EXCLUDE_LINE = "/" + REL_DIR + "/"
CLIENTS = ("claude", "kiro", "antigravity")
RESUME_COMMAND = {
    "claude": "/handoff:resume",
    "kiro": "/handoff-resume",
    "antigravity": "/handoff:resume",
}

CLIENT = "claude"
ROOT = DIR = CURRENT = AUTO = ""


def set_root(root):
    global ROOT, DIR, CURRENT, AUTO
    ROOT = root
    DIR = os.path.join(ROOT, *REL_DIR.split("/"))
    CURRENT = os.path.join(DIR, "CURRENT.md")
    AUTO = os.path.join(DIR, "AUTO.md")


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
    (re.compile(r"(?i)\b(\w*(?:password|passwd|secret|token|api[_ ]?key)\w*)\s+(is|was)\s+\S+"), r"\1 \2 [REDACTED]"),
    # No "/" in the class so file paths survive.
    (re.compile(r"\b[A-Za-z0-9+_=-]{40,}"), "[REDACTED]"),
]


def redact(text):
    for pattern, repl in SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def clean_prompt(text):
    """One redacted line of at most 240 characters, or "" when not a real prompt."""
    if not isinstance(text, str):
        return ""
    text = re.sub(r"<pasted_content.*?</pasted_content>", "[paste]", text, flags=re.S).strip()
    if not text or text.startswith("<") or "continued from a previous conversation" in text:
        return ""
    return redact(" ".join(text.split()))[:240]


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
        data = json.load(sys.stdin)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def project_root(data):
    """The project the session works in, or "" when it can't be told."""
    if CLIENT == "antigravity":
        # Antigravity runs plugin hooks inside the plugin's own folder, so the
        # working directory is no use here.
        paths = data.get("workspacePaths") or []
        return paths[0] if paths and isinstance(paths[0], str) else ""
    if CLIENT == "kiro" and isinstance(data.get("cwd"), str) and data["cwd"]:
        return data["cwd"]
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def session_id(data):
    return str(data.get("session_id") or data.get("conversationId") or data.get("sessionId") or "?")


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


def tail_lines(path):
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(max(0, size - TAIL_BYTES))
            return f.read().decode("utf-8", "ignore").splitlines()
    except Exception:
        return []


# --- Claude Code transcript ---------------------------------------------------

def claude_prompts(transcript):
    """User prompts from the tail of a Claude Code transcript, oldest first."""
    prompts = []
    for line in tail_lines(transcript):
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("type") != "user" or d.get("isMeta") or d.get("isSidechain"):
            continue
        content = d.get("message", {}).get("content")
        if isinstance(content, list):
            content = " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
        text = clean_prompt(content)
        if text:
            prompts.append(text)
    return prompts[-MAX_PROMPTS:]


def claude_started_at(transcript):
    """Epoch seconds of the first timestamped entry in the transcript, or None."""
    try:
        with open(transcript, "rb") as f:
            head = f.read(256 * 1024).decode("utf-8", "ignore")
    except Exception:
        return None
    for line in head.splitlines():
        try:
            ts = json.loads(line).get("timestamp")
        except Exception:
            continue
        if isinstance(ts, str) and ts:
            try:
                return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
            except ValueError:
                continue
    return None


# --- Antigravity transcript (best effort: the format is not documented) ------

def _text_of(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("text", "content", "message", "userMessage"):
            if key in value:
                return _text_of(value[key])
    if isinstance(value, list):
        return " ".join(t for t in (_text_of(v) for v in value) if t)
    return ""


USER_REQUEST = re.compile(r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", re.S)


def antigravity_prompts(transcript):
    """User prompts from an Antigravity transcript.jsonl, oldest first.

    Seen in Antigravity CLI 1.4: one JSON object per step; a prompt is
    {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content":
    "<USER_REQUEST>...</USER_REQUEST><ADDITIONAL_METADATA>..."}.
    Other shapes are tried in case the format changes.
    """
    prompts = []
    for line in tail_lines(transcript):
        try:
            d = json.loads(line)
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        text = ""
        if str(d.get("type", "")).upper() == "USER_INPUT":
            if d.get("source") not in (None, "USER_EXPLICIT"):
                continue  # input the system added, not something the user typed
            text = _text_of(d.get("content"))
        else:
            for key in ("userMessage", "user_message", "userInput", "user_input"):
                if key in d:
                    text = _text_of(d[key])
                    break
            if not text and str(d.get("role", "")).lower() == "user":
                text = _text_of(d.get("content"))
        m = USER_REQUEST.search(text or "")
        if m:
            text = m.group(1)
        text = clean_prompt(text)
        if text:
            prompts.append(text)
    return prompts[-MAX_PROMPTS:]


# --- Per-session state for Kiro and Antigravity -------------------------------
# Kept outside the project, so opening a project never creates files in it.

def state_path(data):
    key = hashlib.sha1((ROOT + "\0" + session_id(data)).encode("utf-8", "replace")).hexdigest()[:20]
    return os.path.join(tempfile.gettempdir(), "handoff-state", key + ".json")


def load_state(data):
    try:
        with open(state_path(data), encoding="utf-8") as f:
            state = json.load(f)
        if isinstance(state, dict):
            return state
    except Exception:
        pass
    return {}


def save_state(data, state):
    try:
        path = state_path(data)
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, path)
    except Exception:
        pass


def remember_start(data):
    state = load_state(data)
    if "started" not in state:
        state["started"] = datetime.datetime.now().timestamp()
        state.setdefault("prompts", [])
        save_state(data, state)


def remember_prompt(data):
    """Kiro UserPromptSubmit: keep the last prompts for the snapshot."""
    text = os.environ.get("USER_PROMPT") or data.get("prompt") or data.get("user_prompt") or ""
    text = clean_prompt(_text_of(text))
    if not text:
        return
    state = load_state(data)
    state.setdefault("started", datetime.datetime.now().timestamp())
    prompts = state.get("prompts") or []
    now = datetime.datetime.now().timestamp()
    if prompts and prompts[-1] == text and now - state.get("last_prompt_at", 0) < 5:
        return  # the same hook installed twice (global and project)
    state["prompts"] = prompts[-(MAX_PROMPTS - 1):] + [text]
    state["last_prompt_at"] = now
    save_state(data, state)


# --- Snapshot -----------------------------------------------------------------

def written_since(started):
    """True when CURRENT.md was updated after the session started."""
    try:
        return started is not None and os.path.getmtime(CURRENT) >= started
    except OSError:
        return False


def write_snapshot(data, prompts, started, reason):
    if not prompts:
        return  # nothing worth recording (e.g. a session that only ran /model)
    if written_since(started):
        # CURRENT.md already says what this session did; the prompts would only
        # repeat it and cost tokens at every start.
        prompts_section = [
            "## Last prompts in that session",
            "Omitted: the handoff in CURRENT.md was updated during this session.",
        ]
    else:
        prompts_section = ["## Last prompts in that session", *[f"- {p}" for p in prompts]]
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    status = git("status", "--short") or "clean"
    lines = [
        "# Auto snapshot (last session end)",
        f"Ended: {now} | Reason: {reason} | Session: {session_id(data)}",
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
        *prompts_section,
        "",
    ]
    os.makedirs(DIR, exist_ok=True)
    ensure_git_exclude()
    with open(AUTO, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def claude_snapshot(data, reason_override=None):
    transcript = data.get("transcript_path") or ""
    reason = reason_override or data.get("reason", "?")
    if reason_override == "compact" and data.get("trigger"):
        reason = f"compact ({data['trigger']})"
    write_snapshot(data, claude_prompts(transcript), claude_started_at(transcript), reason)


def stop_snapshot(data):
    """Kiro and Antigravity: called when a turn or session ends."""
    state = load_state(data)
    if CLIENT == "antigravity":
        prompts = antigravity_prompts(data.get("transcriptPath") or "")
        reason = data.get("terminationReason") or "stop"
    else:
        prompts = state.get("prompts") or []
        reason = data.get("hook_event_name") or "stop"
    write_snapshot(data, prompts, state.get("started"), reason)


# --- Start --------------------------------------------------------------------

def handoff_branch(body):
    m = re.search(r"\bBranch:\s*([^\s|]+)", body)
    return m.group(1) if m else ""


def start_text(data):
    source = data.get("source", "startup") if CLIENT == "claude" else "startup"
    if os.path.isdir(DIR):
        ensure_git_exclude()
    branch = git("branch", "--show-current")
    parts, skipped = [], []
    author = "Claude" if CLIENT == "claude" else "the agent"
    for path, label in ((CURRENT, f"Handoff written by {author}"), (AUTO, "Automatic snapshot")):
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
            return (
                "Session continuity: older handoffs were not loaded because they are stale: "
                + ", ".join(skipped)
                + f". Mention this only if the user asks about earlier work; {RESUME_COMMAND[CLIENT]} loads them."
            )
        return ""
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
    return intro + "\n\n" + "\n\n".join(parts)


def first_start(data):
    """False when this session's handoff was already printed.

    Kiro runs global (~/.kiro/hooks) and project (.kiro/hooks) hooks side by
    side, so with both installed the start hook fires twice per session.
    """
    if session_id(data) == "?":
        return True
    marker = state_path(data)[:-len(".json")] + ".started"
    try:
        os.makedirs(os.path.dirname(marker), mode=0o700, exist_ok=True)
        os.close(os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        return True
    except FileExistsError:
        return False
    except Exception:
        return True


def start(data):
    if CLIENT == "claude":
        return start_text(data)
    if not first_start(data):
        return ""
    remember_start(data)
    return start_text(data)


# --- Main ---------------------------------------------------------------------

def emit(text):
    """Print hook output in the format the client expects."""
    if CLIENT == "antigravity":
        # Antigravity reads a JSON object from stdout on every event.
        out = {}
        if text:
            out = {"injectSteps": [{"systemMessage": {"systemMessage": text}}]}
        print(json.dumps(out))
    elif text:
        print(text)


def parse_args(argv):
    global CLIENT
    args = list(argv)
    if "--client" in args:
        i = args.index("--client")
        if i + 1 < len(args) and args[i + 1] in CLIENTS:
            CLIENT = args[i + 1]
        del args[i:i + 2]
    return args[0] if args else ""


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    mode = parse_args(sys.argv[1:])
    data = read_input()
    root = project_root(data)
    if not root:
        emit("")
        return
    set_root(root)
    text = ""
    try:
        if mode == "start":
            text = start(data)
        elif mode == "end":
            claude_snapshot(data)
        elif mode == "precompact":
            claude_snapshot(data, "compact")
        elif mode == "prompt":
            remember_prompt(data)
        elif mode == "stop":
            stop_snapshot(data)
    except Exception:
        text = ""
    # Kiro adds UserPromptSubmit stdout to the prompt, so "prompt" stays silent.
    if mode != "prompt":
        emit(text)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        if CLIENT == "antigravity":
            print("{}")
