"""The lab must execute the selected source and preserve failed-run evidence."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lab


class LabEntrypointChecks(unittest.TestCase):
    def setUp(self):
        temporary_root = lab.ROOT / "outputs/test-tmp"
        temporary_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=temporary_root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "selected-source"
        (self.source / "agent").mkdir(parents=True)
        self.output = self.root / "result"

    def result(self):
        return json.loads((self.output / "result.json").read_text("utf-8"))

    def test_subprocess_logs_stdout_stderr_and_exact_exit_code(self):
        self.output.mkdir()
        with contextlib.redirect_stdout(io.StringIO()):
            lab.run([sys.executable, "-c", "import sys; print('stdout ♪'); print('stderr 全力', file=sys.stderr)"],
                    cwd=self.source, output=self.output)
        result = self.result()
        self.assertEqual("running", result["status"])
        self.assertEqual("passed", result["commands"][0]["status"])
        self.assertEqual(0, result["commands"][0]["exitCode"])
        self.assertIn("stdout ♪", (self.output / "run.log").read_text("utf-8"))
        self.assertIn("stderr 全力", (self.output / "run.log").read_text("utf-8"))

    def test_main_configures_utf8_even_when_terminal_defaults_to_ascii(self):
        stream = io.TextIOWrapper(io.BytesIO(), encoding="ascii")
        argv = ["lab.py", "--source", str(self.root / "missing"), "prepare"]
        with patch.object(sys, "argv", argv), contextlib.redirect_stdout(stream), contextlib.redirect_stderr(io.StringIO()), \
                self.assertRaises(SystemExit):
            lab.main()
        self.assertEqual("utf-8", stream.encoding)
        stream.write("♪ 全力")
        stream.close()

    def test_failure_propagates_and_is_not_marked_passed(self):
        self.output.mkdir()
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(subprocess.CalledProcessError) as failure:
            lab.run([sys.executable, "-c", "raise SystemExit(7)"], cwd=self.source, output=self.output)
        self.assertEqual(7, failure.exception.returncode)
        self.assertEqual("failed", self.result()["status"])
        self.assertEqual(7, self.result()["commands"][0]["exitCode"])

    def test_missing_executable_records_failure(self):
        self.output.mkdir()
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(FileNotFoundError):
            lab.run([self.root / "missing-executable"], cwd=self.source, output=self.output)
        self.assertEqual("failed", self.result()["status"])
        self.assertIn("error", self.result()["commands"][0])

    def test_explicit_source_controls_fixture_overlay_and_pytest_working_directory(self):
        commands = []
        actual_run = lab.run

        def invoke(command, **kwargs):
            commands.append((command, kwargs))
            actual_run([sys.executable, "-c", "print('ok')"], **kwargs)

        def provenance(output, source):
            self.assertEqual(self.source, source)
            output.mkdir()

        argv = ["lab.py", "--source", str(self.source), "test", "--output", str(self.output), "--", "-k", "battle"]
        with patch.object(sys, "argv", argv), patch.object(lab, "prepare") as prepare, \
                patch.object(lab, "provenance", side_effect=provenance), patch.object(lab, "run", side_effect=invoke), \
                contextlib.redirect_stdout(io.StringIO()):
            lab.main()
        prepare.assert_called_once_with(self.source)
        self.assertEqual(self.source, commands[0][1]["cwd"])
        self.assertEqual(["-k", "battle"], commands[0][0][-2:])
        self.assertEqual("passed", self.result()["status"])

    def test_invalid_vectors_stop_before_overlay_or_output(self):
        argv = ["lab.py", "--source", str(self.source), "test", "--output", str(self.output),
                "--vectors", str(self.root / "absent.json")]
        with patch.object(sys, "argv", argv), patch.object(lab, "prepare") as prepare, \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as failure:
            lab.main()
        self.assertEqual(2, failure.exception.code)
        prepare.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_required_vectors_cannot_be_omitted(self):
        argv = ["lab.py", "--source", str(self.source), "test", "--output", str(self.output), "--require-vectors"]
        with patch.object(sys, "argv", argv), patch.object(lab, "prepare") as prepare, \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as failure:
            lab.main()
        self.assertEqual(2, failure.exception.code)
        prepare.assert_not_called()
        self.assertFalse(self.output.exists())

    def vector_fixture(self):
        self.output.mkdir()
        identity = {"sourceCommit": "selected-sha", "sourceDiffSha256": "tracked-diff", "sourceUntrackedSha256": "new-files"}
        (self.output / "environment.json").write_text(json.dumps(identity), "utf-8")
        vectors = self.output / "native-policy-vectors.json"
        vectors.write_text(json.dumps({"schemaVersion": 2, "cases": [{"id": "case"}]}), "utf-8")
        return identity, vectors

    def test_vectors_require_matching_content_and_source_identity(self):
        identity, vectors = self.vector_fixture()
        with patch.object(lab, "source_identity", return_value=identity):
            lab.record_native_vectors(self.output, self.source)
            result = lab.verify_native_vectors(vectors, self.source)
            self.assertEqual(1, result["caseCount"])
            self.assertEqual(lab.digest(vectors), result["sha256"])
            vectors.write_text("[]", "utf-8")
            with self.assertRaisesRegex(ValueError, "checksum"):
                lab.verify_native_vectors(vectors, self.source)

    def test_vectors_reject_changed_or_untracked_source(self):
        identity, vectors = self.vector_fixture()
        with patch.object(lab, "source_identity", return_value=identity):
            lab.record_native_vectors(self.output, self.source)
        for key in identity:
            changed = {**identity, key: "changed"}
            with self.subTest(key=key), patch.object(lab, "source_identity", return_value=changed), \
                    self.assertRaisesRegex(ValueError, "different source"):
                lab.verify_native_vectors(vectors, self.source)

    def test_vectors_cannot_be_recorded_after_source_changes_during_native_run(self):
        identity, _ = self.vector_fixture()
        with patch.object(lab, "source_identity", return_value={**identity, "sourceDiffSha256": "changed"}), \
                self.assertRaisesRegex(ValueError, "Source changed"):
            lab.record_native_vectors(self.output, self.source)
        self.assertFalse((self.output / "native-policy-provenance.json").exists())

    def test_vectors_without_source_sidecar_are_rejected(self):
        _, vectors = self.vector_fixture()
        with self.assertRaisesRegex(ValueError, "provenance"):
            lab.verify_native_vectors(vectors, self.source)

    def test_empty_native_vectors_cannot_be_recorded(self):
        _, vectors = self.vector_fixture()
        vectors.write_text("[]", "utf-8")
        with self.assertRaisesRegex(ValueError, "nonempty"):
            lab.record_native_vectors(self.output, self.source)

    def test_required_vector_comparison_must_execute_without_skip(self):
        self.output.mkdir()
        report = self.output / "junit.xml"
        for body in ("", '<testcase name="unrelated" />',
                     '<testcase name="test_native_python_policy_equivalence"><skipped /></testcase>'):
            with self.subTest(body=body), self.assertRaisesRegex(ValueError, "missing, skipped, or failed"):
                report.write_text("<testsuite>" + body + "</testsuite>", "utf-8")
                lab.verify_vector_execution(self.output)
        report.write_text('<testsuite><testcase name="test_native_python_policy_equivalence" /></testsuite>', "utf-8")
        lab.verify_vector_execution(self.output)

    def test_required_vectors_also_require_fixed_expectations_and_share_checks(self):
        self.output.mkdir()
        fixtures = self.source / "tests/fixtures"
        fixtures.mkdir(parents=True)
        (fixtures / "card_rule_policy_oracle.json").write_text(json.dumps({
            "policyCases": [{"id": "fixed-policy"}], "validationCases": [{"id": "fixed-validation"}]
        }), "utf-8")
        names = ["test_native_python_policy_equivalence"]
        report = self.output / "junit.xml"
        report.write_text('<testsuite><testcase name="test_native_python_policy_equivalence" /></testsuite>', "utf-8")
        with self.assertRaisesRegex(ValueError, "fixed policy expectations"):
            lab.verify_vector_execution(self.output, self.source)
        names += ["test_fixed_policy_expectations[fixed-policy]", "test_fixed_document_validation[fixed-validation]",
                  "test_native_profession_share_round_trip_reaches_python_policy"]
        report.write_text("<testsuite>" + "".join(f'<testcase name="{name}" />' for name in names) + "</testsuite>", "utf-8")
        lab.verify_vector_execution(self.output, self.source)

    def test_model_check_isolates_native_config_and_logs_from_source_checkout(self):
        commands = []
        actual_run = lab.run

        def invoke(command, **kwargs):
            commands.append((command, kwargs))
            actual_run([sys.executable, "-c", "print('native replay simulated')"], **kwargs)

        argv = ["lab.py", "--source", str(self.source), "model-check", "--image", str(self.root / "frame.png"),
                "--output", str(self.output), "--", "--threshold", "0.5"]
        with patch.object(sys, "argv", argv), patch.object(lab, "provenance", side_effect=lambda output, source: output.mkdir()), \
                patch.object(lab, "run", side_effect=invoke), contextlib.redirect_stdout(io.StringIO()):
            lab.main()
        command, options = commands[0]
        self.assertEqual(self.output, options["cwd"])
        self.assertEqual(self.source / "tools/check_cards_model.py", command[1])
        self.assertEqual(self.source / "assets/resource/base", command[2])
        self.assertEqual(["--threshold", "0.5"], command[-2:])
        self.assertEqual("passed", self.result()["status"])

    def test_unknown_native_script_fails_argument_validation(self):
        argv = ["lab.py", "--source", str(self.source), "ui", "NativeShots", "--script", "round-typo"]
        with patch.object(sys, "argv", argv), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as failure:
            lab.main()
        self.assertEqual(2, failure.exception.code)

    def test_native_suite_missing_in_old_source_fails_before_output(self):
        argv = ["lab.py", "--source", str(self.source), "ui", "LiquidBoardTests", "--output", str(self.output)]
        with patch.object(sys, "argv", argv), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as failure:
            lab.main()
        self.assertEqual(2, failure.exception.code)
        self.assertFalse(self.output.exists())

    def test_provenance_records_selected_source_and_refuses_overwrite(self):
        def check_output(command, **kwargs):
            if command[0] == "git":
                self.assertEqual(self.source, kwargs["cwd"])
                if command[1] == "ls-files":
                    return b""
                return b"selected-sha\n" if command[1] == "rev-parse" else b" M changed.py\n"
            return b"pytest==8.0\n"

        with patch.object(lab.subprocess, "check_output", side_effect=check_output):
            lab.provenance(self.output, self.source)
            with self.assertRaises(FileExistsError):
                lab.provenance(self.output, self.source)
        data = json.loads((self.output / "environment.json").read_text("utf-8"))
        self.assertEqual(str(self.source), data["sourcePath"])
        self.assertEqual("selected-sha", data["sourceCommit"])
        self.assertEqual(["pytest==8.0"], data["packages"])

    def project(self, suite, project_name=None):
        directory = self.source / "tests" / suite
        directory.mkdir(parents=True)
        (directory / ((project_name or suite) + ".csproj")).write_text("<Project />", "utf-8")
        self.output.mkdir()

    def fake_build(self, command, **kwargs):
        if command[1] == "build":
            Path(command[-1]).mkdir()

    def test_native_shots_runs_beside_isolated_defaults(self):
        self.project("NativeShots")
        (self.source / "assets/config").mkdir(parents=True)
        (self.source / "assets/config/card_rules.json").write_text("{}", "utf-8")
        (self.source / "agent/custom").mkdir()
        (self.source / "agent/custom/drink_catalog.json").write_text("[]", "utf-8")
        args = argparse.Namespace(suite="NativeShots", dotnet="dotnet", script="audit", combo_only=False)
        with patch.object(lab, "run", side_effect=self.fake_build) as run:
            lab.run_ui(args, self.source, self.output)
        runtime = self.output / "runtime"
        command = run.call_args.args[0]
        self.assertEqual(["dotnet", runtime / "NativeShots.dll", runtime, self.output, "audit"], command)
        self.assertEqual(runtime, run.call_args.kwargs["cwd"])
        config = json.loads((runtime / "config/config.json").read_text("utf-8"))
        self.assertFalse(config["EnableCheckVersion"])
        self.assertFalse(config["AutoConnectAfterRefresh"])
        global_config = json.loads((runtime / "appsettings.json").read_text("utf-8"))
        self.assertEqual("True", global_config["AnnouncementInfo.DoNotShowAgain"])
        self.assertEqual("True", global_config["Changelog.DoNotShowAgain"])
        self.assertTrue((runtime / "agent/custom/drink_catalog.json").is_file())
        self.assertFalse((self.source / "config").exists())

    def test_portable_layout_copies_dependencies_but_not_personal_config(self):
        self.project("PortableLayout")
        portable = self.root / "portable"
        (portable / "libs").mkdir(parents=True)
        for name in ("libs/MFAAvalonia.Core.dll", "MFAAvalonia.runtimeconfig.json", "MFAAvalonia.deps.json", "libloader.dll"):
            (portable / name).write_bytes(b"fixture")
        (portable / "config").mkdir()
        (portable / "config/private.json").write_text("private", "utf-8")
        args = argparse.Namespace(suite="PortableLayout", dotnet="dotnet", runtime=portable)
        with patch.object(lab, "run", side_effect=self.fake_build) as run:
            lab.run_ui(args, self.source, self.output)
        runtime = self.output / "runtime"
        command = run.call_args.args[0]
        self.assertEqual(["dotnet", "exec", "--runtimeconfig"], command[:3])
        self.assertIn(runtime / "MFAAvalonia.deps.json", command)
        self.assertEqual(self.source / "native-ui/MFAAvalonia/Assets/Localization", command[-1])
        self.assertTrue((runtime / "libs/MFAAvalonia.Core.dll").is_file())
        self.assertFalse((runtime / "config").exists())
        self.assertTrue((output_evidence := self.output / "portable-input.json").is_file())
        self.assertEqual(str(portable), json.loads(output_evidence.read_text("utf-8"))["path"])

    def test_native_project_name_need_not_match_suite_directory(self):
        self.project("native_release_policy", "ReleasePolicyTests")
        args = argparse.Namespace(suite="native_release_policy", dotnet="dotnet")
        with patch.object(lab, "run", side_effect=self.fake_build) as run:
            lab.run_ui(args, self.source, self.output)
        self.assertEqual(self.output / "runtime/ReleasePolicyTests.dll", run.call_args.args[0][1])

    def test_archive_policy_receives_a_new_output_directory(self):
        self.project("native_archive_policy", "ArchivePolicyTests")
        args = argparse.Namespace(suite="native_archive_policy", dotnet="dotnet")
        with patch.object(lab, "run", side_effect=self.fake_build) as run:
            lab.run_ui(args, self.source, self.output)
        self.assertEqual(self.output / "archive-policy", run.call_args.args[0][-1])
        self.assertFalse((self.output / "archive-policy").exists())


if __name__ == "__main__":
    unittest.main()
