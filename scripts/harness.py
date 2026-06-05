#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
TEMPLATE_DIR = REPO_DIR / "references" / "templates"
HARNESS_DIR = ".agent-harness"
DEFAULT_TMP_ROOT = Path(os.environ.get("AGENT_HARNESS_TMP_ROOT", "/tmp/agent-harness"))
TEXT_LIMIT = 1800
MAIN_BRANCHES = {"main", "master", "dev", "develop", "trunk"}
SENSITIVE_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA |)PRIVATE KEY-----"),
    re.compile(r"(?i)\b(AWS_SECRET_ACCESS_KEY|AWS_SESSION_TOKEN|GITHUB_TOKEN|OPENAI_API_KEY)\b"),
    re.compile(r"(?i)\b(private_key|client_secret|access_token|refresh_token)\b\s*[:=]"),
    re.compile(r"(?i)\bapi[_-]?key\b\s*[:=]"),
]


@dataclass
class RepoFacts:
    root: Path
    name: str
    branch: str
    remote_url: str
    purpose: str
    stack: list[str]
    commands: dict[str, str]
    agent_guidance: str
    important_docs: list[str]
    status_short: str
    diff_stat: str


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def run(cmd: list[str], cwd: Path, *, check: bool = False) -> str:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and proc.returncode != 0:
        raise SystemExit(f"Command failed: {' '.join(cmd)}\n{proc.stderr.strip()}")
    return proc.stdout.strip()


def find_repo_root(start: Path) -> Path:
    git_root = run(["git", "rev-parse", "--show-toplevel"], start)
    if git_root:
        return Path(git_root).resolve()
    return start.resolve()


def read_text(path: Path, limit: int | None = None) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    if limit and len(text) > limit:
        return text[:limit].rstrip() + "\n..."
    return text


def slugify(value: str, max_words: int = 8) -> str:
    raw = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    words = [part for part in raw.split("-") if part]
    return "-".join(words[:max_words]) or "task"


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def render(template_name: str, values: dict[str, str]) -> str:
    text = (TEMPLATE_DIR / template_name).read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{ " + key + " }}", value)
    return text


def yaml_list(items: list[str], indent: int = 4) -> str:
    pad = " " * indent
    if not items:
        return f"{pad}[]"
    return "\n".join(f"{pad}- {json.dumps(item)}" for item in items)


def yaml_map(items: dict[str, str], indent: int = 4) -> str:
    pad = " " * indent
    if not items:
        return f"{pad}{{}}"
    return "\n".join(f"{pad}{key}: {json.dumps(value)}" for key, value in items.items())


def bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- None detected"


def fenced(text: str, fallback: str = "None") -> str:
    return f"```text\n{text.strip() or fallback}\n```"


def detect_package_commands(root: Path) -> dict[str, str]:
    commands: dict[str, str] = {}
    make_targets: set[str] = set()
    makefile = root / "Makefile"
    if makefile.exists():
        for line in read_text(makefile).splitlines():
            match = re.match(r"^([A-Za-z0-9_.:-]+):(?:\s|$)", line)
            if match and not match.group(1).startswith("."):
                make_targets.add(match.group(1))
    package_json = root / "package.json"
    if package_json.exists():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            scripts = data.get("scripts") or {}
            package_manager = str(data.get("packageManager") or "")
            runner = "pnpm" if "pnpm" in package_manager or (root / "pnpm-lock.yaml").exists() else "npm run"
            for name in ["dev", "lint", "typecheck", "build", "test", "test:e2e"]:
                if name in scripts:
                    commands[name] = f"make {name}" if name in make_targets else f"{runner} {name}"
        except Exception:
            pass
    if make_targets:
        for name in ["install", "check", "test", "deploy-preview", "deploy-prod"]:
            if name in make_targets:
                commands.setdefault(name, f"make {name}")
        commands.setdefault("make", "make")
    if (root / "pyproject.toml").exists():
        commands.setdefault("python-check", "python -m pytest")
    if (root / "go.mod").exists():
        commands.setdefault("go-test", "go test ./...")
    if (root / "Cargo.toml").exists():
        commands.setdefault("cargo-test", "cargo test")
    return commands


def detect_stack(root: Path) -> list[str]:
    stack: list[str] = []
    package_json = root / "package.json"
    if package_json.exists():
        stack.append("Node/JavaScript project")
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
            if "next" in deps:
                stack.append("Next.js")
            if "react" in deps:
                stack.append("React")
            if "typescript" in deps or (root / "tsconfig.json").exists():
                stack.append("TypeScript")
            if "tailwindcss" in deps:
                stack.append("Tailwind CSS")
            if "@playwright/test" in deps:
                stack.append("Playwright")
            if "@supabase/supabase-js" in deps:
                stack.append("Supabase")
        except Exception:
            pass
    if (root / "pyproject.toml").exists():
        stack.append("Python")
    if (root / "go.mod").exists():
        stack.append("Go")
    if (root / "Cargo.toml").exists():
        stack.append("Rust")
    if (root / "Dockerfile").exists():
        stack.append("Docker")
    return sorted(set(stack))


def extract_purpose(root: Path) -> str:
    for name in ["README.md", "readme.md", "PRD.md"]:
        path = root / name
        if path.exists():
            text = read_text(path, TEXT_LIMIT)
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if lines:
                return "\n".join(lines[:8])
    return "No README or PRD summary found. Fill this in manually."


def summarize_agent_guidance(root: Path) -> str:
    parts: list[str] = []
    for name in ["AGENTS.md", "CLAUDE.md"]:
        path = root / name
        if path.exists():
            parts.append(f"### {name}\n\n" + read_text(path, 1200))
    return "\n\n".join(parts) if parts else "No AGENTS.md or CLAUDE.md found."


def important_docs(root: Path) -> list[str]:
    candidates = [
        "README.md",
        "PRD.md",
        "AGENTS.md",
        "CLAUDE.md",
        "docs/workflow/feature-workflow.md",
        "docs/ops/infra-playbook.md",
    ]
    docs = [item for item in candidates if (root / item).exists()]
    docs.extend(str(path) for path in sorted((root / "docs").glob("*.md"))[:8] if str(path.relative_to(root)) not in docs)
    return docs


def collect_repo_facts(root: Path) -> RepoFacts:
    return RepoFacts(
        root=root,
        name=root.name,
        branch=run(["git", "branch", "--show-current"], root) or "unknown",
        remote_url=run(["git", "remote", "get-url", "origin"], root),
        purpose=extract_purpose(root),
        stack=detect_stack(root),
        commands=detect_package_commands(root),
        agent_guidance=summarize_agent_guidance(root),
        important_docs=important_docs(root),
        status_short=run(["git", "status", "--short"], root),
        diff_stat=run(["git", "diff", "--stat"], root),
    )


def ensure_gitignore(root: Path) -> bool:
    gitignore = root / ".gitignore"
    existing = read_text(gitignore)
    lines = [line.strip() for line in existing.splitlines()]
    if ".agent-harness/" in lines or ".agent-harness" in lines:
        return False
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    with gitignore.open("a", encoding="utf-8") as fh:
        fh.write(prefix + ".agent-harness/\n")
    return True


def ensure_harness(root: Path, *, overwrite: bool = False) -> dict[str, Any]:
    facts = collect_repo_facts(root)
    harness = root / HARNESS_DIR
    tasks = harness / "tasks"
    tasks.mkdir(parents=True, exist_ok=True)

    values = {
        "repo_name": facts.name,
        "source_repo_root": str(facts.root),
        "git_branch": facts.branch,
        "remote_url": facts.remote_url or "none",
        "tmp_root": str(DEFAULT_TMP_ROOT),
        "purpose": facts.purpose,
        "detected_stack_yaml": yaml_list(facts.stack),
        "detected_stack_bullets": bullets(facts.stack),
        "commands_yaml": yaml_map(facts.commands),
        "commands_bullets": bullets([f"`{k}`: `{v}`" for k, v in facts.commands.items()]),
        "agent_guidance": facts.agent_guidance,
        "important_docs": bullets([f"`{item}`" for item in facts.important_docs]),
        "created_at": now(),
    }
    outputs = {
        harness / "config.yaml": render("config.yaml.tmpl", values),
        harness / "repo-profile.md": render("repo-profile.md.tmpl", values),
    }
    for path, content in outputs.items():
        if overwrite or not path.exists():
            path.write_text(content, encoding="utf-8")

    current = harness / "current"
    if not current.exists():
        current.write_text("", encoding="utf-8")

    gitignore_updated = ensure_gitignore(root)
    return {
        "source_repo_root": str(root),
        "harness_dir": str(harness),
        "created_or_updated": [str(path.relative_to(root)) for path in outputs],
        "gitignore_updated": gitignore_updated,
    }


def validate_artifact(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"Artifact not found: {path}")
    if path.is_file() and path.stat().st_size > 5 * 1024 * 1024:
        raise SystemExit(f"Artifact too large to import safely: {path}")
    if path.is_file():
        text = read_text(path, 300_000)
        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(text):
                raise SystemExit(f"Artifact looks sensitive; refusing to copy: {path}")


def copy_artifacts(paths: list[str], task_dir: Path) -> str:
    if not paths:
        return "- None"
    dest_root = task_dir / "artifacts"
    dest_root.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for raw in paths:
        src = Path(raw).expanduser().resolve()
        validate_artifact(src)
        dest = dest_root / src.name
        if src.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__"))
        else:
            shutil.copy2(src, dest)
        lines.append(f"- `{src}` -> `artifacts/{dest.name}`")
    return "\n".join(lines)


def write_patch_files(root: Path, task_dir: Path, capture_patch: bool) -> tuple[str, str]:
    if not capture_patch:
        return "- Patch capture not requested.", ""
    artifact_dir = task_dir / "artifacts"
    artifact_dir.mkdir(exist_ok=True)
    worktree_patch = artifact_dir / "source-working-tree.patch"
    staged_patch = artifact_dir / "source-staged.patch"
    worktree = run(["git", "diff", "--binary"], root)
    staged = run(["git", "diff", "--cached", "--binary"], root)
    worktree_patch.write_text(worktree + ("\n" if worktree else ""), encoding="utf-8")
    staged_patch.write_text(staged + ("\n" if staged else ""), encoding="utf-8")
    lines = [
        f"- Working tree patch: `artifacts/{worktree_patch.name}` ({len(worktree)} bytes)",
        f"- Staged patch: `artifacts/{staged_patch.name}` ({len(staged)} bytes)",
    ]
    return "\n".join(lines), str(worktree_patch if worktree else "")


def default_task_branch(source_branch: str, task_id: str) -> str:
    if source_branch and source_branch not in MAIN_BRANCHES:
        return source_branch
    return f"agent-harness/{task_id}"


def launch_command(agent: str) -> str:
    if agent == "claude":
        return 'claude "$(cat launch-prompt.md)"'
    return 'codex "$(cat launch-prompt.md)"'


def launch_iterm(task_dir: Path, agent: str) -> None:
    command = f"cd {shell_quote(str(task_dir))} && {launch_command(agent)}"
    script = f'''
tell application "iTerm2"
  activate
  if (count of windows) = 0 then
    create window with default profile
  end if
  tell current window
    create tab with default profile
    tell current session
      write text {json.dumps(command)}
    end tell
  end tell
end tell
'''
    subprocess.run(["osascript", "-e", script], check=True)


def start_task(
    root: Path,
    *,
    title: str,
    brief: str,
    owner: str,
    task_id: str | None,
    branch: str | None,
    agent: str,
    capture_patch: bool,
    artifacts: list[str],
    launch: str,
) -> dict[str, Any]:
    ensure_harness(root)
    facts = collect_repo_facts(root)
    created_at = now()
    tid = task_id or f"task-{datetime.now().strftime('%Y%m%d')}-{slugify(title)}"
    task_dir = root / HARNESS_DIR / "tasks" / tid
    if task_dir.exists():
        raise SystemExit(f"Task already exists: {task_dir}")
    task_dir.mkdir(parents=True)
    (task_dir / "artifacts").mkdir()

    task_branch = branch or default_task_branch(facts.branch, tid)
    clone_dir = DEFAULT_TMP_ROOT / tid / facts.name
    artifact_block = copy_artifacts(artifacts, task_dir)
    patch_block, patch_file = write_patch_files(root, task_dir, capture_patch)
    rel = str(task_dir.relative_to(root))
    clone_cmd = f"python3 {shell_quote(str(Path(__file__).resolve()))} clone --task-dir ."
    task_json = {
        "version": 1,
        "task_id": tid,
        "title": title,
        "created_at": created_at,
        "source_repo_root": str(root),
        "source_repo_name": facts.name,
        "source_branch": facts.branch,
        "source_remote_url": facts.remote_url,
        "task_branch": task_branch,
        "task_workspace": str(task_dir),
        "worktree_repo": str(clone_dir),
        "clone_source": str(root),
        "capture_patch": capture_patch,
        "patch_file": patch_file,
        "agent": agent,
    }
    (task_dir / "task.json").write_text(json.dumps(task_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    values = {
        "title": title,
        "brief": brief.strip() or title,
        "created_at": created_at,
        "source_repo_root": str(root),
        "source_repo_name": facts.name,
        "source_branch": facts.branch,
        "source_remote_url": facts.remote_url or "none",
        "source_status": fenced(facts.status_short),
        "source_diff_stat": fenced(facts.diff_stat),
        "task_dir": str(task_dir),
        "task_dir_rel": rel,
        "task_id": tid,
        "task_branch": task_branch,
        "worktree_repo": str(clone_dir),
        "clone_command": clone_cmd,
        "launch_command": launch_command(agent),
        "script_path": str(Path(__file__).resolve()),
        "owner": owner,
        "artifact_block": artifact_block,
        "patch_block": patch_block,
    }
    files = {
        "AGENTS.md": "AGENTS.md.tmpl",
        "CLAUDE.md": "CLAUDE.md.tmpl",
        "goal.md": "goal.md.tmpl",
        "context.md": "context.md.tmpl",
        "status.md": "status.md.tmpl",
        "decisions.md": "decisions.md.tmpl",
        "open-questions.md": "open-questions.md.tmpl",
        "source-repo.md": "source-repo.md.tmpl",
        "launch-prompt.md": "launch-prompt.md.tmpl",
        "worktree.md": "worktree.md.tmpl",
        "owner.json": "owner.json.tmpl",
    }
    for filename, template in files.items():
        (task_dir / filename).write_text(render(template, values), encoding="utf-8")
    (root / HARNESS_DIR / "current").write_text(tid + "\n", encoding="utf-8")

    did_launch = False
    if launch == "iterm":
        launch_iterm(task_dir, agent)
        did_launch = True

    return {
        "source_repo_root": str(root),
        "task_id": tid,
        "task_workspace": str(task_dir),
        "worktree_repo": str(clone_dir),
        "task_branch": task_branch,
        "agent": agent,
        "launch_command": f"cd {shell_quote(str(task_dir))} && {launch_command(agent)}",
        "launched": did_launch,
        "current_session_action": "final_reply_then_stop_if_launched" if did_launch else "handoff_ready",
    }


def read_task_json(task_dir: Path) -> dict[str, Any]:
    path = task_dir / "task.json"
    if not path.exists():
        raise SystemExit(f"task.json not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def checkout_branch(repo: Path, branch: str, base_branch: str) -> None:
    exists = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=str(repo)).returncode == 0
    if exists:
        run(["git", "checkout", branch], repo, check=True)
        return
    if base_branch:
        run(["git", "checkout", base_branch], repo)
    run(["git", "checkout", "-b", branch], repo, check=True)


def clone_task(task_dir: Path, apply_patch: bool) -> dict[str, Any]:
    task = read_task_json(task_dir)
    clone_dir = Path(task["worktree_repo"])
    if clone_dir.exists():
        return {
            "worktree_repo": str(clone_dir),
            "status": "already_exists",
            "next": f"cd {shell_quote(str(clone_dir))}",
        }
    clone_dir.parent.mkdir(parents=True, exist_ok=True)
    clone_source = task.get("clone_source") or task.get("source_remote_url") or task["source_repo_root"]
    run(["git", "clone", "--no-tags", clone_source, str(clone_dir)], task_dir, check=True)
    checkout_branch(clone_dir, task["task_branch"], task.get("source_branch", ""))
    applied: list[str] = []
    if apply_patch and task.get("capture_patch") and task.get("patch_file"):
        patch_file = Path(task["patch_file"])
        if patch_file.exists() and patch_file.stat().st_size > 0:
            run(["git", "apply", str(patch_file)], clone_dir, check=True)
            applied.append(str(patch_file))
    status_text = run(["git", "status", "--short"], clone_dir)
    worktree_md = task_dir / "worktree.md"
    with worktree_md.open("a", encoding="utf-8") as fh:
        fh.write(
            f"\n## Prepared - {now()}\n\n"
            f"- Worktree repo: `{clone_dir}`\n"
            f"- Branch: `{task['task_branch']}`\n"
            f"- Applied patches: {', '.join(applied) if applied else 'none'}\n\n"
            f"```text\n{status_text or 'clean'}\n```\n"
        )
    return {
        "worktree_repo": str(clone_dir),
        "status": "created",
        "branch": task["task_branch"],
        "applied_patches": applied,
        "next": f"cd {shell_quote(str(clone_dir))}",
    }


def status(root: Path) -> dict[str, Any]:
    harness = root / HARNESS_DIR
    current_file = harness / "current"
    current = current_file.read_text(encoding="utf-8").strip() if current_file.exists() else ""
    tasks_root = harness / "tasks"
    tasks = sorted(path.name for path in tasks_root.iterdir() if path.is_dir()) if tasks_root.exists() else []
    return {
        "source_repo_root": str(root),
        "harness_exists": harness.exists(),
        "current_task": current or None,
        "tasks": tasks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent Harness repo task workspace manager")
    parser.add_argument("--repo", default=".", help="Source repository root or any path inside it")
    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser("init", help="Initialize .agent-harness for a source repo")
    init_p.add_argument("--overwrite", action="store_true", help="Refresh config and repo profile")

    start_p = sub.add_parser("start", help="Create a task workspace under .agent-harness/tasks")
    start_p.add_argument("--title", required=True)
    start_p.add_argument("--brief", default="")
    start_p.add_argument("--owner", default=os.environ.get("USER", "agent"))
    start_p.add_argument("--task-id")
    start_p.add_argument("--branch", help="Task branch for the /tmp clone. Defaults to current non-main branch or agent-harness/<task-id>.")
    start_p.add_argument("--agent", choices=["codex", "claude"], default="codex")
    start_p.add_argument("--capture-patch", action="store_true", help="Capture current uncommitted diff into task artifacts for later application.")
    start_p.add_argument("--artifact", action="append", default=[], help="Explicit artifact file or directory to copy into the task workspace.")
    start_p.add_argument("--launch", choices=["none", "iterm"], default="none", help="Optionally launch a new session. Default only prints the launch command.")

    clone_p = sub.add_parser("clone", help="Prepare the /tmp code clone for a task workspace")
    clone_p.add_argument("--task-dir", default=".", help="Task workspace directory. Defaults to current directory.")
    clone_p.add_argument("--no-apply-patch", action="store_true", help="Do not apply captured patch artifacts.")

    sub.add_parser("status", help="Show harness status for the source repo")

    args = parser.parse_args()
    if args.command == "clone":
        result = clone_task(Path(args.task_dir).expanduser().resolve(), apply_patch=not args.no_apply_patch)
    else:
        root = find_repo_root(Path(args.repo).expanduser())
        if args.command == "init":
            result = ensure_harness(root, overwrite=args.overwrite)
        elif args.command == "start":
            result = start_task(
                root,
                title=args.title,
                brief=args.brief,
                owner=args.owner,
                task_id=args.task_id,
                branch=args.branch,
                agent=args.agent,
                capture_patch=args.capture_patch,
                artifacts=args.artifact,
                launch=args.launch,
            )
        elif args.command == "status":
            result = status(root)
        else:
            raise AssertionError(args.command)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
