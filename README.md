# Agent Harness

Dedicated task workspaces for AI coding agents.

[中文文档](README.zh-CN.md)

Agent Harness is an AI skill that lets you turn repo-level brainstorming, requirements work, or partial investigation into a dedicated task workspace for Codex, Claude Code, and other AI coding agents.

The core promise:

> Keep long-running agent work stable for days or weeks by moving task memory into a dedicated workspace and code work into an isolated `/tmp` clone.

## The Model

Agent Harness uses three locations:

```text
source repo root
  where the user explores, brainstorms, reviews requirements, maybe creates a branch,
  and eventually bootstraps the task

.agent-harness/tasks/<task-id>/
  the dedicated task workspace and new agent session cwd
  contains AGENTS.md, CLAUDE.md, goal, context, status, decisions, handoff prompt

/tmp/agent-harness/<task-id>/<repo>/
  the isolated code clone where implementation, tests, and commits happen
```

That means the source repo is not the long-running execution workspace. It is the context capture point.

```text
your-repo/
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

/tmp/agent-harness/task-20260605-fix-checkout/your-repo/
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

Agent Harness fixes that with a task ownership model:

- **Source repo root is for bootstrap**: capture branch, git status, diff summary, artifacts, and user intent.
- **Task workspace is the session root**: the new agent starts from `.agent-harness/tasks/<task-id>/` and gets task-local `AGENTS.md` / `CLAUDE.md`.
- **Code work happens in `/tmp`**: the task session prepares an isolated clone, checks out the task branch, and edits there.
- **One task has one owner**: parallel goals use separate task workspaces and separate clones.
- **Handoff is explicit**: after launch, the bootstrap session stops unless the user explicitly wants it to continue.

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

After installing, restart your agent runtime so it can load the new skill metadata.

## Quick Start

From a source repo after you have done some exploration:

```bash
python3 /path/to/agent-harness/scripts/harness.py --repo . init
```

`init` also ensures `.agent-harness/` is listed in the source repo's `.gitignore`, because task workspaces are local operational memory by default.

Start a dedicated task workspace:

```bash
python3 /path/to/agent-harness/scripts/harness.py --repo . start \
  --title "Fix checkout flow flakiness" \
  --brief "Investigate failing Playwright checkout tests and make the flow stable" \
  --capture-patch
```

The command prints:

- task workspace path,
- planned `/tmp` clone path,
- task branch,
- launch command.

Start the new agent session from the task workspace:

```bash
cd .agent-harness/tasks/task-YYYYMMDD-fix-checkout-flow-flakiness
codex "$(cat launch-prompt.md)"
```

Inside that task session, prepare the `/tmp` code clone:

```bash
python3 /path/to/agent-harness/scripts/harness.py clone --task-dir .
```

Then work from the printed `/tmp` clone path.

## Capturing Existing Work

If you already created a branch or made partial code changes in the source repo, start the task with `--capture-patch`.

Agent Harness captures:

- source branch,
- remote URL,
- `git status --short`,
- `git diff --stat`,
- optional binary patches under `artifacts/`,
- explicit artifacts passed with `--artifact`.

The task session can apply the captured patch to the `/tmp` clone when running `clone`.

## Multiple Goals

One source repo can have many tasks:

```text
.agent-harness/tasks/task-20260605-auth-refactor/
.agent-harness/tasks/task-20260605-fix-ci/

/tmp/agent-harness/task-20260605-auth-refactor/your-repo/
/tmp/agent-harness/task-20260605-fix-ci/your-repo/
```

This is similar to subagents with stronger filesystem isolation: each task has its own memory directory and its own repository clone. Merge conflicts are handled later like normal branch conflicts.

## Handoff

If the current session launches another session:

1. Write the task workspace.
2. Start the new session in `.agent-harness/tasks/<task-id>/`.
3. The new session reads `launch-prompt.md`.
4. The old session stops after a successful handoff unless the user explicitly wants both sessions active.

This avoids duplicate work and conflicting edits.

## Repository Structure

```text
agent-harness/
  SKILL.md
  agents/openai.yaml
  scripts/harness.py
  references/templates/
```

## Design Principles

- Bootstrap from the source repo, but do not let long-running task agents edit it directly.
- Give every task workspace task-local `AGENTS.md` and `CLAUDE.md`.
- Keep code work in isolated `/tmp` clones.
- Keep `.agent-harness/` local by default; commit task records only if you intentionally want that workflow.
- Make ownership visible.
- Prefer stable external state over hidden chat memory.
- Make handoff boring and deterministic.
- Never store secrets in `.agent-harness/`.
