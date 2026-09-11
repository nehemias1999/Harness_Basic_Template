#!/usr/bin/env bash
# init.sh — Environment verification and setup (POSIX / WSL / Linux CI)
#
# Purpose    : check the repository is in a healthy state before working and
#              before declaring any feature `done`.
# Who runs it: the agent when STARTING a session, the `Stop` hook (through
#              scripts/harness_hook.py) when closing it, and the reviewer before
#              issuing its verdict. If it fails, the session does not move on.
# Equivalent : ./init.ps1 (canonical on Windows; same output, same exit code).
# Parameters : --quiet  shortens the test output (same as init.ps1's -Quiet).
# Usage      : ./init.sh [--quiet]
# Output     : numbered blocks with [OK] / [WARN] / [FAIL] lines.
# Exit codes : 0 environment ready (warnings do not block) · 1 something to fix.

set -u

# Like init.ps1: the verifier plants itself at the repository root. Without this,
# running it from another directory reported the base files as "missing" instead
# of verifying what had to be verified.
cd "$(dirname "$0")" || exit 1

QUIET=0
for arg in "$@"; do
  case "$arg" in
    --quiet) QUIET=1 ;;
    *) printf "Unknown parameter: %s (only --quiet)\n" "$arg" >&2; exit 1 ;;
  esac
done

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

ok()    { printf "${GREEN}[OK]${NC}    %s\n" "$1"; }
warn()  { printf "${YELLOW}[WARN]${NC}  %s\n" "$1"; }
fail()  { printf "${RED}[FAIL]${NC}  %s\n" "$1"; }

EXIT_CODE=0

echo "── 1. Checking the environment ─────────────────────────"

# Python interpreter: accepts any of the usual names and discards the stubs that
# run nothing (for example the Microsoft Store's `python3` alias, which exists on
# PATH but only prints an install notice).
PY=""
PY_VERSION=""
for candidate in python3 python py; do
  command -v "$candidate" >/dev/null 2>&1 || continue
  probe=$("$candidate" -c 'import sys; print("PYOK", ".".join(map(str, sys.version_info[:3])), int(sys.version_info >= (3, 9)))' 2>/dev/null)
  case "$probe" in
    PYOK*)
      PY="$candidate"
      PY_VERSION=$(echo "$probe" | cut -d" " -f2)
      PY_OK=$(echo "$probe" | cut -d" " -f3)
      break
      ;;
  esac
done

if [ -z "$PY" ]; then
  fail "No runnable Python found (tried python3, python, py)"
  exit 1
fi
ok "Python -> $PY $PY_VERSION"

# Minimum version 3.9 (dataclasses + modern typing syntax)
if [ "$PY_OK" != "1" ]; then
  fail "Python >= 3.9 is required (found $PY_VERSION)"
  exit 1
fi
ok "Compatible Python version"

echo ""
echo "── 2. Checking the harness base files ──────────────────"

for f in AGENTS.md CLAUDE.md CHECKPOINTS.md README.md feature_list.json \
         progress/current.md progress/history.md specs/_req_template.md \
         docs/architecture.md docs/conventions.md docs/verification.md docs/scripts.md; do
  if [ ! -f "$f" ]; then
    fail "Base file missing: $f"
    EXIT_CODE=1
  else
    ok "$f exists"
  fi
done

echo ""
echo "── 3. Checking the project configuration ───────────────"

# Blocking on purpose: an unconfigured harness has no quality criteria (the
# reviewer judges against docs/architecture.md). See docs/scripts.md.
if [ -f "scripts/validate_project_setup.py" ]; then
  if ! $PY scripts/validate_project_setup.py .; then
    EXIT_CODE=1
  fi
else
  fail "scripts/validate_project_setup.py is missing — cannot check the configuration"
  EXIT_CODE=1
fi

echo ""
echo "── 4. Validating feature_list.json ─────────────────────"

if [ -f "scripts/validate_feature_list.py" ]; then
  if ! $PY scripts/validate_feature_list.py feature_list.json; then
    EXIT_CODE=1
  fi
else
  fail "scripts/validate_feature_list.py is missing — cannot validate the scope"
  EXIT_CODE=1
fi

echo ""
echo "── 5. Validating requirements and traceability ─────────"

# Blocking on purpose: approving a requirement is not a "sure" in the chat, it is
# `status: approved` in specs/ plus the feature in `pending`. The same module
# init.ps1 uses. See docs/scripts.md.
if [ -f "scripts/validate_requirements.py" ]; then
  if ! $PY scripts/validate_requirements.py .; then
    EXIT_CODE=1
  fi
else
  fail "scripts/validate_requirements.py is missing — cannot check traceability"
  EXIT_CODE=1
fi

echo ""
echo "── 6. Running tests ────────────────────────────────────"

if [ ! -d "tests" ]; then
  warn "The tests/ folder does not exist yet"
else
  # Count before running: a discover with no tests returns 0 and must not be
  # mistaken for "all green". A freshly instantiated repo warns, it does not fail.
  # The count's exit code is compared rather than its output: if Python prints
  # something before failing, a string comparison would send the verifier off to
  # run tests it could not even discover (init.ps1 already looked at the code).
  if TEST_COUNT=$($PY -c 'import unittest; print(unittest.TestLoader().discover("tests").countTestCases())' 2>/dev/null); then
    :
  else
    TEST_COUNT="-1"
  fi

  if [ "$TEST_COUNT" = "-1" ]; then
    fail "Could not discover the tests (import error in tests/?)"
    EXIT_CODE=1
  elif [ "$TEST_COUNT" = "0" ]; then
    warn "0 tests in tests/ — the harness is not verifying anything yet"
  else
    if [ "$QUIET" -eq 1 ]; then
      TEST_FLAG="-q"
    else
      TEST_FLAG="-v"
    fi
    if $PY -m unittest discover -s tests "$TEST_FLAG" 2>&1; then
      ok "All tests pass ($TEST_COUNT tests)"
    else
      fail "There are broken tests"
      EXIT_CODE=1
    fi
  fi
fi

echo ""
echo "── 7. Summary ──────────────────────────────────────────"

if [ $EXIT_CODE -eq 0 ]; then
  ok "Environment ready. You can start working."
else
  fail "Environment NOT ready. Resolve the failures before moving on."
fi

exit $EXIT_CODE
