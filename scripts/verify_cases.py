"""Run private cplus and publish only a small allowlisted summary."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMP = Path(os.environ.get("RUNNER_TEMP", str(ROOT / ".tmp")))
GATES = (
    "anti_cheat",
    "build:baseline",
    "repro:baseline",
    "build:patched",
    "repro:patched",
    "repeat",
    "revert",
    "regression",
)
STATUSES = {"PASS", "FAIL", "ERROR", "REVIEW", "SKIPPED"}
VERDICTS = {"VERIFIED", "REJECTED", "REVIEW", "NOT_VERIFIABLE", "ERROR"}
VERIFIER_REVISION = "e9c5ad9c3c63ac1b5a0a1366a122d17f0f226ab6"


def quiet(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)


def selected_cases() -> list[str]:
    explicit = os.environ.get("SELECT_CASE", "").strip()
    if explicit:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", explicit):
            raise ValueError("Invalid case ID")
        return [explicit]
    before = os.environ.get("BEFORE_SHA", "")
    head = os.environ.get("HEAD_SHA", "")
    if before and before != "0" * 40 and head:
        diff = quiet("git", "diff", "--name-only", before, head, "--", "cases/", cwd=ROOT)
        if diff.returncode == 0:
            return sorted({part[1] for line in diff.stdout.splitlines()
                           if (part := line.split("/")) and len(part) >= 3})
    return sorted(path.name for path in (ROOT / "cases").iterdir() if path.is_dir())


def extract_json(output: str) -> dict[str, object]:
    decoder = json.JSONDecoder()
    for match in re.finditer(r'\{\s*"schema_version"\s*:', output):
        try:
            value, _ = decoder.raw_decode(output[match.start():])
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass
    raise ValueError("No verifier result")


def agent_identity(case_id: str) -> tuple[str, str]:
    case = json.loads((ROOT / "cases" / case_id / "case.yaml").read_text(encoding="utf-8"))
    agent = case.get("agent") or {}
    if not isinstance(agent, dict):
        raise ValueError("Invalid agent metadata")
    name = str(agent.get("name") or "not run").replace("\n", " ").replace("\r", " ")
    version = str(agent.get("version") or "not recorded").replace("\n", " ").replace("\r", " ")
    return name, version


def gate_reason(gate: dict[str, object]) -> str:
    name = str(gate["name"])
    evidence = gate.get("evidence")
    raw = evidence.get("reason") if isinstance(evidence, dict) else None
    if not isinstance(raw, str) or not raw.strip():
        return f"{name}: failed"
    first_line = raw.splitlines()[0].strip()
    # The gate's reason is public, but checkout locations and raw logs are not.
    without_paths = re.sub(r"(?<!\w)(?:[A-Za-z]:[\\/]|/(?!/))\S+", "[path]", first_line)
    return " ".join(without_paths.split())[:240] or f"{name}: failed"


def summary_reason(raw: object, fallback: str) -> str:
    """Publish a short verifier summary, never a path or raw diagnostic log."""
    if not isinstance(raw, str) or not raw.strip():
        return fallback
    first_line = " ".join(raw.splitlines()[0].split())
    if (
        not first_line
        or len(first_line) > 240
        or re.search(r"[\\/]|\b(?:traceback|stdout|stderr|log)\b", first_line, re.I)
    ):
        return fallback
    return first_line


def render(case_id: str, verdict: str, gates: dict[str, str], seconds: float | None,
           agent_name: str, agent_version: str, checked_at_utc: str,
           reason: str | None = None) -> str:
    duration = "pending" if seconds is None else f"{seconds:.1f} s"
    rows = "\n".join(f"| {gate} | {gates.get(gate, 'SKIPPED')} |" for gate in GATES)
    note = "\n\nStatus: no agent fix yet" if verdict == "PENDING" else ""
    verifier_note = " (configured; not run)" if verdict == "PENDING" else ""
    if verdict == "INFRASTRUCTURE_ERROR":
        verifier_note = " (attempted; no code verdict)"
    reason_line = f"\n\nReason: {reason}" if reason is not None else ""
    return (f"# {case_id}\n\nVerdict: **{verdict}**{note}{reason_line}\n\nElapsed: {duration}\n\n"
            f"Verifier: cplus {VERIFIER_REVISION} · {checked_at_utc}{verifier_note}\n\n"
            f"Agent: {agent_name} · Version: {agent_version}\n\n"
            f"| Check | Status |\n| --- | --- |\n{rows}\n")


def run_case(case_id: str) -> tuple[str, dict[str, str], float | None, str | None]:
    case_dir = ROOT / "cases" / case_id
    if not case_dir.is_dir():
        raise ValueError("Case missing")
    case = json.loads((case_dir / "case.yaml").read_text(encoding="utf-8"))
    patch = case_dir / "agent-fix.patch"
    if not patch.read_bytes().strip():
        return "PENDING", {}, None, None
    scratch = TEMP / "case-checkouts" / case_id
    scratch.parent.mkdir(parents=True, exist_ok=True)
    clone = quiet("git", "clone", "--quiet", "--no-checkout", case["repo"], str(scratch))
    if clone.returncode:
        raise RuntimeError("Clone failed")
    base, fix = case["base"], case["upstream_fix"]
    if quiet("git", "checkout", "--quiet", "--detach", base, cwd=scratch).returncode:
        raise RuntimeError("Base unavailable")
    fix_patch = quiet("git", "diff", base, fix, cwd=scratch)
    if fix_patch.returncode or not fix_patch.stdout:
        raise RuntimeError("Fix unavailable")
    upstream_patch = TEMP / f"{case_id}-upstream.patch"
    upstream_patch.write_text(fix_patch.stdout, encoding="utf-8")
    config = ("version: 1\nbuild_system: cmake\n"
              f"build: {case['build']}\ntest: {case['test']}\n"
              "build_environment: default image\nprotected_paths:\n"
              "- test/**\n- tests/**\n- .github/**\n- '**/*.supp'\n")
    (scratch / "cplus.yaml").write_text(config, encoding="utf-8")
    spec = TEMP / f"{case_id}-bug-spec.json"
    bug = quiet("cplus", "bug", "--project", str(scratch), "--from-fix",
                str(upstream_patch), "--export", str(spec))
    if bug.returncode or "REPRODUCED" not in bug.stdout or not spec.is_file():
        raise RuntimeError("Baseline not reproduced")
    started = time.monotonic()
    verify = quiet("cplus", "verify", "--project", str(scratch), "--patch",
                   str(patch), "--bug-spec", str(spec),
                   "--reference-test-from-fix", str(upstream_patch), "--json")
    elapsed = time.monotonic() - started
    report = extract_json(verify.stdout)
    verdict = report.get("verdict")
    if verdict not in VERDICTS or report.get("infrastructure_error"):
        raise RuntimeError("Invalid verifier result")
    raw_gates = report.get("gates")
    if not isinstance(raw_gates, list):
        raise RuntimeError("Invalid gate list")
    gates: dict[str, str] = {}
    reason: str | None = None
    for gate in raw_gates:
        if not isinstance(gate, dict):
            raise RuntimeError("Invalid gate")
        name, status = gate.get("name"), gate.get("status")
        if name not in GATES or status not in STATUSES:
            raise RuntimeError("Unexpected gate")
        gates[str(name)] = str(status)
        if status == "FAIL" and reason is None:
            reason = gate_reason(gate)
    if verdict == "REJECTED" and reason is None:
        reason = "verifier rejected the patch; no failing gate reason provided"
    if verdict in {"NOT_VERIFIABLE", "ERROR"} and reason is None:
        reason = summary_reason(report.get("summary"), f"verifier returned {str(verdict).lower()}")
    reference_reason = summary_reason(report.get("summary"), "")
    if reference_reason.startswith("judged by upstream reference test '"):
        reason = reference_reason
    return str(verdict), gates, elapsed, reason


def main() -> int:
    failed = False
    checked_at_utc = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    for case_id in selected_cases():
        agent_name, agent_version = "not recorded", "not recorded"
        try:
            agent_name, agent_version = agent_identity(case_id)
            verdict, gates, seconds, reason = run_case(case_id)
        except Exception:
            verdict, gates, seconds, reason = (
                "INFRASTRUCTURE_ERROR", {}, None, "case execution failed before a valid verifier result"
            )
            failed = True
        result = ROOT / "results" / f"{case_id}.md"
        result.parent.mkdir(parents=True, exist_ok=True)
        result.write_text(
            render(case_id, verdict, gates, seconds, agent_name, agent_version, checked_at_utc,
                   reason),
            encoding="utf-8",
        )
        label = f"{verdict} - no agent fix yet" if verdict == "PENDING" else verdict
        print(f"{case_id}: {label}")
        for gate in GATES:
            print(f"  {gate}: {gates.get(gate, 'SKIPPED')}")
    return 1 if failed else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--has-patches"]:
        print("true" if any((ROOT / "cases" / case_id / "agent-fix.patch").read_bytes().strip()
                            for case_id in selected_cases()) else "false")
    else:
        sys.exit(main())
