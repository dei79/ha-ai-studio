import importlib.util
from pathlib import Path
import re
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('release_metadata',ROOT/'scripts/release_metadata.py')
release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)

class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'ha_ai_studio/app').mkdir(parents=True)
        (self.root/'ha_ai_studio/config.yaml').write_text('version: "1.2.3"\narch: [amd64]\nimage: ghcr.io/example/studio\n')
        (self.root/'ha_ai_studio/app/discovery.py').write_text("VERSION = '1.2.3'\n")
    def test_tag_maps_to_supervisor_image_tag(self):
        self.assertEqual(release.validate(self.root,'v1.2.3','example/studio')['target'],'ghcr.io/example/studio:1.2.3')
    def test_non_release_and_mismatched_versions_fail(self):
        for tag in ('main','1.2.3','v01.2.3','v1.2.3-rc1','v1.2.4','v1.2.3\n'):
            with self.subTest(tag=tag),self.assertRaises(ValueError):release.validate(self.root,tag,'example/studio')
    def test_foreign_repository_and_stale_diagnostics_fail(self):
        with self.assertRaises(ValueError):release.validate(self.root,'v1.2.3','other/studio')
        (self.root/'ha_ai_studio/app/discovery.py').write_text("VERSION = '1.2.2'\n")
        with self.assertRaises(ValueError):release.validate(self.root,'v1.2.3','example/studio')

    @unittest.skipUnless((ROOT/'.github/workflows/release.yml').is_file(),'Workflow metadata is checked on the repository checkout')
    def test_repository_identity_is_consistent_across_release_inputs(self):
        repository='ha-ai-studio/ha-ai-studio'
        config=(ROOT/'ha_ai_studio/config.yaml').read_text()
        version=re.search(r'^version: "([^"\n]+)"$',config,re.MULTILINE).group(1)
        self.assertEqual(release.validate(ROOT,'v'+version,repository)['target'],'ghcr.io/'+repository+':'+version)
        self.assertIn("if: github.repository == '"+repository+"'",(ROOT/'.github/workflows/release.yml').read_text())
        self.assertIn('url: https://github.com/'+repository,(ROOT/'repository.yaml').read_text())
        self.assertIn('url: https://github.com/'+repository,config)
        self.assertIn('org.opencontainers.image.source="https://github.com/'+repository+'"',(ROOT/'ha_ai_studio/Dockerfile').read_text())
