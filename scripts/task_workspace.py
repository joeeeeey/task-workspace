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
STATE_DIR = ".task-workspace"
DEFAULT_TMP_ROOT = Path(os.environ.get("TASK_WORKSPACE_TMP_ROOT", "/tmp/task-workspace"))
TEXT_LIMIT = 1800
TRUNK_BRANCHES = {"main", "master", "dev", "develop", "trunk"}
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
    if f"{STATE_DIR}/" in lines or STATE_DIR in lines:
        return False
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    with gitignore.open("a", encoding="utf-8") as fh:
        fh.write(prefix + f"{STATE_DIR}/\n")
    return True


def ensure_workspace(root: Path, *, overwrite: bool = False) -> dict[str, Any]:
    facts = collect_repo_facts(root)
    state_dir = root / STATE_DIR
    tasks = state_dir / "tasks"
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
        state_dir / "config.yaml": render("config.yaml.tmpl", values),
        state_dir / "repo-profile.md": render("repo-profile.md.tmpl", values),
    }
    for path, content in outputs.items():
        if overwrite or not path.exists():
            path.write_text(content, encoding="utf-8")

    current = state_dir / "current"
    if not current.exists():
        current.write_text("", encoding="utf-8")

    gitignore_updated = ensure_gitignore(root)
    return {
        "source_repo_root": str(root),
        "state_dir": str(state_dir),
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
    if source_branch and source_branch != "unknown" and source_branch not in TRUNK_BRANCHES:
        return source_branch
    return f"task-workspace/{task_id}"


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
    code_workspace: str,
    capture_patch: bool,
    artifacts: list[str],
    launch: str,
) -> dict[str, Any]:
    ensure_workspace(root)
    facts = collect_repo_facts(root)
    created_at = now()
    tid = task_id or f"task-{datetime.now().strftime('%Y%m%d')}-{slugify(title)}"
    task_dir = root / STATE_DIR / "tasks" / tid
    if task_dir.exists():
        raise SystemExit(f"Task already exists: {task_dir}")
    task_dir.mkdir(parents=True)
    (task_dir / "artifacts").mkdir()

    task_branch = branch or default_task_branch(facts.branch, tid)
    worktree_dir = DEFAULT_TMP_ROOT / tid / facts.name
    artifact_block = copy_artifacts(artifacts, task_dir)
    patch_block, patch_file = write_patch_files(root, task_dir, capture_patch)
    rel = str(task_dir.relative_to(root))
    prepare_cmd = f"python3 {shell_quote(str(Path(__file__).resolve()))} prepare --task-dir ."
    task_json = {
        "version": 1,
        "task_id": tid,
        "title": title,
        "created_at": created_at,
        "source_repo_name": facts.name,
        "source_branch": facts.branch,
        "source_remote_url": facts.remote_url,
        "task_branch": task_branch,
        "code_workspace": code_workspace,
        "capture_patch": capture_patch,
        "agent": agent,
    }
    local_json = {
        "version": 1,
        "task_id": tid,
        "source_repo_root": str(root),
        "task_workspace": str(task_dir),
        "worktree_repo": str(worktree_dir),
        "clone_source": str(root),
        "patch_file": patch_file,
    }
    (task_dir / "task.json").write_text(json.dumps(task_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (task_dir / "local.json").write_text(json.dumps(local_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
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
        "worktree_repo": str(worktree_dir),
        "code_workspace": code_workspace,
        "prepare_command": prepare_cmd,
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
    (root / STATE_DIR / "current").write_text(tid + "\n", encoding="utf-8")

    did_launch = False
    if launch == "iterm":
        launch_iterm(task_dir, agent)
        did_launch = True

    return {
        "source_repo_root": str(root),
        "task_id": tid,
        "task_workspace": str(task_dir),
        "worktree_repo": str(worktree_dir),
        "task_branch": task_branch,
        "code_workspace": code_workspace,
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


def infer_source_root_from_task_dir(task_dir: Path) -> Path | None:
    if task_dir.parent.name == "tasks" and task_dir.parent.parent.name == STATE_DIR:
        return task_dir.parent.parent.parent.resolve()
    return None


def default_local_json(task_dir: Path, task: dict[str, Any]) -> dict[str, Any]:
    task_id = task["task_id"]
    source_root = infer_source_root_from_task_dir(task_dir)
    source_repo_name = task.get("source_repo_name") or (source_root.name if source_root else "repo")
    worktree_repo = DEFAULT_TMP_ROOT / task_id / source_repo_name
    clone_source = str(source_root) if source_root and source_root.exists() else task.get("source_remote_url", "")
    return {
        "version": 1,
        "task_id": task_id,
        "source_repo_root": str(source_root) if source_root else "",
        "task_workspace": str(task_dir),
        "worktree_repo": str(worktree_repo),
        "clone_source": clone_source,
        "patch_file": "",
        "generated_from_task_json": True,
        "generated_at": now(),
    }


def read_local_json(task_dir: Path, task: dict[str, Any]) -> dict[str, Any]:
    path = task_dir / "local.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    data = default_local_json(task_dir, task)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return data


def checkout_branch(repo: Path, branch: str, base_branch: str) -> None:
    exists = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=str(repo)).returncode == 0
    if exists:
        run(["git", "checkout", branch], repo, check=True)
        return
    if base_branch:
        run(["git", "checkout", base_branch], repo)
    run(["git", "checkout", "-b", branch], repo, check=True)


def can_use_worktree(source_repo: Path) -> bool:
    if not source_repo.exists():
        return False
    return bool(run(["git", "rev-parse", "--git-dir"], source_repo))


def prepare_with_worktree(source_repo: Path, worktree_dir: Path, branch: str, base_branch: str) -> str:
    if worktree_dir.exists():
        return "already_exists"
    worktree_dir.parent.mkdir(parents=True, exist_ok=True)
    branch_exists = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=str(source_repo)).returncode == 0
    if branch_exists:
        run(["git", "worktree", "add", "--force", str(worktree_dir), branch], source_repo, check=True)
    else:
        base = base_branch if base_branch and base_branch != "unknown" else "HEAD"
        run(["git", "worktree", "add", "-b", branch, str(worktree_dir), base], source_repo, check=True)
    return "created"


def prepare_with_clone(task_dir: Path, source: str, worktree_dir: Path, branch: str, base_branch: str) -> str:
    if worktree_dir.exists():
        return "already_exists"
    worktree_dir.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", "--no-tags", source, str(worktree_dir)], task_dir, check=True)
    checkout_branch(worktree_dir, branch, base_branch)
    return "created"


def prepare_task(task_dir: Path, apply_patch: bool, mode: str | None = None) -> dict[str, Any]:
    task = read_task_json(task_dir)
    local = read_local_json(task_dir, task)
    worktree_dir = Path(local["worktree_repo"])
    source_repo = Path(local["source_repo_root"])
    requested = mode or task.get("code_workspace", "auto")
    used_mode = requested
    if requested == "auto":
        used_mode = "worktree" if can_use_worktree(source_repo) else "clone"
    if used_mode == "worktree":
        if not can_use_worktree(source_repo):
            raise SystemExit(f"Cannot create git worktree from source repo: {source_repo}")
        created_status = prepare_with_worktree(source_repo, worktree_dir, task["task_branch"], task.get("source_branch", ""))
    elif used_mode == "clone":
        clone_source = local.get("clone_source") or task.get("source_remote_url") or str(source_repo)
        if Path(clone_source).expanduser().exists() is False and task.get("source_remote_url"):
            clone_source = task["source_remote_url"]
        created_status = prepare_with_clone(task_dir, clone_source, worktree_dir, task["task_branch"], task.get("source_branch", ""))
    else:
        raise SystemExit(f"Unsupported code workspace mode: {used_mode}")
    applied: list[str] = []
    if created_status == "created" and apply_patch and task.get("capture_patch") and local.get("patch_file"):
        patch_file = Path(local["patch_file"])
        if patch_file.exists() and patch_file.stat().st_size > 0:
            run(["git", "apply", str(patch_file)], worktree_dir, check=True)
            applied.append(str(patch_file))
    status_text = run(["git", "status", "--short"], worktree_dir)
    worktree_md = task_dir / "worktree.md"
    with worktree_md.open("a", encoding="utf-8") as fh:
        fh.write(
            f"\n## Prepared - {now()}\n\n"
            f"- Worktree repo: `{worktree_dir}`\n"
            f"- Code workspace mode: `{used_mode}`\n"
            f"- Branch: `{task['task_branch']}`\n"
            f"- Applied patches: {', '.join(applied) if applied else 'none'}\n\n"
            f"```text\n{status_text or 'clean'}\n```\n"
        )
    return {
        "worktree_repo": str(worktree_dir),
        "status": created_status,
        "code_workspace": used_mode,
        "branch": task["task_branch"],
        "applied_patches": applied,
        "next": f"cd {shell_quote(str(worktree_dir))}",
    }


def remove_state_dir_from_root_gitignore(root: Path) -> bool:
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        return False
    original = gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
    filtered = [line for line in original if line.strip() not in {STATE_DIR, f"{STATE_DIR}/"}]
    if filtered == original:
        return False
    gitignore.write_text("\n".join(filtered).rstrip() + ("\n" if filtered else ""), encoding="utf-8")
    return True


def ensure_share_gitignore(root: Path, task_id: str | None = None) -> Path:
    state_dir = root / STATE_DIR
    state_dir.mkdir(parents=True, exist_ok=True)
    gitignore = state_dir / ".gitignore"
    task_scope = ""
    if task_id:
        task_scope = f"""# Only expose the selected task record.
tasks/*
!tasks/{task_id}/
!tasks/{task_id}/**

"""
    content = f"""{task_scope}# Machine-local Task Workspace state
current
tasks/*/local.json
tasks/*/owner.json

# Imported or generated task artifacts can be large or sensitive.
tasks/*/artifacts/
tasks/*/logs/
tasks/*/local/
tasks/*/*.patch
tasks/*/*.diff

# Runtime/cache files
**/.DS_Store
**/__pycache__/
**/*.pyc
"""
    gitignore.write_text(content, encoding="utf-8")
    return gitignore


def share(root: Path, task_id: str | None = None) -> dict[str, Any]:
    ensure_workspace(root)
    root_gitignore_changed = remove_state_dir_from_root_gitignore(root)
    state_gitignore = ensure_share_gitignore(root, task_id=task_id)
    state_dir = root / STATE_DIR
    add_targets = [
        str((state_dir / ".gitignore").relative_to(root)),
        str((state_dir / "config.yaml").relative_to(root)),
        str((state_dir / "repo-profile.md").relative_to(root)),
    ]
    if task_id:
        task_dir = state_dir / "tasks" / task_id
        if not task_dir.exists():
            raise SystemExit(f"Task not found: {task_dir}")
        add_targets.append(str(task_dir.relative_to(root)))
    else:
        tasks_dir = state_dir / "tasks"
        if tasks_dir.exists():
            add_targets.append(str(tasks_dir.relative_to(root)))
    return {
        "source_repo_root": str(root),
        "state_dir": str(state_dir),
        "root_gitignore_changed": root_gitignore_changed,
        "share_gitignore": str(state_gitignore),
        "safe_to_commit": [
            "config.yaml",
            "repo-profile.md",
            "task.json",
            "goal/context/status/decisions/open-questions/source-repo/worktree/launch-prompt",
            "task-local AGENTS.md and CLAUDE.md",
        ],
        "kept_local": [
            "current",
            "tasks/*/local.json",
            "tasks/*/owner.json",
            "tasks/*/artifacts/",
            "tasks/*/logs/",
            "tasks/*/local/",
        ],
        "suggested_git_add": add_targets,
    }


def status(root: Path) -> dict[str, Any]:
    state_dir = root / STATE_DIR
    current_file = state_dir / "current"
    current = current_file.read_text(encoding="utf-8").strip() if current_file.exists() else ""
    tasks_root = state_dir / "tasks"
    tasks = sorted(path.name for path in tasks_root.iterdir() if path.is_dir()) if tasks_root.exists() else []
    return {
        "source_repo_root": str(root),
        "state_exists": state_dir.exists(),
        "current_task": current or None,
        "tasks": tasks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Task Workspace repo task manager")
    parser.add_argument("--repo", default=".", help="Source repository root or any path inside it")
    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser("init", help=f"Initialize {STATE_DIR} for a source repo")
    init_p.add_argument("--overwrite", action="store_true", help="Refresh config and repo profile")

    start_p = sub.add_parser("start", help=f"Create a task workspace under {STATE_DIR}/tasks")
    start_p.add_argument("--title", required=True)
    start_p.add_argument("--brief", default="")
    start_p.add_argument("--owner", default=os.environ.get("USER", "agent"))
    start_p.add_argument("--task-id")
    start_p.add_argument("--branch", help="Task branch for the /tmp code workspace. Defaults to task-workspace/<task-id>.")
    start_p.add_argument("--agent", choices=["codex", "claude"], default="codex")
    start_p.add_argument(
        "--code-workspace",
        choices=["auto", "worktree", "clone"],
        default="auto",
        help="How to prepare the /tmp code workspace. Default auto uses git worktree when possible, with clone fallback.",
    )
    start_p.add_argument("--capture-patch", action="store_true", help="Capture current uncommitted diff into task artifacts for later application.")
    start_p.add_argument("--artifact", action="append", default=[], help="Explicit artifact file or directory to copy into the task workspace.")
    start_p.add_argument("--launch", choices=["none", "iterm"], default="none", help="Optionally launch a new session. Default only prints the launch command.")

    prepare_p = sub.add_parser("prepare", help="Prepare the /tmp code workspace for a task")
    prepare_p.add_argument("--task-dir", default=".", help="Task workspace directory. Defaults to current directory.")
    prepare_p.add_argument("--no-apply-patch", action="store_true", help="Do not apply captured patch artifacts.")
    prepare_p.add_argument("--code-workspace", choices=["auto", "worktree", "clone"], help="Override the task's code workspace mode.")

    clone_p = sub.add_parser("clone", help="Compatibility alias for prepare --code-workspace clone")
    clone_p.add_argument("--task-dir", default=".", help="Task workspace directory. Defaults to current directory.")
    clone_p.add_argument("--no-apply-patch", action="store_true", help="Do not apply captured patch artifacts.")

    share_p = sub.add_parser("share", help=f"Make {STATE_DIR} safe to commit by ignoring local task state")
    share_p.add_argument("--task-id", help="Limit suggested git add target to one task.")

    sub.add_parser("status", help="Show Task Workspace status for the source repo")

    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare_task(
            Path(args.task_dir).expanduser().resolve(),
            apply_patch=not args.no_apply_patch,
            mode=args.code_workspace,
        )
    elif args.command == "clone":
        result = prepare_task(
            Path(args.task_dir).expanduser().resolve(),
            apply_patch=not args.no_apply_patch,
            mode="clone",
        )
    else:
        root = find_repo_root(Path(args.repo).expanduser())
        if args.command == "init":
            result = ensure_workspace(root, overwrite=args.overwrite)
        elif args.command == "start":
            result = start_task(
                root,
                title=args.title,
                brief=args.brief,
                owner=args.owner,
                task_id=args.task_id,
                branch=args.branch,
                agent=args.agent,
                code_workspace=args.code_workspace,
                capture_patch=args.capture_patch,
                artifacts=args.artifact,
                launch=args.launch,
            )
        elif args.command == "share":
            result = share(root, task_id=args.task_id)
        elif args.command == "status":
            result = status(root)
        else:
            raise AssertionError(args.command)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
