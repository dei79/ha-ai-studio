import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import release_notes as notes


class ReleaseNotesTests(unittest.TestCase):
    def render(self, key='', opener=None):
        kwargs = {'opener': opener} if opener else {}
        return notes.render('Only Echo is implemented.', 'Change documentation',
            {'target': 'ghcr.io/example/studio:1.2.3'}, 'v1.2.3', 'example/studio',
            'v1.2.2', True, key=key, **kwargs)

    def test_version_section_required_and_isolated(self):
        text = '## 1.2.3\n\nNew notes.\n\n## 1.2.2\n\nOld notes.'
        self.assertEqual(notes.changelog_section(text, '1.2.3'), 'New notes.')
        with self.assertRaises(ValueError):
            notes.changelog_section(text, '1.2.4')

    def test_no_key_uses_maintained_changelog_and_installation(self):
        body, mode = self.render()
        self.assertEqual(mode, 'changelog')
        for expected in ('Only Echo', 'Experimental pre-release', 'amd64', 'compare/v1.2.2...v1.2.3', 'ghcr.io/example/studio:1.2.3'):
            self.assertIn(expected, body)

    def test_structured_api_request_and_render(self):
        def opener(request, timeout):
            payload = json.loads(request.data)
            self.assertEqual(request.full_url, 'https://api.openai.com/v1/responses')
            self.assertFalse(payload['store'])
            self.assertTrue(payload['text']['format']['strict'])
            self.assertEqual(timeout, 60)
            self.assertNotIn('test-secret', request.data.decode())
            result = {'status': 'completed', 'output': [{'type': 'message', 'content': [
                {'type': 'output_text', 'text': json.dumps({'summary': 'MQTT Actions for Home Assistant.', 'highlights': ['Echo returns JSON data.']})}]}]}
            return io.BytesIO(json.dumps(result).encode())
        body, mode = self.render('test-secret', opener)
        self.assertEqual(mode, 'ai')
        self.assertIn('## Highlights', body)
        self.assertIn('Only Echo is implemented.', body)
        self.assertNotIn('test-secret', body)

    def test_api_failure_never_logs_sensitive_exception(self):
        def failure(*args, **kwargs):
            raise RuntimeError('test-secret and private response')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            body, mode = self.render('test-secret', failure)
        self.assertEqual(mode, 'changelog')
        self.assertNotIn('test-secret', body + output.getvalue())
        self.assertNotIn('private response', output.getvalue())

    def test_malformed_refused_incomplete_responses_fall_back(self):
        cases = [b'not json', b'{}', b'{"status":"incomplete"}',
            json.dumps({'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'refusal', 'refusal': 'No'}]}]}).encode()]
        for data in cases:
            with self.subTest(data=data):
                _, mode = self.render('test-secret', lambda *a, **kw: io.BytesIO(data))
                self.assertEqual(mode, 'changelog')

    def test_git_baseline_first_release_and_previous_tag(self):
        # The unit-test container intentionally has no Git binary.
        import shutil
        if not shutil.which('git'):
            self.skipTest('Git range checks run on the host/CI runner')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.DEVNULL)
            git('init'); git('config', 'user.email', 'test@example.invalid'); git('config', 'user.name', 'Test')
            git('commit', '--allow-empty', '-m', 'First release'); git('tag', 'v1.0.0')
            self.assertEqual(notes.context(root, 'v1.0.0'), (None, 'First release'))
            git('commit', '--allow-empty', '-m', 'Second release'); git('tag', 'v1.0.1')
            self.assertEqual(notes.context(root, 'v1.0.1'), ('v1.0.0', 'Second release'))
