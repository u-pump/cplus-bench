"""Offline smoke test of case selection and public report generation."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import verify_cases


class VerifyCasesSmokeTest(unittest.TestCase):
    def test_rejected_report_has_only_public_one_line_gate_reason(self) -> None:
        gate = {
            "name": "anti_cheat",
            "status": "FAIL",
            "evidence": {"reason": "protected test edited at test/test1.cc:756; checkout D:\\runner\\private\\case\nPRIVATE_CPLUS_LOG"},
        }
        reason = verify_cases.gate_reason(gate)
        report = verify_cases.render(
            "cpp-peglib-121", "REJECTED", {"anti_cheat": "FAIL"}, 0.9,
            "Codex CLI", "0.163.0", "2026-10-19 21:00:00 UTC", reason,
        )
        self.assertIn("Reason: protected test edited at test/test1.cc:756", report)
        self.assertIn("[path]", report)
        self.assertNotIn("D:\\runner", report)
        self.assertNotIn("PRIVATE_CPLUS_LOG", report)
        self.assertEqual(report.count("Reason:"), 1)

    def test_one_case_without_private_verifier_or_token(self) -> None:
        source = Path(__file__).resolve().parents[1] / "cases" / "cpp-peglib-121"
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / ".tmp") as directory:
            root = Path(directory)
            case_dir = root / "cases" / "cpp-peglib-121"
            case_dir.mkdir(parents=True)
            case = json.loads((source / "case.yaml").read_text(encoding="utf-8"))
            case["agent"] = {"name": "MockAgent", "version": "2026.10"}
            (case_dir / "case.yaml").write_text(json.dumps(case), encoding="utf-8")
            (case_dir / "agent-fix.patch").write_text("diff --git a/a b/a\n", encoding="utf-8")
            calls: list[tuple[str, ...]] = []

            def fake_quiet(*args: str, cwd: Path | None = None):
                calls.append(args)
                if args[:2] == ("git", "clone"):
                    Path(args[-1]).mkdir(parents=True)
                    return completed("")
                if args[:2] == ("git", "diff"):
                    return completed("diff --git a/a b/a\n")
                if args[:2] == ("cplus", "bug"):
                    Path(args[args.index("--export") + 1]).write_text("{}", encoding="utf-8")
                    return completed("REPRODUCED — bug reproduced in 3/3 runs")
                if args[:2] == ("cplus", "verify"):
                    report = {
                        "schema_version": 1,
                        "verdict": "VERIFIED",
                        "infrastructure_error": None,
                        "gates": [{"name": name, "status": "PASS", "evidence": {"private": "TOKEN_SENTINEL D:\\private\\cplus PRIVATE_CPLUS_LOG"}}
                                  for name in verify_cases.GATES],
                    }
                    return completed(json.dumps(report) + "\nVERIFIED")
                return completed("")

            public_log = io.StringIO()
            with (patch.object(verify_cases, "ROOT", root),
                  patch.object(verify_cases, "TEMP", root / "tmp"),
                  patch.object(verify_cases, "quiet", side_effect=fake_quiet),
                  patch.dict("os.environ", {"SELECT_CASE": "cpp-peglib-121"}),
                  contextlib.redirect_stdout(public_log)):
                self.assertEqual(verify_cases.main(), 0)
            result = (root / "results" / "cpp-peglib-121.md").read_text(encoding="utf-8")
            self.assertIn("Verdict: **VERIFIED**", result)
            self.assertRegex(result, rf"Verifier: cplus {verify_cases.VERIFIER_REVISION} · \d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}}:\d{{2}} UTC")
            self.assertIn("Agent: MockAgent · Version: 2026.10", result)
            self.assertEqual(result.count("| PASS |"), 8)
            self.assertIn("| anti_cheat | PASS |", result)
            for sensitive in ("TOKEN_SENTINEL", "D:\\private\\cplus", "PRIVATE_CPLUS_LOG"):
                self.assertNotIn(sensitive, result)
                self.assertNotIn(sensitive, public_log.getvalue())
            self.assertTrue(any(call[:2] == ("cplus", "bug") for call in calls))
            self.assertTrue(any(call[:2] == ("cplus", "verify") for call in calls))

    def test_empty_patch_skips_verifier_and_says_no_agent_fix_yet(self) -> None:
        source = Path(__file__).resolve().parents[1] / "cases" / "cpp-peglib-121"
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / ".tmp") as directory:
            root = Path(directory)
            case_dir = root / "cases" / "cpp-peglib-121"
            case_dir.mkdir(parents=True)
            case = json.loads((source / "case.yaml").read_text(encoding="utf-8"))
            case["agent"] = None
            (case_dir / "case.yaml").write_text(json.dumps(case), encoding="utf-8")
            (case_dir / "agent-fix.patch").write_bytes(b"")
            public_log = io.StringIO()
            with (patch.object(verify_cases, "ROOT", root),
                  patch.object(verify_cases, "TEMP", root / "tmp"),
                  patch.object(verify_cases, "quiet", side_effect=AssertionError("cplus must not run")),
                  patch.dict("os.environ", {"SELECT_CASE": "cpp-peglib-121"}),
                  contextlib.redirect_stdout(public_log)):
                self.assertEqual(verify_cases.main(), 0)
            self.assertIn("no agent fix yet", public_log.getvalue())
            result = (root / "results" / "cpp-peglib-121.md").read_text(encoding="utf-8")
            self.assertIn("Status: no agent fix yet", result)
            self.assertIn("(configured; not run)", result)
            self.assertIn("Agent: not run · Version: not recorded", result)


def completed(stdout: str):
    from subprocess import CompletedProcess
    return CompletedProcess(args=(), returncode=0, stdout=stdout, stderr="")


if __name__ == "__main__":
    unittest.main()
