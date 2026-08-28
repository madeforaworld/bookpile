#!/usr/bin/env bash
# Everything that must pass before a commit. No arguments, no options.
set -uo pipefail
cd "$(dirname "$0")/.."
fail=0

run() {
  printf '\n\033[1m%s\033[0m\n' "$1"; shift
  "$@" || fail=1
}

run "privacy gate"        node scripts/privacy-check.js
run "safety unit tests"   python3 -m unittest discover -q -s safety/tests -t .
run "reference tests"     python3 -m unittest discover -q -s reference/tests -t .
run "conformance vectors" python3 conformance/runner.py

if [ "$fail" -ne 0 ]; then
  printf '\n\033[31mFAILED\033[0m\n'; exit 1
fi
printf '\n\033[32mall checks passed\033[0m\n'
