# Contributing

Task Workspace is intentionally small. Contributions should preserve these constraints:

- No external runtime dependencies for `scripts/task_workspace.py`.
- The source repository root remains the bootstrap and context-capture location.
- `.task-workspace/tasks/<task-id>/` is the dedicated task workspace and follow-up session cwd.
- Code edits happen in the isolated `/tmp/task-workspace/<task-id>/<repo>/` code workspace.
- Do not add secret storage or credential handling.
- Keep generated task files readable by humans and agents.
- Keep English and Chinese README sections aligned when changing product messaging.

Before opening a PR:

```bash
python3 -m py_compile scripts/task_workspace.py
python3 scripts/task_workspace.py --repo . init --overwrite
python3 scripts/task_workspace.py --repo . start --title "Smoke task" --brief "Smoke test" --task-id task-smoke
python3 scripts/task_workspace.py prepare --task-dir .task-workspace/tasks/task-smoke
```
