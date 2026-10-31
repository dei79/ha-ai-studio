"""Build a source-installable HA app from approved public files only."""
import gzip
import hashlib
import re
import tarfile
from pathlib import Path

APP_FILES = (
    '.dockerignore', 'config.yaml', 'Dockerfile', 'DOCS.md', 'CHANGELOG.md',
    'LICENSE', 'README.md', 'icon.png', 'logo.png', 'icon.svg', 'THIRD_PARTY.md', 'requirements.txt', 'requirements.lock.txt',
)
STATIC_FILES = ('index.html', 'app.js', 'ha-example.js', 'schema-editor.js', 'style.css')


def public_files(app):
    """Exclude private data, caches, captures and unregistered frontend assets."""
    files = [app / name for name in APP_FILES]
    files += [app / 'app' / 'static' / name for name in STATIC_FILES]
    files += sorted((app / 'app').rglob('*.py'))
    files += [app / 'app' / 'action_types' / 'README.md',
              app / 'app' / 'action_types' / 'legacy_echo' / 'editor.js']
    for path in files:
        if '__pycache__' in path.parts:
            continue
        if any(part.is_symlink() for part in (path, *path.parents)
               if part == app or app in part.parents):
            raise ValueError('Package inputs must not be symbolic links.')
        if not path.is_file():
            raise ValueError(f'Required package file missing: {path.name}')
        yield path


def build(root):
    app = root / 'ha_ai_studio'
    version = re.search(r'^version:\s*"(\d+\.\d+\.\d+)"\s*$',
                        (app / 'config.yaml').read_text(), re.MULTILINE)
    if not version:
        raise ValueError('App metadata must contain a quoted semantic version.')
    files = list(public_files(app))  # Validate before creating the archive.
    out = root / 'dist'
    out.mkdir(exist_ok=True)
    archive = out / f'ha-ai-studio-{version[1]}.tar.gz'
    with archive.open('wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w', format=tarfile.USTAR_FORMAT) as tar:
                for path in sorted(files):
                    info = tar.gettarinfo(path, arcname=str(path.relative_to(root)))
                    info.uid = info.gid = info.mtime = 0
                    info.uname = info.gname = ''
                    info.mode = 0o644
                    info.pax_headers = {}
                    with path.open('rb') as source:
                        tar.addfile(info, source)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (out / 'SHA256SUMS').write_text(f'{digest}  {archive.name}\n')
    return archive


if __name__ == '__main__':
    print(build(Path(__file__).resolve().parent.parent))
