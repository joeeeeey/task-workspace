---
name: agent-harness
description: >-
  Repository task harness for AI coding agents. Use this skill whenever a user
  wants to capture repo context into a durable task workspace, start a long
  running goal from an existing repo, migrate brainstorming or partial work into
  a dedicated Codex/Claude session, create task-local AGENTS/CLAUDE instructions,
  hand off work, prevent context drift, or run parallel tasks through isolated
  /tmp repository clones. This skill bootstraps from the source repo, launches
  follow-up agents from `.agent-harness/tasks/<task-id>/`, and keeps code
  changes in a separate /tmp clone.
---

# Agent Harness

Use this skill to turn early repo exploration into a dedicated task workspace for long-running AI coding work.

The model has three locations:

```text
source repo root        user exploration / bootstrap / context capture
task workspace          .agent-harness/tasks/<task-id>/, new agent cwd
/tmp worktree clone     actual code edits, commands, tests, git commits
```

This intentionally mirrors a human handoff:

1. Explore in the source repo.
2. Capture the goal, decisions, artifacts, branch, status, and optional patch.
3. Start a fresh task-owned agent session from the task workspace.
4. Let that session prepare a /tmp clone and implement there.

## When To Use

Use this skill when the user asks to:

- initialize a repo for persistent AI agent work,
- convert brainstorming or requirements into a durable task,
- start a long-running feature, bug, refactor, migration, or design task,
- preserve context after many turns of exploration,
- hand off to a fresh Codex or Claude session,
- run multiple goals in parallel through separate task workspaces and /tmp clones,
- or avoid contaminating the source repo while the task agent works.

Do not use this skill for tiny one-off answers that do not need durable memory.

## Core Layout

```text
source-repo/
  src/
  package.json
  AGENTS.md
  .agent-harness/
    config.yaml
    repo-profile.md
    current
    tasks/
      task-20260605-fix-checkout/
        AGENTS.md
        CLAUDE.md
        goal.md
        context.md
        status.md
        decisions.md
        open-questions.md
        source-repo.md
        worktree.md
        launch-prompt.md
        task.json
        artifacts/

/tmp/agent-harness/task-20260605-fix-checkout/source-repo/
  actual code edits happen here
```

## Operating Rules

1. Bootstrap from the source repo root after exploration, requirements work, or partial investigation.
2. Initialize repo profile if needed:

   ```bash
   python3 /path/to/agent-harness/scripts/harness.py --repo . init
   ```

   `init` also ensures `.agent-harness/` is ignored in the source repo by default.

3. Start a task workspace:

   ```bash
   python3 /path/to/agent-harness/scripts/harness.py --repo . start \
     --title "Fix flaky checkout tests" \
     --brief "Make the checkout flow stable" \
     --capture-patch
   ```

4. If launch succeeds, the bootstrap session should stop after the final handoff reply unless the user explicitly asks it to continue.
5. The new session should start with task workspace as cwd and read `launch-prompt.md`.
6. The task session prepares the /tmp clone:

   ```bash
   python3 /path/to/agent-harness/scripts/harness.py clone --task-dir .
   ```

7. The task session edits code and runs commands inside the /tmp clone, not inside the source repo root or task workspace.
8. After meaningful progress, update `status.md`; update `decisions.md` and `open-questions.md` when needed.

## Multiple Goals

Use separate task workspaces and separate /tmp clones for separate goals.

Good:

```text
.agent-harness/tasks/task-20260605-auth-refactor/
.agent-harness/tasks/task-20260605-fix-ci/
/tmp/agent-harness/task-20260605-auth-refactor/repo/
/tmp/agent-harness/task-20260605-fix-ci/repo/
```

Merge conflicts are handled later like normal parallel branches.

## Final Reply Shape

When starting a task, tell the user:

- source repo root,
- task workspace path,
- /tmp clone target,
- task branch,
- launch command or whether launch already happened,
- and whether the current session is stopping after handoff.

Keep the response concise.
