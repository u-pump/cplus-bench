#!/usr/bin/env bash
set -eu
if [ -z "${CPLUS_READ_TOKEN:-}" ]; then
  echo 'Verifier token missing'
  exit 1
fi
printf '#!/bin/sh\ncase "$1" in *Username*) printf "x-access-token";; *) printf "%%s" "$CPLUS_READ_TOKEN";; esac\n' > "$RUNNER_TEMP/askpass"
chmod 700 "$RUNNER_TEMP/askpass"
trap 'rm -f "$RUNNER_TEMP/askpass"' EXIT
GIT_ASKPASS="$RUNNER_TEMP/askpass" GIT_TERMINAL_PROMPT=0 git clone -q https://github.com/u-pump/c-plus.git "$RUNNER_TEMP/cplus-src" >/dev/null 2>&1 || { echo 'Verifier install failed'; exit 1; }
rm -f "$RUNNER_TEMP/askpass"
git -C "$RUNNER_TEMP/cplus-src" checkout -q --detach 46cd11f >/dev/null 2>&1 || { echo 'Verifier revision unavailable'; exit 1; }
python -m pip install -q "$RUNNER_TEMP/cplus-src" >/dev/null 2>&1 || { echo 'Verifier install failed'; exit 1; }
