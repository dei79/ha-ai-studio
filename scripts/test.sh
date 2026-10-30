#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
docker compose build --quiet
docker run --rm --platform linux/amd64 -v "$PWD/tests:/workspace/tests:ro" -v "$PWD/scripts:/workspace/scripts:ro" -v "$PWD/ha_ai_studio:/workspace/ha_ai_studio:ro" -v "$PWD/LICENSE:/workspace/LICENSE:ro" ha-ai-studio:dev python -m unittest discover -s /workspace/tests -v
