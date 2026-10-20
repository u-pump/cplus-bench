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
    def test_run_case_uses_public_verifier_summary(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / ".tmp") as directory:
            temp = Path(directory)

            def fake_quiet(*args: str, cwd: Path | None = None):
                if args[:2] == ("git", "clone"):
                    Path(args[-1]).mkdir(parents=True, exist_ok=True)
                if args[:2] == ("git", "diff"):
                    return completed("diff --git a/test.cc b/test.cc\n")
                if args[:2] == ("cplus", "bug"):
                    Path(args[args.index("--export") + 1]).write_text("{}", encoding="utf-8")
                    return completed("REPRODUCED")
                if args[:2] == ("cplus", "verify"):
                    return completed(json.dumps({
                        "schema_version": 1, "verdict": current_verdict,
                        "summary": "the fix patch differs from the one whose test reproduced this bug",
                        "infrastructure_error": None, "gates": [],
                    }))
                return completed("")

            for current_verdict in ("NOT_VERIFIABLE", "ERROR"):
                with (self.subTest(verdict=current_verdict),
                      patch.object(verify_cases, "TEMP", temp),
                      patch.object(verify_cases, "quiet", side_effect=fake_quiet)):
                    verdict, gates, _elapsed, reason = verify_cases.run_case("cpp-peglib-121")
                self.assertEqual(verdict, current_verdict)
                self.assertEqual(gates, {})
                self.assertEqual(
                    reason, "the fix patch differs from the one whose test reproduced this bug"
                )

    def test_nonverifiable_and_error_reasons_are_short_and_public(self) -> None:
        summary = "the fix patch differs from the one whose test reproduced this bug\nPRIVATE_CPLUS_LOG"
        self.assertEqual(
            verify_cases.summary_reason(summary, "fallback"),
            "the fix patch differs from the one whose test reproduced this bug",
        )
        self.assertEqual(
            verify_cases.summary_reason("build failed at D:\\runner\\private\\log", "verifier returned error"),
            "verifier returned error",
        )
        for verdict in ("NOT_VERIFIABLE", "ERROR", "INFRASTRUCTURE_ERROR"):
            report = verify_cases.render(
                "fmt-4800", verdict, {}, 0.7, "Codex CLI", "0.163.0",
                "2026-10-20 18:00:00 UTC", verify_cases.summary_reason(summary, "fallback"),
            )
            self.assertEqual(report.count("Reason:"), 1)
            self.assertNotIn("PRIVATE_CPLUS_LOG", report)
            self.assertNotIn("D:\\runner", report)

    def test_infrastructure_error_reports_generic_reason_without_exception_details(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / ".tmp") as directory:
            root = Path(directory)
            with (patch.object(verify_cases, "ROOT", root),
                  patch.object(verify_cases, "selected_cases", return_value=["fmt-4800"]),
                  patch.object(verify_cases, "agent_identity", return_value=("Codex CLI", "0.163.0")),
                  patch.object(verify_cases, "run_case", side_effect=RuntimeError("D:\\runner\\private\\log PRIVATE_CPLUS_LOG")),
                  contextlib.redirect_stdout(io.StringIO())):
                self.assertEqual(verify_cases.main(), 1)
            result = (root / "results" / "fmt-4800.md").read_text(encoding="utf-8")
            self.assertIn("Verdict: **INFRASTRUCTURE_ERROR**", result)
            self.assertIn("Reason: case execution failed before a valid verifier result", result)
            self.assertNotIn("D:\\runner", result)
            self.assertNotIn("PRIVATE_CPLUS_LOG", result)

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
