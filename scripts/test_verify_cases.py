"""Offline smoke test of case selection and public report generation."""

from __future__ import annotations

import json
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import verify_cases


class VerifyCasesSmokeTest(unittest.TestCase):
    def test_one_case_without_private_verifier_or_token(self) -> None:
        source = Path(__file__).resolve().parents[1] / "cases" / "cpp-peglib-121"
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / ".tmp") as directory:
            root = Path(directory)
            case_dir = root / "cases" / "cpp-peglib-121"
            case_dir.mkdir(parents=True)
            (case_dir / "case.yaml").write_bytes((source / "case.yaml").read_bytes())
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
            (case_dir / "case.yaml").write_bytes((source / "case.yaml").read_bytes())
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


def completed(stdout: str):
    from subprocess import CompletedProcess
    return CompletedProcess(args=(), returncode=0, stdout=stdout, stderr="")


if __name__ == "__main__":
    unittest.main()
