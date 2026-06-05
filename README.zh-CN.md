# Agent Harness 中文说明

[English README](README.md)

Agent Harness 是一个 AI skill，用来把 repo 里的前期分析、需求讨论、头脑风暴、甚至已经开始的代码改动，迁移成一个独立的 task workspace，让 Codex / Claude 可以在更稳定的上下文里长期工作。

核心承诺：

> 通过独立 task workspace 和 `/tmp` 代码 clone，让 AI agent 的长任务可以稳定持续数天到数周。

## 三层模型

Agent Harness 有三个位置：

```text
source repo root
  用户前期探索、头脑风暴、需求确认、可能开 branch 或做少量改动的地方

.agent-harness/tasks/<task-id>/
  独立 task workspace，也是新 Codex/Claude session 的 cwd
  包含 AGENTS.md、CLAUDE.md、goal、context、status、decisions、launch-prompt

/tmp/agent-harness/<task-id>/<repo>/
  独立代码 clone，真正改代码、跑测试、commit 的地方
```

也就是说，repo root 不是长期执行 workspace，而是 **context capture 入口**。

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
  代码改动发生在这里
```

## 核心卖点

- **长对话不漂移**：目标、状态、决策都落在 task workspace 文件里。
- **task-local 指令完整**：每个 task 都有自己的 `AGENTS.md` / `CLAUDE.md`。
- **源 repo 不被污染**：新 session 不直接在 source repo 改代码。
- **代码隔离**：每个 task 都有自己的 `/tmp` clone，可以并行工作。
- **handoff 可控**：新 session 接管后，bootstrap session 停止，避免两个 agent 同时做同一件事。
- **适合长任务**：feature、bug、refactor、migration、设计落地、长期个人项目都适合。

## 什么时候用

适合：

- 多文件 feature；
- 复杂 bug investigation；
- 已经在 repo root 里讨论了一段需求，准备正式开工；
- 已经开 branch 或有一点未提交代码，想迁移到独立 task workspace；
- 需要几天持续推进的个人项目；
- 大 refactor；
- migration；
- 多个目标需要并行推进。

不适合：

- 一句话回答；
- 很小的单文件改动；
- 不需要后续记忆的一次性命令。

## 作为 AI Skill 安装

这个 repo 的定位是一个 AI skill repo，可以直接用 `npx skills add` 加 GitHub 链接安装：

```bash
npx skills add 'https://github.com/joeeeeey/agent-harness.git' \
  --global \
  --agent '*' \
  --yes
```

只安装给 Codex：

```bash
npx skills add 'https://github.com/joeeeeey/agent-harness.git' \
  --global \
  --agent codex \
  --yes
```

只查看可安装 skill，不安装：

```bash
npx skills add 'https://github.com/joeeeeey/agent-harness.git' \
  --list
```

这个 skill 就在 repo 根目录，所以不需要 `--full-depth`。

安装后重启 agent runtime，让它重新加载 skill metadata。

## 快速开始

在 source repo 里完成前期探索后运行：

```bash
python3 /path/to/agent-harness/scripts/harness.py --repo . init
```

`init` 也会把 `.agent-harness/` 写入 source repo 的 `.gitignore`。这些 task workspace 默认是本地操作记忆，不建议自动提交进业务 repo。

创建独立 task workspace：

```bash
python3 /path/to/agent-harness/scripts/harness.py --repo . start \
  --title "Fix checkout flow flakiness" \
  --brief "Investigate failing Playwright checkout tests and make the flow stable" \
  --capture-patch
```

命令会输出：

- task workspace path；
- 计划的 `/tmp` clone path；
- task branch；
- launch command。

从 task workspace 启动新 session：

```bash
cd .agent-harness/tasks/task-YYYYMMDD-fix-checkout-flow-flakiness
codex "$(cat launch-prompt.md)"
```

在新 task session 里准备 `/tmp` 代码 clone：

```bash
python3 /path/to/agent-harness/scripts/harness.py clone --task-dir .
```

然后进入输出的 `/tmp` clone 路径里改代码、跑测试、commit。

## 捕获已有工作

如果你已经在 source repo 开了 branch 或做了一些未提交代码，用 `--capture-patch`：

- 捕获 source branch；
- 捕获 remote URL；
- 捕获 `git status --short`；
- 捕获 `git diff --stat`；
- 保存 patch artifact；
- 复制显式传入的 `/tmp` artifact。

新 task session 执行 `clone` 时可以把 patch 应用到 `/tmp` clone。

## 多目标并行

一个 source repo 可以有多个 task：

```text
.agent-harness/tasks/task-20260605-auth-refactor/
.agent-harness/tasks/task-20260605-fix-ci/

/tmp/agent-harness/task-20260605-auth-refactor/your-repo/
/tmp/agent-harness/task-20260605-fix-ci/your-repo/
```

这很像 subagent，但文件系统隔离更完整：每个 task 有自己的记忆目录和代码 clone。后续 merge 慢的一方如果冲突，就按普通分支冲突处理。

## 关键设计

```text
source repo root   = bootstrap / context capture
task workspace     = new agent session cwd + durable memory
/tmp clone         = code execution workspace
one task           = one goal
one session        = one active owner
launch-prompt.md   = next session startup prompt
```

`.agent-harness/` 默认保持本地状态；只有明确需要团队共享 task record 时才手动调整。

这就是它稳定的原因：模型可以忘，但 task workspace 和 `/tmp` clone 不会忘。
