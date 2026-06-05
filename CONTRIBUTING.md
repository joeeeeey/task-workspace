# Contributing

Agent Harness is intentionally small. Contributions should preserve these constraints:

- No external runtime dependencies for `scripts/harness.py`.
- The source repository root remains the bootstrap and context-capture location.
- `.agent-harness/tasks/<task-id>/` is the dedicated task workspace and follow-up session cwd.
- Code edits happen in the isolated `/tmp/agent-harness/<task-id>/<repo>/` clone.
- Do not add secret storage or credential handling.
- Keep generated task files readable by humans and agents.
- Keep English and Chinese README sections aligned when changing product messaging.

Before opening a PR:

```bash
python3 -m py_compile scripts/harness.py
python3 scripts/harness.py --repo . init --overwrite
python3 scripts/harness.py --repo . start --title "Smoke task" --brief "Smoke test" --task-id task-smoke
python3 scripts/harness.py clone --task-dir .agent-harness/tasks/task-smoke
```
