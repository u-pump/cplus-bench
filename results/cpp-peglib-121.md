# cpp-peglib-121

Verdict: **REJECTED**

Reason: judged by upstream reference test 'Start rule with ignore operator test'; the patch did not eliminate the expected reproducer failure

Elapsed: 46.8 s

Verifier: cplus fb95bec48fa1d9872b96fd429f50984529e76a86 · 2026-10-24 08:59:26 UTC

Agent: Codex CLI · Version: 0.163.0

| Check | Status |
| --- | --- |
| anti_cheat | PASS |
| build:baseline | PASS |
| repro:baseline | PASS |
| build:patched | PASS |
| repro:patched | FAIL |
| repeat | SKIPPED |
| revert | SKIPPED |
| regression | SKIPPED |
