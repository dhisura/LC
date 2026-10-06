# 🏢 LC (LazyCorp)

> *"The disciplined, high-performing software team that writes minimal, bulletproof code because everyone wants to go home on time."*

LC is a local-first multi-agent software engineering & autonomous system automation company powered by **Ollama** and **Qwen 2.5**. Everything runs on your machine — no cloud, no API keys.

## 🎭 The Team
- 📋 **PM (Project Manager)**: Runs pre-flight environment audits and reports **what is missing** before writing any code.
- 💻 **Dev (Senior Minimalist)**: Observes the **Anti-Overtime Diff Budget**—writes clean, concise code with zero boilerplate.
- 🧪 **QA (Verification Engineer)**: Runs real PowerShell tests and checks, with a 2-retry fail-fast limit.
- 🛡️ **QC (Quality Control)**: Reviews diffs, checks compliance, and stores **Mistake Vaccines** in SQLite.

## 📦 Requirements
- Python 3.10+
- [Ollama](https://ollama.com/) running locally, with the model pulled:
  ```bash
  ollama serve            # if it is not already running
  ollama pull qwen2.5:3b  # required — LC does not pull models for you
  ```
- `git` on your `PATH` (LC checks for it during pre-flight)

## 🚀 Install

```bash
git clone https://github.com/dhisura/LC.git
cd LC
pip install -e .
```

Installing from the repo root puts the `lc` package on your `PATH`. If you would
rather not install, every command below also works as `python -m lc`.

## 🏃 Quickstart

```bash
# Start an interactive sprint
python -m lc

# Or provide a task directly
python -m lc "Build a lightweight CLI countdown timer in Python with unit tests"

# Non-interactive: auto-approve the planning gate and all commands
python -m lc --yes "Add a --version flag to the parser"
```

## 🔍 Inspection commands

These are flags, **not** positional arguments — `python -m lc vaccines` would run a
sprint with the literal task "vaccines".

```bash
python -m lc --vaccines   # List stored Mistake Vaccines
python -m lc --models     # Check the Ollama connection and list local models
python -m lc --skills     # List installed skill plugins
python -m lc --new-skill my-skill   # Scaffold a new skill in ~/.lc/skills/
```

## 🛡️ Safety model

LC executes shell commands that an LLM generated, so the **ExecutionGuard** sits in
front of every one of them.

- A command is tokenized with quote awareness, then checked against a per-command
  allowlist. Only read-only commands (`dir`, `git status`, `git log`, …) auto-approve.
- Anything containing shell metacharacters outside quotes — `;`, `&`, `|`, `>`,
  `$(...)`, backticks, newlines — requires approval, even if it starts with an
  otherwise-safe command. `git log; git push` is not a safe `git log`.
- Interpreters (`python`, `py`, `node`) are limited to version probes; `python -c "..."`
  always prompts.
- Reads of credential material (`.ssh`, `.aws`, `.env`, …) are blocked.
- Everything else stops and asks: `[Y]` once, `[A]` for the session, `[N]` deny, or
  `[C]` to substitute a different command.

Use `--yes` only in a disposable workspace or a container — it disables every prompt.

### The workspace is a boundary

File operations are confined to `--workspace`. `FileManager.resolve()` rejects
anything that lands outside it — `../`, an absolute path, or a symlink pointing
out — so a `[FILE: ...]` header naming `../../.ssh/authorized_keys` is refused
rather than written. A refused file is skipped and reported; the rest of the
sprint's work is kept.

### Permission tiers

`AgentState.permission_level` tracks how destructive the agent currently is,
derived from the lifecycle mode (`IDLE`→observe, `PLANNING`→read,
`EXECUTING`/`VERIFYING`→write). No mode grants the destructive tier implicitly;
`state.can_perform(level)` answers whether an operation is in bounds. Only
`EXECUTING` is entered after the planning gate, so file writes never happen
before you approve the plan.

## 🧩 Skills

Skills are folders containing a `SKILL.md` (description injected into agent prompts)
and an optional `skill.py` exporting `run(context) -> dict`.

They load from two places, with `~/.lc/skills` taking precedence:

1. `~/.lc/skills/` — your own, where `lc --new-skill` scaffolds.
2. `skills/` in this repo — `github_deploy` (implemented) and `UI` (scaffold only).

## 🧪 Tests

```bash
python -m unittest discover -s tests -t .
```

## 📂 Layout

```
lc/
  cli.py          Sprint orchestrator + argparse entrypoint
  config.py       Environment config; no side effects at import
  core/           Runtime, state machine, event bus, execution context
  roles/          PM, Dev, QA, QC
  engine/         Ollama client, SQLite memory, skill loader
  tools/          Execution guard, PowerShell runner, file manager
  ui/             Rich console rendering
skills/           Bundled skill plugins
tests/            unittest suite
```

Runtime state (the memory database and installed skills) lives under `~/.lc/`, not
in the source tree.

## ⚙️ Configuration

| Variable | Default | Purpose |
|---|---|---|
| `LC_OLLAMA_HOST` | `http://localhost:11434` | Ollama endpoint |
| `LC_MODEL` | `qwen2.5:3b` | Default model |
| `LC_HOME` | `~/.lc` | Memory DB + skills directory |
| `LC_GUARD_EXTRA_SAFE_COMMANDS` | *(empty)* | Extra auto-approved commands (comma-separated) |
| `LC_GUARD_EXTRA_SAFE_GIT_SUBCOMMANDS` | *(empty)* | Extra auto-approved read-only git subcommands |
| `LC_GUARD_EXTRA_SENSITIVE_MARKERS` | *(empty)* | Extra path fragments treated as credentials |

The three `LC_GUARD_EXTRA_*` variables widen the ExecutionGuard's allowlists so a
project can auto-approve its own read-only tools without `--yes`:

```bash
setx LC_GUARD_EXTRA_SAFE_COMMANDS "npm, npx, bun"
```

Two limits are fixed regardless of these settings:

- Shell metacharacters (`;`, `|`, `>`, `$(...)`) always require approval, so
  `npm run build; Remove-Item .` still prompts.
- Mutating git subcommands (`push`, `commit`, `reset`, `clean`, `add`, …) can
  never be added to the git allowlist. Listing one is silently ignored rather
  than honoured.

## ⚠️ A note on scope

The bundled `github_deploy` skill creates a **public** GitHub repository and turns
on GitHub Pages. It refuses to do either without `confirm=True` in its context, and
it stops rather than publishing when the workspace contains credential-like files
(`.env`, `*.pem`, `id_rsa`, …) or sits inside an existing git repository. Pass
`dry_run=True` to print the plan without contacting GitHub. See
`skills/github_deploy/SKILL.md`.
