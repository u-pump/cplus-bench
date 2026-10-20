# cpp-peglib-121

Verdict: **REJECTED**

Reason: judged by upstream reference test 'Start rule with ignore operator test'; the patch did not eliminate the expected reproducer failure

Elapsed: 50.7 s

Verifier: cplus e9c5ad9c3c63ac1b5a0a1366a122d17f0f226ab6 · 2026-10-20 17:12:25 UTC

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
