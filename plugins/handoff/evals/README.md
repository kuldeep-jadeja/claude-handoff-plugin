# Evals

Cases for `claude plugin eval`:

| Case | Checks |
| --- | --- |
| `save-before-clear` | "I'm going to /clear" triggers the skill, writes `CURRENT.md` in the template, and keeps the facts that matter. |
| `no-secrets` | A password and an API key the user mentioned never reach the handoff. |
| `resume-command` | `/handoff:resume` summarises the handoff, warns about the other branch, and waits before working. |

Run from `plugins/handoff`:

```bash
claude plugin eval . --scaffold --allow-tools Write --judge-model sonnet
```

- `--scaffold` runs `resume-command/fixture.sh`, which creates a git repo and a sample handoff in the run's empty workspace.
- `Write` lets the skill save `CURRENT.md`. The cases do not need `Bash`; granting it is optional and needs a working sandbox (on Linux, `bubblewrap` and `socat`, and on Ubuntu 24.04+ the AppArmor profile from the Claude Code sandboxing docs).
- Each case runs twice with the plugin and twice without it, so every run costs about 12 model sessions.
- Use `--judge-model sonnet`: the default Haiku judge sometimes marks a correct resume summary as a failure.

## Last results (1.2.0, 2026-11-02, Claude Code 2.1.316)

| Case | With plugin | Without | Δ |
| --- | --- | --- | --- |
| `save-before-clear` | 1.00 (2 runs) | 0.00 | +1.00 |
| `no-secrets` | 1.00 (2 runs) | 0.00 | +1.00 |
| `resume-command` | 1.00 (3 runs) | 0.89 | +0.11 |

Without the plugin, Claude does not save a handoff file at all. The resume case gains little because the sample handoff sits in the workspace, where Claude can find it unaided; it mainly guards the command's behaviour (branch warning, no edits before confirmation).
