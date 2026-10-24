# cpp-peglib-121

Verdict: **REJECTED**

Reason: judged by upstream reference test 'Start rule with ignore operator test'; the patch did not eliminate the expected reproducer failure

Elapsed: 44.4 s

Verifier: cplus 81c0fda242fef1daf55d3164e06127d372c81caa · 2026-10-24 13:33:39 UTC

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
