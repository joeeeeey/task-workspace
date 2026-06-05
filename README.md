# Agent Harness

Persistent task memory for AI coding agents.

[中文文档](README.zh-CN.md)

Agent Harness is a repository-level harness that helps Codex, Claude Code, and other AI coding agents keep long-running engineering work stable across very long conversations, handoffs, and context resets.

The core promise:

> Keep one AI session working on the same goal for days or weeks without losing the thread.

It does this by moving the most important task state out of the chat window and into a small repo-local memory layer.

```text
your-repo/                         # execution workspace
  src/
  package.json
  AGENTS.md
  .agent-harness/                  # persistent memory layer
    config.yaml
    repo-profile.md
    current
    tasks/
      task-20260605-fix-checkout/
        goal.md
        status.md
        decisions.md
        open-questions.md
        repo-context.md
        owner.json
        handoff.md
```

## Why This Exists

AI coding agents are good at local reasoning, but long-running work can drift:

- the conversation gets long,
- earlier decisions become hard to find,
- the active goal changes subtly,
- two sessions may accidentally work on the same thing,
- a new session may restart from scratch instead of continuing.

Agent Harness fixes that with a simple operating model:

- **Repo root is the workspace**: code edits, commands, tests, and git operations happen in the repository root.
- **Task records are memory**: `.agent-harness/tasks/<task-id>/` stores goal, status, decisions, blockers, and handoff context.
- **One session owns one active task**: parallel goals are separate task records, not mixed in one conversation.
- **Handoff is explicit**: a new session reads `handoff.md` and continues from `status.md`.

## When To Use It

Use Agent Harness when a task is likely to take more than a few turns:

- feature implementation across multiple files,
- bug investigations with several hypotheses,
- refactors,
- migrations,
- design-to-code work,
- production follow-up work,
- multi-day personal projects,
- any task where "what have we already decided?" matters.

For tiny one-off edits, you probably do not need it.

## Quick Start

Clone or install this skill, then from any repository:

```bash
python3 /path/to/agent-harness/scripts/harness.py init
```

Start a task:

```bash
python3 /path/to/agent-harness/scripts/harness.py start \
  --title "Fix checkout flow flakiness" \
  --brief "Investigate failing Playwright checkout tests and make the flow stable"
```

Check state:

```bash
python3 /path/to/agent-harness/scripts/harness.py status
```

Then tell your agent:

```text
Use Agent Harness. Continue the current task from .agent-harness/current.
Work from the repo root and update status.md after meaningful progress.
```

## First-Time Initialization

`init` scans stable repo files and creates `.agent-harness/`:

- `README.md`
- `AGENTS.md`
- `CLAUDE.md`
- `package.json`, `Makefile`, `pyproject.toml`, `go.mod`, `Cargo.toml`
- common docs under `docs/`

It writes:

- `.agent-harness/config.yaml`: workspace mode, task root, detected commands.
- `.agent-harness/repo-profile.md`: project purpose, stack, commands, important docs, safety rules.
- `.agent-harness/current`: active task pointer.
- `.agent-harness/tasks/`: task memory records.

## Starting A Task

Each task gets its own record:

```text
.agent-harness/tasks/task-20260605-fix-checkout/
  goal.md            # what success means
  status.md          # current progress and next steps
  decisions.md       # decisions and rationale
  open-questions.md  # unresolved questions
  repo-context.md    # repo-root execution reminder
  owner.json         # current session owner
  handoff.md         # prompt for another session
```

The agent should read these files before implementation and update them as work progresses.

## Multiple Goals

One repository can have many tasks:

```text
.agent-harness/tasks/task-20260605-auth-refactor/
.agent-harness/tasks/task-20260605-fix-ci/
.agent-harness/tasks/task-20260605-docs-refresh/
```

But one running session should normally own only one active task. If you want parallel work, use a separate session per task and keep `owner.json` current.

## Handoff

If the current session needs to hand off work:

1. Update `status.md`.
2. Update `decisions.md` and `open-questions.md`.
3. Give the next session the task's `handoff.md`.
4. Stop the old session after a successful handoff unless the user explicitly wants both sessions active.

This avoids duplicate work and conflicting edits.

## Install As An AI Skill

This repository is an AI skill repo. Install it directly from GitHub with the `skills` CLI:

```bash
npx skills add 'https://github.com/joeeeeey/agent-harness.git' \
  --global \
  --agent '*' \
  --yes
```

Install for Codex only:

```bash
npx skills add 'https://github.com/joeeeeey/agent-harness.git' \
  --global \
  --agent codex \
  --yes
```

List the skill without installing:

```bash
npx skills add 'https://github.com/joeeeeey/agent-harness.git' \
  --list
```

The skill lives at the repository root, so `--full-depth` is not required.

Repository structure:

```text
agent-harness/
  SKILL.md
  agents/openai.yaml
  scripts/harness.py
  references/templates/
```

After installing, restart your agent runtime so it can load the new skill metadata. Then ask:

```text
Use Agent Harness to initialize this repository for persistent task memory.
```

## Design Principles

- Keep the repo as the execution workspace.
- Keep task memory small and explicit.
- Make ownership visible.
- Prefer stable external state over hidden chat memory.
- Make handoff boring and deterministic.
- Never store secrets in `.agent-harness/`.
