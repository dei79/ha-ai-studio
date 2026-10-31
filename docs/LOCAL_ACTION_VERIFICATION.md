# Local Action sources and custom configuration editors

Verified locally on 2026-10-31. No deployment or live Home Assistant changes.

## Result

Development Compose mounts the sibling `ha-ai-studio-actions-ai-on-the-edge-meters` directory read-only. The local source `.` is registered and Ready in the local server at `http://localhost:8099`; **Meter reading example** is available for instance creation. No test Action was activated against a real configured broker.

Local source refresh validates and snapshots files without executing them. Explicit reload requires an inactive, idle instance, preserves identity/configuration/request history, and rebuilds its private Python environment. An optional `ui/editor.js` module supplies the configuration editor, including relative module imports under Ingress. Editor failure does not prevent independent deactivation. Input, Output and saving remain Studio-owned.

## Verification

- `./scripts/test.sh`: 99 tests, success; one release-check test skipped inside the container because workflow metadata is not mounted.
- `python3 -m unittest discover -s tests -p test_release.py -v`: all four release checks passed on the actual checkout, including that skipped check.
- Final `docker compose up -d --build`: frontend 19 tests, TypeScript check and production bundle passed; local server restarted successfully.
- `./scripts/test-mqtt.sh`: both isolated MQTT and discovery suites passed, including real A/B/C brokers, restart, deduplication/conflicts, retained request rejection, delivery retry, reconnect, clean offline/hard-kill LWT and UI-test isolation.
- Example repository: three Python unit tests passed (defaults/no mutation, scaling/zero, overflow).
- IAB only: synthetic UI fixture at direct and Ingress paths. Added a local source, created an Action, loaded the actual example editor and its relative `fields.js` import, edited/saved values including zero, activated/deactivated, reloaded, deleted and ran the compatibility draft test. Desktop and 768px tablet layouts inspected; no browser errors reported. Fixture never connects to MQTT or production storage.
- Backend local-source regressions cover symlink root escape, traversal, disabled local support, excluded private files, asset allowlisting, pinned code/history, restart, invalid source/settings, registry/queue persistence failure, and a barrier-controlled concurrent refresh/reload race.
- Backend, frontend and test-strategy subagent reviews completed; HIGH findings fixed. Follow-up backend review found no remaining HIGH issue.

## Limits

Custom editors and Python Actions are trusted code, not sandboxes. Local sources require explicitly configured development mode. Incompatible settings-schema changes reject reload; temporarily retain compatibility or create a new inactive instance from the refreshed catalog. There is no automatic settings migration. Git/local draft execution remains unavailable. The example performs numeric normalization only, with no device access, image recognition or external APIs. Actual HA authentication, production TLS and live HA integration were not validated.

## Changed files

Studio:

- `.env.example`, `compose.yaml`: explicit local source root and read-only host mount.
- `ha_ai_studio/app/plugins.py`: local source snapshots, manifest editor metadata and historical snapshot retention.
- `ha_ai_studio/app/actions.py`: guarded durable local reload.
- `ha_ai_studio/app/server.py`: reload API and bound-snapshot UI assets.
- `ha_ai_studio/frontend/src/features/SettingsPage.tsx`: local source selection.
- `ha_ai_studio/frontend/src/features/ActionEditor.tsx`: custom editor, local reload, independent deactivation.
- `ha_ai_studio/frontend/src/features/SchemaEditor.tsx`: trusted module lifecycle/getter/cleanup.
- `ha_ai_studio/frontend/src/lib/types.ts`, `ha_ai_studio/frontend/vite.config.ts`: typed contracts and development asset proxy.
- `tests/test_local_plugins.py`, `tests/ui_fixture.py`, `ha_ai_studio/frontend/src/regressions.test.tsx`: backend, synthetic UI and frontend regressions.
- `AGENTS.md`, `README.md`, `ha_ai_studio/app/action_types/README.md`, `ha_ai_studio/frontend/README.md`, `docs/LOCAL_ACTION_VERIFICATION.md`: current rules, usage, editor contract and verification.

Sibling example directory `ha-ai-studio-actions-ai-on-the-edge-meters`:

- `.gitignore`, `README.md`.
- `actions/meter-reading/action.json`, `action.py`, `requirements.lock`.
- `actions/meter-reading/ui/editor.js`, `ui/fields.js`.
- `tests/test_meter_reading.py`.
