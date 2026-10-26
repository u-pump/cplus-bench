# fmt-4742

Verdict: **REJECTED**

Reason: judged by upstream reference test 'printf_test.trailing_percent'; the patch did not eliminate the expected reproducer failure

Elapsed: 53.6 s

Verifier: cplus 81c0fda242fef1daf55d3164e06127d372c81caa · 2026-10-24 14:16:42 UTC

Patch: sha256 7885a0e066f0738c4e31ea438ef6a98565b6298d468509fedffcf919c39ddc05
Agent: Codex CLI · Version: 0.164.0

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
