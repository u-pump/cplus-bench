"""Run private cplus and publish only a small allowlisted summary."""

from __future__ import annotations

import hashlib
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
RESULTS_DIR = Path(os.environ.get("RESULTS_DIR", str(ROOT / "results")))
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
VERIFIER_REVISION = "81c0fda242fef1daf55d3164e06127d372c81caa"


class CaseExecutionError(RuntimeError):
    """An infrastructure failure with an allowlisted public stage and reason."""

    def __init__(self, stage: str, reason: str) -> None:
        self.stage = stage
        self.public_reason = f"{stage}: {reason}"
        super().__init__(self.public_reason)


def quiet(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)


def quiet_stage(stage: str, reason: str, *args: str,
                cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return quiet(*args, cwd=cwd)
    except OSError as exc:
        raise CaseExecutionError(stage, reason) from exc


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


def selected_agents(case_id: str) -> list[str]:
    root = ROOT / "cases" / case_id / "agents"
    if not root.is_dir():
        raise CaseExecutionError("parse", "agent directory unavailable")
    agents = sorted(path.name for path in root.iterdir() if path.is_dir())
    if not agents or any(not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name) for name in agents):
        raise CaseExecutionError("parse", "invalid agent directory")
    return agents


def agent_identity(case_id: str, agent_id: str) -> tuple[str, str]:
    agent = json.loads(
        (ROOT / "cases" / case_id / "agents" / agent_id / "agent.yaml").read_text(encoding="utf-8")
    )
    if not isinstance(agent, dict):
        raise ValueError("Invalid agent metadata")
    required = {"name", "version", "model", "invocation", "date_utc", "environment", "patch_sha256", "attempt_note"}
    if not required <= agent.keys():
        raise ValueError("Missing agent metadata")
    name = str(agent.get("name") or "not run").replace("\n", " ").replace("\r", " ")
    version = str(agent.get("version") or "not recorded").replace("\n", " ").replace("\r", " ")
    return name, version


def agent_result_note(case_id: str, agent_id: str) -> str | None:
    """Read a curated, single-line note from public agent metadata."""
    agent = json.loads(
        (ROOT / "cases" / case_id / "agents" / agent_id / "agent.yaml").read_text(encoding="utf-8")
    )
    note = agent.get("result_note")
    if note is None:
        return None
    if not isinstance(note, str) or not note or summary_reason(note, "") != note:
        raise CaseExecutionError("parse", "invalid case result note")
    return note


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
           reason: str | None = None, result_note: str | None = None) -> str:
    duration = "pending" if seconds is None else f"{seconds:.1f} s"
    rows = "\n".join(f"| {gate} | {gates.get(gate, 'SKIPPED')} |" for gate in GATES)
    note = "\n\nStatus: no agent fix yet" if verdict == "PENDING" else ""
    verifier_note = " (configured; not run)" if verdict == "PENDING" else ""
    if verdict == "INFRASTRUCTURE_ERROR":
        verifier_note = " (attempted; no code verdict)"
    reason_line = f"\n\nReason: {reason}" if reason is not None else ""
    note_line = f"\n\nNote: {result_note}" if verdict == "REJECTED" and result_note else ""
    return (f"# {case_id}\n\nVerdict: **{verdict}**{note}{reason_line}{note_line}\n\nElapsed: {duration}\n\n"
            f"Verifier: cplus {VERIFIER_REVISION} · {checked_at_utc}{verifier_note}\n\n"
            f"Agent: {agent_name} · Version: {agent_version}\n\n"
            f"| Check | Status |\n| --- | --- |\n{rows}\n")


def run_case(case_id: str, agent_id: str) -> tuple[str, dict[str, str], float | None, str | None]:
    case_dir = ROOT / "cases" / case_id
    if not case_dir.is_dir():
        raise CaseExecutionError("parse", "case metadata unavailable")
    try:
        case = json.loads((case_dir / "case.yaml").read_text(encoding="utf-8"))
        patch = case_dir / "agents" / agent_id / "agent-fix.patch"
        patch_bytes = patch.read_bytes()
        agent = json.loads((patch.parent / "agent.yaml").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CaseExecutionError("parse", "case metadata unavailable") from exc
    if not patch_bytes.strip():
        if patch_bytes or agent.get("patch_sha256") is not None:
            raise CaseExecutionError("parse", "invalid pending patch metadata")
        return "PENDING", {}, None, None
    if not isinstance(agent, dict) or any(not agent.get(key) for key in (
        "name", "version", "model", "invocation", "date_utc", "environment", "attempt_note"
    )):
        raise CaseExecutionError("parse", "incomplete agent metadata")
    if hashlib.sha256(patch_bytes).hexdigest() != agent.get("patch_sha256"):
        raise CaseExecutionError("parse", "patch hash mismatch")
    scratch = TEMP / "case-checkouts" / case_id / agent_id
    scratch.parent.mkdir(parents=True, exist_ok=True)
    clone = quiet_stage("clone", "source repository unavailable", "git", "clone", "--quiet",
                        "--no-checkout", case["repo"], str(scratch))
    if clone.returncode:
        raise CaseExecutionError("clone", "source repository unavailable")
    base, fix = case["base"], case["upstream_fix"]
    if quiet_stage("checkout base", "base revision unavailable", "git", "checkout",
                   "--quiet", "--detach", base, cwd=scratch).returncode:
        raise CaseExecutionError("checkout base", "base revision unavailable")
    fix_patch = quiet_stage("upstream fix", "reference revision unavailable", "git", "diff",
                            base, fix, cwd=scratch)
    if fix_patch.returncode or not fix_patch.stdout:
        raise CaseExecutionError("upstream fix", "reference revision unavailable")
    upstream_patch = TEMP / f"{case_id}-{agent_id}-upstream.patch"
    upstream_patch.write_text(fix_patch.stdout, encoding="utf-8")
    config = ("version: 1\nbuild_system: cmake\n"
              f"build: {case['build']}\ntest: {case['test']}\n"
              "build_environment: default image\nprotected_paths:\n"
              "- test/**\n- tests/**\n- .github/**\n- '**/*.supp'\n")
    (scratch / "cplus.yaml").write_text(config, encoding="utf-8")
    spec = TEMP / f"{case_id}-{agent_id}-bug-spec.json"
    reference_name = case.get("reference_test_name")
    if reference_name is not None and (
        not isinstance(reference_name, str)
        or not re.fullmatch(r"[A-Za-z_]\w*\.[A-Za-z_]\w*", reference_name)
    ):
        raise CaseExecutionError("parse", "invalid reference test selection")
    bug_args = ["cplus", "bug", "--project", str(scratch), "--from-fix",
                str(upstream_patch), "--export", str(spec)]
    if reference_name is not None:
        bug_args.extend(("--command", f"GTEST_FILTER={reference_name} {case['test']}"))
    bug = quiet_stage("cplus bug baseline", "reference test did not reproduce", *bug_args)
    if bug.returncode or "REPRODUCED" not in bug.stdout or not spec.is_file():
        raise CaseExecutionError("cplus bug baseline", "reference test did not reproduce")
    started = time.monotonic()
    verify_args = ["cplus", "verify", "--project", str(scratch), "--patch",
                   str(patch), "--bug-spec", str(spec),
                   "--reference-test-from-fix", str(upstream_patch), "--json"]
    if reference_name is not None:
        verify_args.extend(("--reference-test-name", reference_name))
    verify = quiet_stage("verify", "verifier could not evaluate patch", *verify_args)
    elapsed = time.monotonic() - started
    try:
        report = extract_json(verify.stdout)
    except ValueError as exc:
        raise CaseExecutionError("parse", "no valid verifier result") from exc
    verdict = report.get("verdict")
    infrastructure = report.get("infrastructure_error")
    if infrastructure:
        if isinstance(infrastructure, str) and "reference test has no unique test name" in infrastructure:
            raise CaseExecutionError("verify", "upstream reference test could not be selected")
        if isinstance(infrastructure, str) and "did not reproduce the bug after revert" in infrastructure:
            raise CaseExecutionError("verify", "reference failure was absent after source revert")
        raise CaseExecutionError("verify", "verifier could not evaluate patch")
    if verdict not in VERDICTS:
        raise CaseExecutionError("parse", "invalid verifier verdict")
    raw_gates = report.get("gates")
    if not isinstance(raw_gates, list):
        raise CaseExecutionError("parse", "invalid verifier result")
    gates: dict[str, str] = {}
    reason: str | None = None
    for gate in raw_gates:
        if not isinstance(gate, dict):
            raise CaseExecutionError("parse", "invalid verifier result")
        name, status = gate.get("name"), gate.get("status")
        if status not in STATUSES:
            raise CaseExecutionError("parse", "invalid verifier result")
        if name not in GATES:
            # The verifier may include a diagnostic gate on an inconclusive result.
            # Keep its name and evidence out of the public summary, but never
            # publish a positive code verdict if an unknown check appeared.
            if verdict in {"NOT_VERIFIABLE", "ERROR"}:
                continue
            raise CaseExecutionError("parse", "unexpected verifier check")
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
        for agent_id in selected_agents(case_id):
            agent_name, agent_version = "not recorded", "not recorded"
            result_note = None
            try:
                agent_name, agent_version = agent_identity(case_id, agent_id)
                verdict, gates, seconds, reason = run_case(case_id, agent_id)
                result_note = agent_result_note(case_id, agent_id)
            except Exception as exc:
                public_reason = (exc.public_reason if isinstance(exc, CaseExecutionError)
                                 else "parse: unexpected case processing error")
                verdict, gates, seconds, reason = (
                    "INFRASTRUCTURE_ERROR", {}, None, public_reason
                )
                failed = True
            result = RESULTS_DIR / case_id / f"{agent_id}.md"
            result.parent.mkdir(parents=True, exist_ok=True)
            result.write_text(
                render(case_id, verdict, gates, seconds, agent_name, agent_version, checked_at_utc,
                       reason, result_note),
                encoding="utf-8",
            )
            label = f"{verdict} - no agent fix yet" if verdict == "PENDING" else verdict
            print(f"{case_id}/{agent_id}: {label}" + (f"; Reason: {reason}" if reason else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--has-patches"]:
        print("true" if any((ROOT / "cases" / case_id / "agents" / agent_id / "agent-fix.patch").read_bytes().strip()
                            for case_id in selected_cases() for agent_id in selected_agents(case_id)) else "false")
    else:
        sys.exit(main())
