#!/bin/bash
# SessionStart hook for Claude Code on the web.
#
# Sets up an isolated Python virtualenv (.venv) with the project's dependencies
# so the source modules import cleanly and `ruff`/`pytest` work as soon as the
# session starts. A venv is used deliberately: the base image ships several
# apt-installed packages (PyYAML, packaging, pyparsing) that pip cannot
# uninstall to satisfy the pinned versions in requirements.txt, and a venv has
# no system site-packages, so those conflicts never arise. The container
# filesystem is cached after the hook finishes, so this heavy install happens
# once and later sessions start fast.
set -euo pipefail

# Only run in the remote (Claude Code on the web) environment. On a developer's
# own machine we don't want to touch their Python setup / virtualenv.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

VENV="$CLAUDE_PROJECT_DIR/.venv"

# Keep pip non-interactive and quiet, and send its (verbose) output to stderr so
# only the short status lines below land in the session context on stdout.
PIP_FLAGS=(--no-input --disable-pip-version-check --quiet)

if [ ! -x "$VENV/bin/python" ]; then
  echo "[session-start] Creating virtualenv at .venv ..." 1>&2
  python3 -m venv "$VENV"
fi

echo "[session-start] Installing runtime dependencies from requirements.txt ..." 1>&2
"$VENV/bin/python" -m pip install "${PIP_FLAGS[@]}" -r requirements.txt 1>&2

echo "[session-start] Installing dev tools from requirements-dev.txt ..." 1>&2
"$VENV/bin/python" -m pip install "${PIP_FLAGS[@]}" -r requirements-dev.txt 1>&2

# Persist for the rest of the session (idempotent across resume/clear/compact):
#  - put the venv on PATH so python/pip/pytest/ruff resolve to it
#  - put src/ on PYTHONPATH because the scripts import each other flatly
#    (e.g. `from data import ...`), which only works with src/ on the path.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  if ! grep -qsF "$VENV/bin" "$CLAUDE_ENV_FILE" 2>/dev/null; then
    {
      echo "export VIRTUAL_ENV=\"$VENV\""
      echo "export PATH=\"$VENV/bin:\$PATH\""
    } >> "$CLAUDE_ENV_FILE"
  fi
  if ! grep -qsF "$CLAUDE_PROJECT_DIR/src" "$CLAUDE_ENV_FILE" 2>/dev/null; then
    echo "export PYTHONPATH=\"$CLAUDE_PROJECT_DIR/src:\${PYTHONPATH:-}\"" >> "$CLAUDE_ENV_FILE"
  fi
fi

echo "[session-start] Environment ready. Lint with 'ruff check .', test with 'pytest'."
