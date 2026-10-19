# Rejected candidates

These candidates are excluded from the public case set. No agent was run.

| Candidate | Broken base → upstream fix | Reason |
| --- | --- | --- |
| [cpp-peglib #122](https://github.com/yhirose/cpp-peglib/issues/122) | [`d84c2993af4335e2bfb1873ee631cb1eea803d15`](https://github.com/yhirose/cpp-peglib/commit/d84c2993af4335e2bfb1873ee631cb1eea803d15) → [`b3b29ce8f3acf3a32733d930105a17d7b0ba347e`](https://github.com/yhirose/cpp-peglib/commit/b3b29ce8f3acf3a32733d930105a17d7b0ba347e) | Fixed test passed on the broken base (0/20 failures); bug was not reproduced. |
| [cpp-peglib #187](https://github.com/yhirose/cpp-peglib/issues/187) | [`4d67d96d7ace0830549908a6fae9064d74683f5a`](https://github.com/yhirose/cpp-peglib/commit/4d67d96d7ace0830549908a6fae9064d74683f5a) → [`578eec705c3be307e08ef5738fef7e5b03f728ee`](https://github.com/yhirose/cpp-peglib/commit/578eec705c3be307e08ef5738fef7e5b03f728ee) | Build needed a dependency download from a host outside the approved sandbox network allowlist. |
| [fmt #4498](https://github.com/fmtlib/fmt/pull/4498) | [`553ec11ec06fbe0beebfbb45f9dc3c9eabd83d28`](https://github.com/fmtlib/fmt/commit/553ec11ec06fbe0beebfbb45f9dc3c9eabd83d28) → [`35dcc58263d6b55419a5932bd6b0b3029a0a8c00`](https://github.com/fmtlib/fmt/commit/35dcc58263d6b55419a5932bd6b0b3029a0a8c00) | Fix adds a regression assertion inside an existing `TEST`, which `--from-fix` did not recognize as a test to run. |
