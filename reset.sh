#!/usr/bin/env bash
# reset.sh — Returns the workspace to the template and starts another project
#
# Purpose    : one local copy of the harness, many projects, one after another.
#              When a project is finished and pushed to its own repository,
#              this makes the folder identical to the template again and
#              instantiates the next project on top.
# Who runs it: a human. It is on the agent's `deny` list: resetting deletes a
#              project's working copy, and that decision is yours.
# Equivalent : ./reset.ps1 (canonical on Windows).
#
# Both are wrappers around scripts/reset_workspace.py, where the logic lives.
#
# Usage      : ./reset.sh --name "ecommerce" --repo "<url>" [--dry-run]
#              ./reset.sh --name "ecommerce" --repo "<url>" --force
# Exit codes : 0 reset (or simulated) · 1 it refused, and nothing was deleted.

set -u

cd "$(dirname "$0")" || exit 1

# Same >= 3.9 gate as the verifier. Probing only `print("PYOK")` let the most
# destructive script in the harness run under an interpreter init.sh rejects.
PY=""
for candidate in python3 python py; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if [ "$($candidate -c 'import sys; print("PYOK" if sys.version_info >= (3, 9) else "OLD")' 2>/dev/null)" = "PYOK" ]; then
      PY="$candidate"
      break
    fi
  fi
done

if [ -z "$PY" ]; then
  printf "[FAIL]  No runnable Python >= 3.9 found: the harness needs it (see docs/scripts.md)\n" >&2
  exit 1
fi

exec "$PY" scripts/reset_workspace.py "$@"
