"""Runnable demo of the Leader-Worker pattern with results written to disk.

Purpose
    Illustrate the harness's anti-broken-telephone rule: each "worker" analyses
    a module under `src/`, writes its full report to
    `progress/explore_<module>.md` and returns **only the path**. Nothing but
    lightweight references travels through the communication channel (stdout
    here, the chat in a real session).

    It is the deterministic, AI-free version of the pattern the real subagents
    in `.claude/agents/` follow.

Who runs it
    A human who wants to understand or demonstrate the pattern, or an agent
    asked for a quick map of `src/`. It is not part of verification: neither
    `init.ps1` / `init.sh` nor any hook calls it.

Parameters
    --src DIR       Folder to analyse (default: src)
    --out DIR       Where to write the reports (default: progress)
    --dry-run       Writes nothing; only lists what it would write

Usage
    python scripts/demo_orchestration.py
    python scripts/demo_orchestration.py --src src --out progress --dry-run

Output
    One line per module with the reference to its report, in the same format a
    subagent returns:  done -> progress/explore_<module>.md

Exit codes
    0  finished fine (even if there were no modules to analyse)
    1  the folder given in --src does not exist
"""
from __future__ import annotations

import argparse
import ast
import os
import sys
from datetime import datetime


def analyze(path: str) -> dict[str, object]:
    """Extracts structural metrics from a Python module without importing it."""
    with open(path, encoding="utf-8") as handle:
        source = handle.read()

    tree = ast.parse(source, filename=path)
    lines = source.splitlines()

    functions: list[str] = []
    classes: list[str] = []
    imports: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            args = [a.arg for a in node.args.args]
            functions.append(f"{node.name}({', '.join(args)})")
        elif isinstance(node, ast.ClassDef):
            bases = [ast.unparse(b) for b in node.bases]
            suffix = f"({', '.join(bases)})" if bases else ""
            classes.append(f"{node.name}{suffix}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])

    return {
        "lines": len(lines),
        "code_lines": len([ln for ln in lines if ln.strip() and not ln.strip().startswith("#")]),
        "docstring": ast.get_docstring(tree) or "",
        "functions": functions,
        "classes": classes,
        "imports": sorted(imports),
    }


def render(module: str, path: str, data: dict[str, object]) -> str:
    """Builds the report in the standard `progress/explore_*.md` format."""
    def bullets(items: list[str]) -> str:
        return "\n".join(f"- `{item}`" for item in items) if items else "_none_"

    return f"""# Exploration — {module}

- **File:** `{path}`
- **Generated:** {datetime.now().isoformat(timespec="seconds")}
- **By:** `scripts/demo_orchestration.py`

## Stated purpose

{data["docstring"].strip() or "_the module has no docstring_"}

## Metrics

| Metric        | Value |
|---------------|-------|
| Total lines   | {data["lines"]} |
| Code lines    | {data["code_lines"]} |
| Functions     | {len(data["functions"])} |
| Classes       | {len(data["classes"])} |

## Functions

{bullets(data["functions"])}

## Classes

{bullets(data["classes"])}

## Dependencies

{bullets(data["imports"])}
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Writes one report per module in src/ and returns only the paths.",
    )
    parser.add_argument("--src", default="src", help="folder to analyse")
    parser.add_argument("--out", default="progress", help="folder to write the reports into")
    parser.add_argument("--dry-run", action="store_true", help="writes nothing, only lists")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.src):
        print(f"[FAIL]  The folder {args.src} does not exist", file=sys.stderr)
        return 1

    modules = sorted(
        name for name in os.listdir(args.src)
        if name.endswith(".py") and name != "__init__.py"
    )

    if not modules:
        print(f"[WARN]  There are no modules to analyse in {args.src}/", file=sys.stderr)
        return 0

    if not args.dry_run:
        os.makedirs(args.out, exist_ok=True)

    for filename in modules:
        module = filename[:-3]
        source_path = os.path.join(args.src, filename)
        report_path = os.path.join(args.out, f"explore_{module}.md").replace(os.sep, "/")

        if not args.dry_run:
            report = render(module, source_path.replace(os.sep, "/"), analyze(source_path))
            with open(report_path, "w", encoding="utf-8") as handle:
                handle.write(report)

        # This is the only thing that goes through the channel: the reference,
        # never the content.
        print(f"done -> {report_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
