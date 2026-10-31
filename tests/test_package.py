"""Public source archives must not expose host metadata or private files."""
import importlib.util
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless((ROOT/'scripts/package.py').exists(),'Packaging runs separately on the repository checkout')
class PackageTests(unittest.TestCase):
    def test_reproducible_private_metadata_and_license(self):
        spec=importlib.util.spec_from_file_location('packager',ROOT/'scripts/package.py')
        packager=importlib.util.module_from_spec(spec);spec.loader.exec_module(packager)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            shutil.copytree(ROOT/'ha_ai_studio',root/'ha_ai_studio',ignore=shutil.ignore_patterns('__pycache__', 'node_modules', 'dist'))
            (root/'ha_ai_studio/.env').write_text('PRIVATE=not-for-release')
            archive=packager.build(root);first=archive.read_bytes()
            with tarfile.open(archive) as tar:
                self.assertNotIn('ha_ai_studio/.env',tar.getnames())
                self.assertIn('ha_ai_studio/app/action_types/legacy_echo/editor.js',tar.getnames())
                self.assertIn('ha_ai_studio/frontend/src/features/SchemaEditor.tsx',tar.getnames())
                self.assertNotIn('ha_ai_studio/app/action_types/echo/editor.js',tar.getnames())
                self.assertEqual(tar.extractfile('ha_ai_studio/LICENSE').read(),(ROOT/'LICENSE').read_bytes())
                for item in tar:
                    self.assertEqual((item.uid,item.gid,item.uname,item.gname,item.mtime,item.mode),(0,0,'','',0,0o644))
                    self.assertFalse(item.pax_headers)
            for file in (root/'ha_ai_studio').rglob('*'):
                if file.is_file():os.utime(file,(123456789,123456789));file.chmod(0o600)
            self.assertEqual(packager.build(root).read_bytes(),first)
            target=root/'ha_ai_studio/frontend/src/styles/main.scss';target.unlink();target.symlink_to(ROOT/'ha_ai_studio/frontend/src/styles/main.scss')
            with self.assertRaises(ValueError):packager.build(root)

if __name__=='__main__':unittest.main()
