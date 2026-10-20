# cplus-bench

AI agents attempt to fix real C/C++ bugs from open-source projects. An independent, closed-source verifier, `cplus`, checks each patch against the project's own reference test, which the agent never saw.

## Results

| Case | Project | Bug | Agent | Verdict | Report |
| --- | --- | --- | --- | --- | --- |
| cpp-peglib-121 | [cpp-peglib](https://github.com/yhirose/cpp-peglib) | [#121: start rule with ignore operator](https://github.com/yhirose/cpp-peglib/issues/121) | Codex CLI 0.163.0 (`gpt-6-sol`) | REJECTED | [Result](results/cpp-peglib-121.md) |
| fmt-4800 | [fmt](https://github.com/fmtlib/fmt) | [#4800: positional width and precision](https://github.com/fmtlib/fmt/pull/4800) | Codex CLI 0.163.0 (`gpt-6-sol`) | VERIFIED | [Result](results/fmt-4800.md) |

## How to read a verdict

- **VERIFIED:** The reference test fails on the broken base, passes with the agent patch, and fails again after the agent's source changes are reverted; required checks pass.
- **REJECTED:** The patch fails a required check, such as fixing the reference test or preserving existing tests.
- **NOT_VERIFIABLE:** The verifier cannot establish a reliable code verdict from the available evidence.

## Methodology

1. Select an upstream bug and reproduce its reference test on the broken commit.
2. Give the agent only the broken source snapshot and issue text, without the reference test or upstream fix.
3. Preserve the agent's first patch and record its identity and patch hash.
4. Check the complete patch against the upstream reference test and the verifier's other gates; publish the verdict and checks.

See the [full protocol](docs/protocol.md).

Two cases so far; this is not a statistical benchmark. More cases are coming.
