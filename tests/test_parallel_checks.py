from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ParallelChecksTests(unittest.TestCase):
    def run_gate(self, checks, cwd):
        # Exercise the actual process exit code used to gate publication in CI.
        code = (
            "import importlib.util, sys; "
            f"spec = importlib.util.spec_from_file_location('checks', {str(ROOT / 'scripts/parallel_checks.py')!r}); "
            "module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); "
            f"sys.exit(module.run_checks({checks!r}, {str(cwd)!r}))"
        )
        return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=20)

    def test_checks_overlap_and_success_opens_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            checks = {}
            for name, peer in (("first", "second"), ("second", "first")):
                code = (
                    "from pathlib import Path; import time; "
                    f"Path({name!r}).touch(); deadline = time.monotonic() + 5\n"
                    f"while not Path({peer!r}).exists() and time.monotonic() < deadline: time.sleep(.01)\n"
                    f"assert Path({peer!r}).exists(), 'Checks did not overlap'"
                )
                checks[name] = [sys.executable, "-c", code]
            result = self.run_gate(checks, directory)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_failure_closes_gate_but_waits_for_other_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_gate({
                "failure": [sys.executable, "-c", "raise SystemExit(7)"],
                "finishes": [sys.executable, "-c", "import time; from pathlib import Path; time.sleep(.2); Path('done').touch()"],
            }, directory)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertTrue((Path(directory) / "done").exists())
            self.assertIn("failure (exit 7)", result.stdout)
            self.assertIn("finishes (exit 0)", result.stdout)

    def test_missing_command_closes_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_gate({"missing": ["./missing-command"]}, directory)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("Failed checks: missing", result.stdout)
