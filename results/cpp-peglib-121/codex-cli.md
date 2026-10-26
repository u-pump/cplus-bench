# cpp-peglib-121

Verdict: **REJECTED**

Reason: judged by upstream reference test 'Start rule with ignore operator test'; the patch did not eliminate the expected reproducer failure

Elapsed: 37.7 s

Verifier: cplus 81c0fda242fef1daf55d3164e06127d372c81caa · 2026-10-24 14:16:42 UTC

Patch: sha256 7b922707d7bae0bf112195fda84b00bed24e92c3b7cb8b1c72dca6f5204f3970
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
