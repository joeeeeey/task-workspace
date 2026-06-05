# Task Workspace

Dedicated task workspaces for AI coding agents.

[中文文档](README.zh-CN.md)

Task Workspace is an AI skill that lets you turn repo-level brainstorming, requirements work, or partial investigation into a dedicated task workspace for Codex, Claude Code, and other AI coding agents.

The core promise:

> Keep long-running agent work stable for days or weeks by moving task memory into a dedicated workspace and code work into an isolated `/tmp` git worktree.

## The Model

Task Workspace uses three locations:

```text
source repo root
  where the user explores, brainstorms, reviews requirements, maybe creates a branch,
  and eventually bootstraps the task

.task-workspace/tasks/<task-id>/
  the dedicated task workspace and new agent session cwd
  contains AGENTS.md, CLAUDE.md, goal, context, status, decisions, handoff prompt

/tmp/task-workspace/<task-id>/<repo>/
  the isolated code workspace where implementation, tests, and commits happen
  defaults to git worktree; can fall back to git clone
```

That means the source repo is not the long-running execution workspace. It is the context capture point.

```text
your-repo/
  src/
  package.json
  AGENTS.md
  .task-workspace/
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

/tmp/task-workspace/task-20260605-fix-checkout/your-repo/
  code edits happen here
```

## Why This Exists

AI coding agents are good at local reasoning, but long-running work can drift:

- the conversation gets long,
- earlier decisions become hard to find,
- the active goal changes subtly,
- source repo state changes while the agent works,
- two sessions may accidentally work on the same thing,
- a new session may restart from scratch instead of continuing.

Task Workspace fixes that with a task ownership model:

- **Source repo root is for bootstrap**: capture branch, git status, diff summary, artifacts, and user intent.
- **Task workspace is the session root**: the new agent starts from `.task-workspace/tasks/<task-id>/` and gets task-local `AGENTS.md` / `CLAUDE.md`.
- **Code work happens in `/tmp`**: the task session prepares an isolated git worktree, checks out the task branch, and edits there.
- **Clone fallback remains available**: use `--code-workspace clone` when worktree is not appropriate.
- **One task has one owner**: parallel goals use separate task workspaces and separate code workspaces.
- **Handoff is explicit**: after launch, the bootstrap session stops unless the user explicitly wants it to continue.

## When To Use It

Use Task Workspace when a task is likely to take more than a few turns:

- feature implementation across multiple files,
- bug investigations with several hypotheses,
- refactors,
- migrations,
- design-to-code work,
- production follow-up work,
- multi-day personal projects,
- any task where "what have we already decided?" matters.

For tiny one-off edits, you probably do not need it.

## Install As An AI Skill

This repository is an AI skill repo. Install it directly from GitHub with the `skills` CLI:

```bash
npx skills add 'https://github.com/joeeeeey/task-workspace.git' \
  --global \
  --agent '*' \
  --yes
```

Install for Codex only:

```bash
npx skills add 'https://github.com/joeeeeey/task-workspace.git' \
  --global \
  --agent codex \
  --yes
```

List the skill without installing:

```bash
npx skills add 'https://github.com/joeeeeey/task-workspace.git' \
  --list
```

The skill lives at the repository root, so `--full-depth` is not required.

After installing, restart your agent runtime so it can load the new skill metadata.

## Quick Start

From a source repo after you have done some exploration:

```bash
python3 /path/to/task-workspace/scripts/task_workspace.py --repo . init
```

`init` also ensures `.task-workspace/` is listed in the source repo's `.gitignore`, because task workspaces are local operational memory by default.

Start a dedicated task workspace:

```bash
python3 /path/to/task-workspace/scripts/task_workspace.py --repo . start \
  --title "Fix checkout flow flakiness" \
  --brief "Investigate failing Playwright checkout tests and make the flow stable" \
  --capture-patch
```

The command prints:

- task workspace path,
- planned `/tmp` code workspace path,
- task branch,
- launch command.

By default, the `/tmp` code workspace is prepared with `git worktree`. If you start from a non-trunk branch, Task Workspace reuses that branch as the task branch; otherwise it creates `task-workspace/<task-id>`.

Start the new agent session from the task workspace:

```bash
cd .task-workspace/tasks/task-YYYYMMDD-fix-checkout-flow-flakiness
codex "$(cat launch-prompt.md)"
```

Inside that task session, prepare the `/tmp` code workspace:

```bash
python3 /path/to/task-workspace/scripts/task_workspace.py prepare --task-dir .
```

Then work from the printed `/tmp` code workspace path.

To force the old full-clone behavior:

```bash
python3 /path/to/task-workspace/scripts/task_workspace.py --repo . start \
  --title "Fix checkout flow flakiness" \
  --code-workspace clone
```

You can also use the compatibility command from an existing task workspace:

```bash
python3 /path/to/task-workspace/scripts/task_workspace.py clone --task-dir .
```

## Capturing Existing Work

If you already created a branch or made partial code changes in the source repo, start the task with `--capture-patch`.

Task Workspace captures:

- source branch,
- remote URL,
- `git status --short`,
- `git diff --stat`,
- optional binary patches under `artifacts/`,
- explicit artifacts passed with `--artifact`.

The task session can apply the captured patch to the `/tmp` code workspace when running `prepare`.

## Portable And Local State

Task Workspace splits task metadata into two files:

```text
task.json
  portable task identity, source repo name/remote, branch, task branch, agent, and requested code workspace mode

local.json
  machine-local source path, task workspace path, /tmp worktree path, clone source, and local patch file path
```

`task.json` is safe to share. `local.json` is ignored by the `share` command and can be regenerated on another machine from the portable task record.

## Sharing Task Records

By default, `init` ignores `.task-workspace/` because task records often contain local operational memory and imported artifacts. When you want cross-environment collaboration, run:

```bash
python3 /path/to/task-workspace/scripts/task_workspace.py --repo . share
```

`share` removes the broad `.task-workspace/` root ignore and writes `.task-workspace/.gitignore` so safe task records can be committed while machine-local and potentially large files stay out of git:

- ignored: `current`, `tasks/*/local.json`, `tasks/*/owner.json`, `tasks/*/artifacts/`, `tasks/*/logs/`, `tasks/*/local/`
- shareable: `config.yaml`, `repo-profile.md`, `task.json`, task-local Markdown files, `AGENTS.md`, `CLAUDE.md`, and `launch-prompt.md`

For one task:

```bash
python3 /path/to/task-workspace/scripts/task_workspace.py --repo . share --task-id task-20260605-fix-checkout
git add .task-workspace/.gitignore .task-workspace/config.yaml .task-workspace/repo-profile.md .task-workspace/tasks/task-20260605-fix-checkout
```

## Multiple Goals

One source repo can have many tasks:

```text
.task-workspace/tasks/task-20260605-auth-refactor/
.task-workspace/tasks/task-20260605-fix-ci/

/tmp/task-workspace/task-20260605-auth-refactor/your-repo/
/tmp/task-workspace/task-20260605-fix-ci/your-repo/
```

This is similar to subagents with stronger filesystem isolation: each task has its own memory directory and its own repository worktree. Merge conflicts are handled later like normal branch conflicts.

## Handoff

If the current session launches another session:

1. Write the task workspace.
2. Start the new session in `.task-workspace/tasks/<task-id>/`.
3. The new session reads `launch-prompt.md`.
4. The old session stops after a successful handoff unless the user explicitly wants both sessions active.

This avoids duplicate work and conflicting edits.

## Repository Structure

```text
task-workspace/
  SKILL.md
  agents/openai.yaml
  scripts/task_workspace.py
  references/templates/
```

## Design Principles

- Bootstrap from the source repo, but do not let long-running task agents edit it directly.
- Give every task workspace task-local `AGENTS.md` and `CLAUDE.md`.
- Keep code work in isolated `/tmp` git worktrees by default; use clone fallback when needed.
- Keep `.task-workspace/` local by default; commit task records only if you intentionally want that workflow.
- Make ownership visible.
- Prefer stable external state over hidden chat memory.
- Make handoff boring and deterministic.
- Never store secrets in `.task-workspace/`.
