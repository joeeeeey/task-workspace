#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
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
TEXT_LIMIT = 1800


@dataclass
class RepoFacts:
    root: Path
    name: str
    branch: str
    purpose: str
    stack: list[str]
    commands: dict[str, str]
    agent_guidance: str
    important_docs: list[str]


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def run(cmd: list[str], cwd: Path) -> str:
    try:
        return subprocess.check_output(cmd, cwd=str(cwd), text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


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
            if not lines:
                continue
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
        purpose=extract_purpose(root),
        stack=detect_stack(root),
        commands=detect_package_commands(root),
        agent_guidance=summarize_agent_guidance(root),
        important_docs=important_docs(root),
    )


def ensure_harness(root: Path, *, overwrite: bool = False) -> dict[str, Any]:
    facts = collect_repo_facts(root)
    harness = root / HARNESS_DIR
    tasks = harness / "tasks"
    tasks.mkdir(parents=True, exist_ok=True)

    values = {
        "repo_name": facts.name,
        "repo_root": str(facts.root),
        "git_branch": facts.branch,
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

    return {
        "repo_root": str(root),
        "harness_dir": str(harness),
        "created_or_updated": [str(path.relative_to(root)) for path in outputs],
    }


def start_task(root: Path, title: str, brief: str, owner: str, task_id: str | None) -> dict[str, Any]:
    ensure_harness(root)
    created_at = now()
    tid = task_id or f"task-{datetime.now().strftime('%Y%m%d')}-{slugify(title)}"
    task_dir = root / HARNESS_DIR / "tasks" / tid
    if task_dir.exists():
        raise SystemExit(f"Task already exists: {task_dir}")
    task_dir.mkdir(parents=True)
    rel = str(task_dir.relative_to(root))
    values = {
        "title": title,
        "brief": brief.strip() or title,
        "created_at": created_at,
        "repo_root": str(root),
        "task_dir_rel": rel,
        "task_id": tid,
        "owner": owner,
    }
    files = {
        "goal.md": "goal.md.tmpl",
        "status.md": "status.md.tmpl",
        "decisions.md": "decisions.md.tmpl",
        "open-questions.md": "open-questions.md.tmpl",
        "repo-context.md": "repo-context.md.tmpl",
        "handoff.md": "handoff.md.tmpl",
        "owner.json": "owner.json.tmpl",
    }
    for filename, template in files.items():
        (task_dir / filename).write_text(render(template, values), encoding="utf-8")
    (root / HARNESS_DIR / "current").write_text(tid + "\n", encoding="utf-8")
    return {
        "repo_root": str(root),
        "task_id": tid,
        "task_dir": rel,
        "current_session_action": "continue_from_repo_root",
        "handoff_prompt": f"{rel}/handoff.md",
    }


def status(root: Path) -> dict[str, Any]:
    harness = root / HARNESS_DIR
    current_file = harness / "current"
    current = current_file.read_text(encoding="utf-8").strip() if current_file.exists() else ""
    tasks_root = harness / "tasks"
    tasks = sorted(path.name for path in tasks_root.iterdir() if path.is_dir()) if tasks_root.exists() else []
    return {
        "repo_root": str(root),
        "harness_exists": harness.exists(),
        "current_task": current or None,
        "tasks": tasks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent Harness repo-level task memory")
    parser.add_argument("--repo", default=".", help="Repository root or any path inside it")
    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser("init", help="Initialize .agent-harness for a repo")
    init_p.add_argument("--overwrite", action="store_true", help="Refresh config and repo profile")

    start_p = sub.add_parser("start", help="Start a new persistent task record")
    start_p.add_argument("--title", required=True)
    start_p.add_argument("--brief", default="")
    start_p.add_argument("--owner", default=os.environ.get("USER", "agent"))
    start_p.add_argument("--task-id")

    sub.add_parser("status", help="Show harness status")

    args = parser.parse_args()
    root = find_repo_root(Path(args.repo).expanduser())
    if args.command == "init":
        result = ensure_harness(root, overwrite=args.overwrite)
    elif args.command == "start":
        result = start_task(root, args.title, args.brief, args.owner, args.task_id)
    elif args.command == "status":
        result = status(root)
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
