"""Run private cplus and publish only a small allowlisted summary."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
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


def render(case_id: str, verdict: str, gates: dict[str, str], seconds: float | None) -> str:
    duration = "pending" if seconds is None else f"{seconds:.1f} s"
    rows = "\n".join(f"| {gate} | {gates.get(gate, 'SKIPPED')} |" for gate in GATES)
    note = "\n\nStatus: no agent fix yet" if verdict == "PENDING" else ""
    return (f"# {case_id}\n\nVerdict: **{verdict}**{note}\n\nElapsed: {duration}\n\n"
            f"| Check | Status |\n| --- | --- |\n{rows}\n")


def run_case(case_id: str) -> tuple[str, dict[str, str], float | None]:
    case_dir = ROOT / "cases" / case_id
    if not case_dir.is_dir():
        raise ValueError("Case missing")
    case = json.loads((case_dir / "case.yaml").read_text(encoding="utf-8"))
    patch = case_dir / "agent-fix.patch"
    if not patch.read_bytes().strip():
        return "PENDING", {}, None
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
                   str(patch), "--bug-spec", str(spec), "--json")
    elapsed = time.monotonic() - started
    report = extract_json(verify.stdout)
    verdict = report.get("verdict")
    if verdict not in VERDICTS or report.get("infrastructure_error"):
        raise RuntimeError("Invalid verifier result")
    raw_gates = report.get("gates")
    if not isinstance(raw_gates, list):
        raise RuntimeError("Invalid gate list")
    gates: dict[str, str] = {}
    for gate in raw_gates:
        if not isinstance(gate, dict):
            raise RuntimeError("Invalid gate")
        name, status = gate.get("name"), gate.get("status")
        if name not in GATES or status not in STATUSES:
            raise RuntimeError("Unexpected gate")
        gates[str(name)] = str(status)
    return str(verdict), gates, elapsed


def main() -> int:
    failed = False
    for case_id in selected_cases():
        try:
            verdict, gates, seconds = run_case(case_id)
        except Exception:
            verdict, gates, seconds = "INFRASTRUCTURE_ERROR", {}, None
            failed = True
        result = ROOT / "results" / f"{case_id}.md"
        result.parent.mkdir(parents=True, exist_ok=True)
        result.write_text(render(case_id, verdict, gates, seconds), encoding="utf-8")
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
