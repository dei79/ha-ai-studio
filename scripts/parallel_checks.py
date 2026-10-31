"""Check an already-built image; fail the gate if any check fails."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
CHECKS = {
    "Unit, API and package tests": ["./scripts/test.sh", "--skip-build"],
    "MQTT integration tests": ["./scripts/test-mqtt.sh"],
    "TLS and topic permissions": ["./scripts/test-mqtt-security.sh"],
    "Security checks": ["./scripts/security-check.sh"],
}


def run_checks(checks, cwd=ROOT):
    def run(command, log):
        try:
            return subprocess.run(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT).returncode
        except OSError as error:
            log.write((str(error) + "\n").encode())
            return 1

    failed = []
    with tempfile.TemporaryDirectory(prefix="studio-checks-") as directory:
        with ThreadPoolExecutor(max_workers=len(checks)) as executor:
            futures = {}
            for index, (name, command) in enumerate(checks.items()):
                log = open(Path(directory) / f"{index}.log", "w+b")
                print(f"Starting: {name}", flush=True)
                futures[executor.submit(run, command, log)] = (name, log)
            # Wait for every suite, even after a failure, so all results are visible.
            for future in as_completed(futures):
                name, log = futures[future]
                code = future.result()
                print(f"::group::{name} (exit {code})", flush=True)
                with log:
                    log.seek(0)
                    shutil.copyfileobj(log, sys.stdout.buffer)
                print("\n::endgroup::", flush=True)
                if code:
                    failed.append(name)
    if failed:
        print("Failed checks: " + ", ".join(failed), flush=True)
        return 1
    print("All checks passed.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(run_checks(CHECKS))
