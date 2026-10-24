# cplus-bench

AI agents attempt to fix real C/C++ bugs from open-source projects. An independent, closed-source verifier, `cplus`, checks each patch against the project's own reference test, which the agent never saw.

## Results

| Case | Project | Bug | Agent | Verdict | Report |
| --- | --- | --- | --- | --- | --- |
| cpp-peglib-121 | [cpp-peglib](https://github.com/yhirose/cpp-peglib) | [#121: start rule with ignore operator](https://github.com/yhirose/cpp-peglib/issues/121) | Codex CLI 0.163.0 (`gpt-6-sol`) | REJECTED | [Result](results/cpp-peglib-121.md) |
| fmt-4490 | [fmt](https://github.com/fmtlib/fmt) | [#4490: allocator move](https://github.com/fmtlib/fmt/pull/4490) | Codex CLI 0.164.0 (`gpt-6-sol`) | REJECTED | [Result](results/fmt-4490.md) |
| fmt-4742 | [fmt](https://github.com/fmtlib/fmt) | [#4742: out-of-bounds read](https://github.com/fmtlib/fmt/pull/4742) | Codex CLI 0.164.0 (`gpt-6-sol`) | REJECTED | [Result](results/fmt-4742.md) |
| fmt-4800 | [fmt](https://github.com/fmtlib/fmt) | [#4800: positional width and precision](https://github.com/fmtlib/fmt/pull/4800) | Codex CLI 0.163.0 (`gpt-6-sol`) | VERIFIED | [Result](results/fmt-4800.md) |
| fmt-4933 | [fmt](https://github.com/fmtlib/fmt) | [#4933: named argument count](https://github.com/fmtlib/fmt/pull/4933) | Codex CLI 0.164.0 (`gpt-6-sol`) | REJECTED | [Result](results/fmt-4933.md) |
| fmt-4942 | [fmt](https://github.com/fmtlib/fmt) | [#4942: zero precision](https://github.com/fmtlib/fmt/pull/4942) | Codex CLI 0.164.0 (`gpt-6-sol`) | VERIFIED | [Result](results/fmt-4942.md) |
| fmt-4960 | [fmt](https://github.com/fmtlib/fmt) | [#4960: floating-point precision](https://github.com/fmtlib/fmt/pull/4960) | Codex CLI 0.164.0 (`gpt-6-sol`) | REJECTED | [Result](results/fmt-4960.md) |
| fmt-4978 | [fmt](https://github.com/fmtlib/fmt) | [#4978: calendar formatting](https://github.com/fmtlib/fmt/pull/4978) | Codex CLI 0.164.0 (`gpt-6-sol`) | VERIFIED | [Result](results/fmt-4978.md) |
| spdlog-3049 | [spdlog](https://github.com/gabime/spdlog) | [#3049: concurrent async flush](https://github.com/gabime/spdlog/pull/3049) | Codex CLI 0.164.0 (`gpt-6-sol`) | REJECTED | [Result](results/spdlog-3049.md) |
| zlibng-2465 | [zlib-ng](https://github.com/zlib-ng/zlib-ng) | [#2465: inflate boundary](https://github.com/zlib-ng/zlib-ng/pull/2465) | Codex CLI 0.164.0 (`gpt-6-sol`) | VERIFIED | [Result](results/zlibng-2465.md) |

4 verified, 6 rejected of 10.

fmt-4960: reference test chosen after the agent run ([see case](cases/fmt-4960/case.yaml)).

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

Small sample, not a statistical benchmark. More cases are coming.
