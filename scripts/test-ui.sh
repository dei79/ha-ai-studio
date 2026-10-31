#!/bin/sh
set -eu
cd "$(dirname "$0")/../ha_ai_studio/frontend"
npm ci --no-audit --no-fund
npm run typecheck
npm test
