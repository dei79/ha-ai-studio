#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT INT TERM
# Versioned scanner images pinned to immutable manifests. No host Docker socket.
gitleaks='ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f'
grype='anchore/grype@sha256:621d56d1d68106b787022c81546f7e0a36202a25d1239f0c20195fab8c16f7ea'
docker run --rm -v "$PWD:/repo:ro" -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0=/repo "$gitleaks" git --redact --no-banner /repo
# Scan the intended working tree too, excluding ignored private local data.
python3 - "$scratch" <<'PY'
import pathlib, shutil, subprocess, sys
out=pathlib.Path(sys.argv[1])/'source';out.mkdir()
files=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z']).decode().split('\0')
for name in set(files):
    path=pathlib.Path(name)
    if not name or not path.is_file() or path.is_symlink():continue
    dest=out/path;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
PY
docker run --rm -v "$scratch/source:/source:ro" "$gitleaks" dir --redact --no-banner /source
docker run --rm --platform linux/amd64 -v "$PWD/ha_ai_studio/requirements.lock.txt:/requirements.lock.txt:ro" ha-ai-studio:dev sh -c 'pip install --quiet pip-audit==2.9.0 && pip-audit --disable-pip --no-deps -r /requirements.lock.txt'
docker save ha-ai-studio:dev -o "$scratch/image.tar"
docker run --rm -v "$scratch/image.tar:/scan/image.tar:ro" "$grype" docker-archive:/scan/image.tar --fail-on high
