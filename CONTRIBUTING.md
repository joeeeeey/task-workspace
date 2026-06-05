# Contributing

Agent Harness is intentionally small. Contributions should preserve these constraints:

- No external runtime dependencies for `scripts/harness.py`.
- The repository root remains the execution workspace.
- `.agent-harness/tasks/<task-id>/` remains memory only.
- Do not add secret storage or credential handling.
- Keep generated task files readable by humans and agents.
- Keep English and Chinese README sections aligned when changing product messaging.

Before opening a PR:

```bash
python3 -m py_compile scripts/harness.py
python3 scripts/harness.py --repo . init --overwrite
python3 scripts/harness.py --repo . status
```

