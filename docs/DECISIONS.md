# Decisions

## BENCH-10: One result per case and agent

Each case keeps its frozen source metadata in `case.yaml`. Each agent gets its own immutable first patch and run metadata under `agents/<agent-id>/`, with a separate public verifier report under `results/<id>/<agent-id>.md`. Existing Codex patches and reports are moved byte-for-byte. This permits a second agent on the same frozen input without overwriting the original evidence.
