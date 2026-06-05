# Example: Crit Deck / Signal Desk

This example shows how Task Workspace can turn repo-root exploration into a dedicated task workspace.

```bash
cd /path/to/signal-desk
python3 /path/to/task-workspace/scripts/task_workspace.py --repo . init
python3 /path/to/task-workspace/scripts/task_workspace.py --repo . start \
  --title "Polish draw arena mobile UI" \
  --brief "Improve the draw arena mobile layout while preserving existing TCG visual language and i18n rules" \
  --capture-patch
```

The bootstrap command creates:

```text
/path/to/signal-desk/.task-workspace/tasks/task-YYYYMMDD-polish-draw-arena-mobile-ui/
```

Start the next agent from that task workspace:

```bash
cd /path/to/signal-desk/.task-workspace/tasks/task-YYYYMMDD-polish-draw-arena-mobile-ui
codex "$(cat launch-prompt.md)"
```

The task session then prepares and uses an isolated code workspace:

```bash
python3 /path/to/task-workspace/scripts/task_workspace.py prepare --task-dir .
cd /tmp/task-workspace/task-YYYYMMDD-polish-draw-arena-mobile-ui/signal-desk
```

The task workspace should remind the agent to read:

- `AGENTS.md`
- `CLAUDE.md`
- `goal.md`
- `context.md`
- `status.md`
- `source-repo.md`
- `worktree.md`
