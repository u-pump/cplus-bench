# Rejected candidates

These candidates are excluded from the public case set. No agent was run.

| Candidate | Upstream commits | Reason |
| --- | --- | --- |
| [cpp-peglib #122](https://github.com/yhirose/cpp-peglib/issues/122) | [`d84c2993af4335e2bfb1873ee631cb1eea803d15`](https://github.com/yhirose/cpp-peglib/commit/d84c2993af4335e2bfb1873ee631cb1eea803d15) → [`b3b29ce8f3acf3a32733d930105a17d7b0ba347e`](https://github.com/yhirose/cpp-peglib/commit/b3b29ce8f3acf3a32733d930105a17d7b0ba347e) | Fixed test passed on the broken base (0/20 failures); bug was not reproduced. |
| [cpp-peglib #187](https://github.com/yhirose/cpp-peglib/issues/187) | [`4d67d96d7ace0830549908a6fae9064d74683f5a`](https://github.com/yhirose/cpp-peglib/commit/4d67d96d7ace0830549908a6fae9064d74683f5a) → [`578eec705c3be307e08ef5738fef7e5b03f728ee`](https://github.com/yhirose/cpp-peglib/commit/578eec705c3be307e08ef5738fef7e5b03f728ee) | Build needed a dependency download from a host outside the approved sandbox network allowlist. |
| [fmt #4498](https://github.com/fmtlib/fmt/pull/4498) | [`553ec11ec06fbe0beebfbb45f9dc3c9eabd83d28`](https://github.com/fmtlib/fmt/commit/553ec11ec06fbe0beebfbb45f9dc3c9eabd83d28) → [`35dcc58263d6b55419a5932bd6b0b3029a0a8c00`](https://github.com/fmtlib/fmt/commit/35dcc58263d6b55419a5932bd6b0b3029a0a8c00) | Fix adds a regression assertion inside an existing `TEST`, which `--from-fix` did not recognize as a test to run. |
| [cpp-peglib #266](https://github.com/yhirose/cpp-peglib/pull/266) | [fix](https://github.com/yhirose/cpp-peglib/commit/d8ec5992f63273e9ec35d46b66aea65ad4e1d635) | No 3/3 result; the test build requires a network-fetched dependency. |
| [cJSON #852](https://github.com/DaveGamble/cJSON/pull/852) | [fix](https://github.com/DaveGamble/cJSON/commit/3ef4e4e730e5efd381be612df41e1ff3f5bb3c32) | The added Unity test is not selectable as a standalone reference test. |
| [fmt #4802](https://github.com/fmtlib/fmt/pull/4802) | [fix](https://github.com/fmtlib/fmt/commit/de4c6c502e23cef18da5ed6738bf6612663a9cd2) | The fix adds a check inside an existing test, not a selectable new test. |
| [fmt #3797](https://github.com/fmtlib/fmt/pull/3797) | [fix](https://github.com/fmtlib/fmt/commit/961df829b9a266adda89d3aa403d2625c5161e76) | The added test passed on the broken base (0/3 failures). |
| [BehaviorTree.CPP #1236](https://github.com/BehaviorTree/BehaviorTree.CPP/pull/1236) | [fix](https://github.com/BehaviorTree/BehaviorTree.CPP/commit/3708289638d38d4ebb5da21c4d07e8cf27060f06) | The TSan test build needs dependencies unavailable in the current sandbox. |
| [fmt #4934](https://github.com/fmtlib/fmt/pull/4934) | [fix](https://github.com/fmtlib/fmt/commit/8a7aea04222d6680aae2c69fe8d514ffc2f9808d) | The broken base failed for another reason, not the added test (0/3). |
| [spdlog #3658](https://github.com/gabime/spdlog/pull/3658) | [fix](https://github.com/gabime/spdlog/commit/737325e92366adf7f74b7ff7a13a0fcb19d025b0) | The concurrent test timed out in all three baseline runs. |
