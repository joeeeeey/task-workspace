# Example: Crit Deck / Signal Desk

This example shows how Agent Harness would initialize a product repository where the repo root is the execution workspace.

```bash
cd /path/to/signal-desk
python3 /path/to/agent-harness/scripts/harness.py init
python3 /path/to/agent-harness/scripts/harness.py start \
  --title "Polish draw arena mobile UI" \
  --brief "Improve the draw arena mobile layout while preserving existing TCG visual language and i18n rules"
```

The agent should then work from the repository root:

```text
/path/to/signal-desk
```

Task memory lives under:

```text
.agent-harness/tasks/task-YYYYMMDD-polish-draw-arena-mobile-ui/
```

The task record should remind the agent to read:

- `README.md`
- `AGENTS.md`
- `CLAUDE.md`
- `docs/workflow/feature-workflow.md`
- `.agent-harness/repo-profile.md`

