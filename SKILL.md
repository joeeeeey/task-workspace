---
name: agent-harness
description: >-
  Repository-level task harness for AI coding agents. Use this skill whenever a
  user wants to initialize persistent task memory for a repo, start a durable
  engineering task, continue a long-running goal, hand off work between Codex or
  Claude sessions, prevent context drift, or keep weeks of agent conversation
  grounded in stable repo-local state. This skill treats the repository root as
  the execution workspace and stores per-goal memory under `.agent-harness/`.
---

# Agent Harness

Use this skill to give a repository stable, repo-local task memory for long-running AI coding work.

The key design rule is:

- Repository root = execution workspace where code edits, commands, tests, and git operations happen.
- `.agent-harness/tasks/<task-id>/` = task memory record for one goal.

Do not `cd` into the task memory directory to run project commands. Always run project commands from the repository root.

## When To Use

Use this skill when the user asks to:

- initialize a repo for persistent AI agent work,
- start a durable task or goal in a repo,
- continue a task across a long conversation,
- hand off work between sessions,
- keep memory stable over many turns,
- manage multiple independent goals in one repository,
- or create a repo-level task state without creating a separate workspace clone.

Do not use this skill for tiny one-off answers that do not need durable memory.

## Core Model

```text
repo-root/
  src/
  package.json
  AGENTS.md
  CLAUDE.md
  .agent-harness/
    config.yaml
    repo-profile.md
    current
    tasks/
      task-20260605-example/
        goal.md
        status.md
        decisions.md
        open-questions.md
        repo-context.md
        owner.json
        handoff.md
```

One repository can have multiple tasks. One running session should own only one active task at a time.

## Operating Rules

1. Before substantial work, check whether `.agent-harness/` exists.
2. If missing and the user wants durable work, initialize it with:

   ```bash
   python3 /path/to/agent-harness/scripts/harness.py --repo . init
   ```

3. Start a task with:

   ```bash
   python3 /path/to/agent-harness/scripts/harness.py --repo . start \
     --title "Fix flaky checkout tests" \
     --brief "Make the checkout flow stable"
   ```

4. Read the generated task files before implementation:
   - `.agent-harness/repo-profile.md`
   - `.agent-harness/tasks/<task-id>/goal.md`
   - `.agent-harness/tasks/<task-id>/status.md`
   - `.agent-harness/tasks/<task-id>/decisions.md`
   - `.agent-harness/tasks/<task-id>/open-questions.md`
   - `.agent-harness/tasks/<task-id>/repo-context.md`

5. After meaningful progress, update:
   - `status.md`
   - `decisions.md` when a decision was made
   - `open-questions.md` when uncertainty changes

6. If the user asks for handoff, generate or use `handoff.md`. After a successful handoff to another session, the old session should stop executing that task unless the user explicitly asks it to continue.

## First-Time Repo Initialization

Initialization should infer a repo profile from stable local files, including:

- `README.md`
- `AGENTS.md`
- `CLAUDE.md`
- package or build files such as `package.json`, `Makefile`, `pyproject.toml`, `go.mod`, `Cargo.toml`
- docs under `docs/` when present

The profile should summarize:

- product or project purpose,
- stack and package manager,
- common commands,
- agent rules,
- testing expectations,
- important docs,
- safety boundaries.

## Multiple Goals

Use separate task records for separate goals.

Good:

```text
.agent-harness/tasks/task-20260605-auth-refactor/
.agent-harness/tasks/task-20260605-fix-ci/
```

Avoid making one session actively implement both at the same time. If parallel work is needed, assign a separate session to each task and keep each task's `owner.json` current.

## Final Reply Shape

When initializing or starting a task, tell the user:

- repo root,
- task id,
- task memory path,
- whether the current session will continue or hand off,
- next command or next file to inspect.

Keep the response concise.
