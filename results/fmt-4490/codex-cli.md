# fmt-4490

Verdict: **REJECTED**

Reason: judged by upstream reference test 'memory_buffer_test.move_ctor_inline_buffer_non_propagating'; the patch did not eliminate the expected reproducer failure

Elapsed: 23.8 s

Verifier: cplus 81c0fda242fef1daf55d3164e06127d372c81caa · 2026-10-24 14:16:42 UTC

Patch: sha256 226c71b74e16e3ca2cf4d747a095d4343e1d18d5786036a61b95632c350e8cf8
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
