# Agent Harness

Persistent task memory for AI coding agents.

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

## Public Skill Installation

This repository is structured as a skill:

```text
agent-harness/
  SKILL.md
  agents/openai.yaml
  scripts/harness.py
  references/templates/
```

Install it with your preferred skill installer or copy it into your local skills directory.

## Design Principles

- Keep the repo as the execution workspace.
- Keep task memory small and explicit.
- Make ownership visible.
- Prefer stable external state over hidden chat memory.
- Make handoff boring and deterministic.
- Never store secrets in `.agent-harness/`.

---

# Agent Harness 中文说明

Agent Harness 是一个给 AI coding agent 用的 **repo-level 任务记忆框架**。

它的目标很简单：

> 让一个 AI session 即使连续工作数天到数周，经历很多轮对话，仍然能稳定记住当前目标、进度、决策和未解决问题。

它不是让模型本身“记性变好”，而是把关键任务状态从聊天上下文里搬到 repo 内的稳定文件系统里。

```text
your-repo/                         # 执行 workspace：改代码、跑命令、跑测试
  src/
  package.json
  AGENTS.md
  .agent-harness/                  # 任务记忆层
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

## 核心卖点

- **长对话不漂移**：目标、状态、决策都落在文件里，不完全依赖聊天上下文。
- **单个 session 能持续做很久**：第 50 轮、第 100 轮仍然可以回到 `status.md` 和 `decisions.md` 找到当前状态。
- **repo 本身就是 workspace**：不复制 repo，不新建奇怪工作目录；命令和代码改动都在 repo root。
- **每个 goal 独立记忆**：一个 repo 可以有多个 task，但每个 task 有自己的状态文件。
- **handoff 可控**：新 session 接班时读 `handoff.md`，旧 session 停止，避免两个 agent 做同一件事。
- **适合个人项目和团队 repo**：可以用于 feature、bug、refactor、migration、设计落地、长期实验。

## 什么时候用

适合：

- 多文件 feature；
- 复杂 bug investigation；
- 需要几天持续推进的个人项目；
- 大 refactor；
- migration；
- 需要反复测试和记录决策的任务；
- 任何你担心 AI “聊着聊着忘了原目标”的工作。

不适合：

- 一句话回答；
- 很小的单文件改动；
- 不需要后续记忆的一次性命令。

## 第一次初始化

在任意 repo 根目录运行：

```bash
python3 /path/to/agent-harness/scripts/harness.py init
```

它会扫描：

- `README.md`
- `AGENTS.md`
- `CLAUDE.md`
- `package.json` / `Makefile` / `pyproject.toml` / `go.mod` / `Cargo.toml`
- `docs/` 里的常见文档

然后生成：

- `.agent-harness/config.yaml`
- `.agent-harness/repo-profile.md`
- `.agent-harness/current`
- `.agent-harness/tasks/`

## 开始一个任务

```bash
python3 /path/to/agent-harness/scripts/harness.py start \
  --title "Fix checkout flow flakiness" \
  --brief "Investigate failing Playwright checkout tests and make the flow stable"
```

之后告诉 agent：

```text
Use Agent Harness. Continue the current task from .agent-harness/current.
Work from the repo root and update status.md after meaningful progress.
```

## 关键设计

```text
repo root        = execution workspace
task record      = memory only
one task         = one goal
one session      = one active owner
handoff.md       = next session startup prompt
```

这就是它能保持稳定的原因：模型可以忘，但任务文件不会忘。

