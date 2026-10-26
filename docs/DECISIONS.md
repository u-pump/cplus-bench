# Decisions

## BENCH-10: One result per case and agent

Each case keeps its frozen source metadata in `case.yaml`. Each agent gets its own immutable first patch and run metadata under `agents/<agent-id>/`, with a separate public verifier report under `results/<id>/<agent-id>.md`. Existing Codex patches and reports are moved byte-for-byte. This permits a second agent on the same frozen input without overwriting the original evidence.

## BENCH-10 review: sandboxed Claude commands and immutable reports

Claude Code attempts run only under its Linux/WSL2 Bash sandbox with an empty strict network allowlist, no unsandboxed retry, and a required seccomp filter on WSL2. Sandbox availability is a startup gate; a successful Bash result is required before recording an attempt. Native Windows cannot run this agent. The CLI process, file tools, and host files readable by sandboxed commands remain outside the Bash boundary, and are disclosed in run metadata.

CI selects changed `(case, agent)` pairs from patch and metadata content. A byte-identical patch rename alone does not select a pair. A report with the same patch SHA-256 and verifier revision is retained unchanged. The ten preexisting Codex reports receive only a `Patch: sha256 <hash>` line; their verdicts, checks, elapsed times, and dates are unchanged. Explicit workflow dispatch selections override this cache.
