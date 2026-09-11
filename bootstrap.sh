#!/usr/bin/env bash
# bootstrap.sh — Instantiates a new project (POSIX / WSL / macOS / Linux)
#
# Purpose    : fill in the template's placeholders and leave the repository in
#              a "project just started" state.
# Who runs it: a human, ONCE, right after copying or cloning the template.
#              It is not on the agent's allow list: instantiating a project
#              empties the scope and deletes the requirements, and that
#              decision is yours.
# Equivalent : ./bootstrap.ps1 (canonical on Windows).
#
# Both are wrappers around scripts/instantiate.py, which is where the logic
# lives. Duplicating it in PowerShell and bash guaranteed they would say
# different things one day — the same reason the validators are Python modules.
#
# Usage      : ./bootstrap.sh --name "my-project" [--description "What it does."]
#                             [--repo <url>] [--template-repo <url>]
#                             [--force] [--reset-git] [--no-git] [--dry-run]
#
#              --repo is YOUR project's repository: it becomes `origin`, and
#              the URL you cloned from is kept as `template`, which is what
#              lets you reset this folder later for the next project.
# Exit codes : 0 instantiated · 1 something missing, or already a project.

set -u

cd "$(dirname "$0")" || exit 1

PY=""
for candidate in python3 python py; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if [ "$($candidate -c 'print("PYOK")' 2>/dev/null)" = "PYOK" ]; then
      PY="$candidate"
      break
    fi
  fi
done

if [ -z "$PY" ]; then
  printf "[FAIL]  No runnable Python found: the harness needs it (see docs/scripts.md)\n" >&2
  exit 1
fi

exec "$PY" scripts/instantiate.py "$@"
