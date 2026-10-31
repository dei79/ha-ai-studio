import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SecurityChecksTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.log = self.directory / 'docker.jsonl'
        docker = self.directory / 'docker'
        docker.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
with open(os.environ['DOCKER_LOG'], 'a') as log:
    log.write(json.dumps(args) + '\\n')
if args[0] == 'save':
    pathlib.Path(args[args.index('-o') + 1]).touch()
sys.exit(int(os.environ.get('DOCKER_EXIT', '0')))
''')
        docker.chmod(0o755)
        self.env = dict(os.environ, PATH=f'{self.directory}:{os.environ["PATH"]}',
                        DOCKER_LOG=str(self.log),
                        SECURITY_GRYPE_CACHE_DIR=str(self.directory / 'cache'))
        self.env.pop('SECURITY_IMAGE_ARCHIVE', None)

    def run_check(self, mode):
        result = subprocess.run(['sh', str(ROOT / 'scripts/security-check.sh'), mode],
                                env=self.env, capture_output=True, text=True)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        return result, calls

    def test_supplied_archive_is_scanned_without_export_and_findings_fail(self):
        archive = self.directory / 'built image.tar'
        archive.touch()
        self.env.update(SECURITY_IMAGE_ARCHIVE=str(archive), DOCKER_EXIT='1')
        result, calls = self.run_check('image')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(calls), 1)
        self.assertIn(f'{archive}:/scan/image.tar:ro', calls[0])
        self.assertEqual(calls[0][-3:], ['docker-archive:/scan/image.tar', '--fail-on', 'high'])
        for setting in ('GRYPE_DB_AUTO_UPDATE=true', 'GRYPE_DB_VALIDATE_AGE=true',
                        'GRYPE_DB_VALIDATE_BY_HASH_ON_START=true'):
            self.assertIn(setting, calls[0])

    def test_missing_explicit_archive_fails_without_fallback(self):
        self.env['SECURITY_IMAGE_ARCHIVE'] = str(self.directory / 'missing.tar')
        result, calls = self.run_check('image')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [])

    def test_local_image_scan_exports_when_no_archive_is_supplied(self):
        result, calls = self.run_check('image')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls[0][:2], ['save', 'ha-ai-studio:dev'])
        self.assertEqual(calls[1][0], 'run')

    def test_database_update_uses_shared_cache_and_propagates_failure(self):
        self.env['DOCKER_EXIT'] = '3'
        result, calls = self.run_check('grype-db')
        self.assertEqual(result.returncode, 3)
        self.assertEqual(calls[0][-2:], ['db', 'update'])
        self.assertIn(f'{self.directory}/cache:/grype-db', calls[0])
        self.assertNotIn('/var/run/docker.sock', ' '.join(calls[0]))


if __name__ == '__main__':
    unittest.main()
