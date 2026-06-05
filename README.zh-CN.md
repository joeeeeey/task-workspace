# Agent Harness 中文说明

[English README](README.md)

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

安装后重启 agent runtime，让它重新加载 skill metadata。然后可以直接说：

```text
Use Agent Harness to initialize this repository for persistent task memory.
```
