#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT INT TERM
# Versioned scanner images pinned to immutable manifests. No host Docker socket.
gitleaks='ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f'
grype='anchore/grype@sha256:621d56d1d68106b787022c81546f7e0a36202a25d1239f0c20195fab8c16f7ea'
check_secrets() {
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
}

check_dependencies() {
  docker run --rm --platform linux/amd64 -v "$PWD/ha_ai_studio/requirements.lock.txt:/requirements.lock.txt:ro" ha-ai-studio:dev sh -c 'pip install --quiet pip-audit==2.9.0 && pip-audit --disable-pip --no-deps -r /requirements.lock.txt'
}

run_grype() {
  cache_dir=${SECURITY_GRYPE_CACHE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/ha-ai-studio/grype}
  mkdir -p "$cache_dir"
  cache_dir=$(cd "$cache_dir" && pwd)
  docker run --rm --user "$(id -u):$(id -g)" --tmpfs /tmp:rw,nosuid,nodev,mode=1777 \
    -e GRYPE_DB_CACHE_DIR=/grype-db \
    -e GRYPE_DB_AUTO_UPDATE=true -e GRYPE_DB_VALIDATE_AGE=true \
    -e GRYPE_DB_VALIDATE_BY_HASH_ON_START=true \
    -v "$cache_dir:/grype-db" "$@"
}

check_image() {
  archive=${SECURITY_IMAGE_ARCHIVE:-}
  if [ -z "$archive" ]; then
    archive="$scratch/image.tar"
    docker save ha-ai-studio:dev -o "$archive"
  fi
  # An explicitly supplied archive must exist; never silently scan another image.
  if [ ! -f "$archive" ]; then
    echo 'Security image archive does not exist.' >&2
    return 1
  fi
  archive=$(cd "$(dirname "$archive")" && pwd)/$(basename "$archive")
  run_grype -v "$archive:/scan/image.tar:ro" "$grype" docker-archive:/scan/image.tar --fail-on high
}

case "${1:-all}" in
  all) check_secrets; check_dependencies; run_grype "$grype" db update; check_image ;;
  secrets) check_secrets ;;
  dependencies) check_dependencies ;;
  grype-db) run_grype "$grype" db update ;;
  image) check_image ;;
  *) echo 'Usage: ./scripts/security-check.sh [all|secrets|dependencies|grype-db|image]' >&2; exit 2 ;;
esac
