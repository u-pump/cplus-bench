# fmt-4960

Verdict: **REJECTED**

Reason: judged by upstream reference test 'format_test.high_precision_trailing_zeros'; the patch did not eliminate the expected reproducer failure

Elapsed: 31.1 s

Verifier: cplus 81c0fda242fef1daf55d3164e06127d372c81caa · 2026-10-24 14:16:42 UTC

Patch: sha256 de59e2be3977371c892015b82cfd35d6ebcf5ed590c5410db9de14ceb46c4efc
Agent: Codex CLI · Version: 0.164.0

| Check | Status |
| --- | --- |
| anti_cheat | REVIEW |
| build:baseline | PASS |
| repro:baseline | PASS |
| build:patched | PASS |
| repro:patched | FAIL |
| repeat | SKIPPED |
| revert | SKIPPED |
| regression | SKIPPED |
