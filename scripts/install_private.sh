#!/usr/bin/env bash
set -eu
if [ -z "${CPLUS_READ_TOKEN:-}" ]; then
  echo 'Verifier token missing'
  exit 1
fi
case "${RUNNER_TEMP:-}" in
  /*) ;;
  *) echo 'Runner temp unavailable'; exit 1 ;;
esac
source_dir="$RUNNER_TEMP/cplus-src"
printf '#!/bin/sh\ncase "$1" in *Username*) printf "x-access-token";; *) printf "%%s" "$CPLUS_READ_TOKEN";; esac\n' > "$RUNNER_TEMP/askpass"
chmod 700 "$RUNNER_TEMP/askpass"
trap 'rm -f "$RUNNER_TEMP/askpass"; rm -rf -- "$source_dir"' EXIT
GIT_ASKPASS="$RUNNER_TEMP/askpass" GIT_TERMINAL_PROMPT=0 git clone -q https://github.com/u-pump/c-plus.git "$source_dir" >/dev/null 2>&1 || { echo 'Verifier install failed'; exit 1; }
rm -f "$RUNNER_TEMP/askpass"
git -C "$source_dir" checkout -q --detach e9c5ad9c3c63ac1b5a0a1366a122d17f0f226ab6 >/dev/null 2>&1 || { echo 'Verifier revision unavailable'; exit 1; }
python -m pip install -q "$source_dir" >/dev/null 2>&1 || { echo 'Verifier install failed'; exit 1; }
rm -rf -- "$source_dir"
