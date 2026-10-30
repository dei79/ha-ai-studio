# Project rules

## Product and UI
- Home Assistant owns triggers, schedules, conditions and follow-up actions. This app executes individual configured Actions, not workflows.
- The Actions table is the main page. Create action opens a right-hand side panel with name and action type. Editing opens a separate configuration page with Input, type settings and Output. No workflow diagram, mappings, templates or activity chains.
- Only Echo is implemented. Each type has its own directory under `ha_ai_studio/app/action_types/`, with schemas, validation, execution and editor; register it explicitly.
- Keep the Home Assistant visual style: HA blue, compact navigation, plain cards and clear textual states. All UI, errors, protocol diagnostics and documentation must be English.
- Use only the embedded Codex browser (IAB) for interactive and visual testing; reuse the existing tab. No external Playwright, Chrome or Safari.

## MQTT and state
- Local operation uses the same real MQTT behavior as the HA app; do not show a DEV banner. In HA, additionally discover the supplied MQTT broker automatically at startup.
- Shared brokers live in Settings. Offer an HA default only after successful Supervisor discovery. Optional private .env adds a read-only development broker; no invented defaults or simulation fallback.
- Input selects broker/request topic; Output defaults to Same as input or selects another broker/result topic. Connect only active Actions; reject route cycles, including between active Actions. Ignore result envelopes on request topics as defense against external bridges/aliases.
- Use MQTT v5 with Retain As Published to reject both live and replayed retained requests. Requests/results use QoS 1 and retain off. No internal activity MQTT.
- Keep drafts separate from active configuration. UI tests must never publish to MQTT or modify production job state.
- Persist request digest and configuration before execution. Deduplicate per action/ID, reject changed payloads, do not rerun interrupted work. Persist execution and delivery separately; do not promise exactly-once delivery.
- Use the HA AI Studio naming consistently. Preserve private data and broker credentials; future identity changes require an explicit migration. Old agents/workflows are unsupported and inactive; never automatically convert them to Echo.
- Never expose broker credentials in browser responses or logs. Do not include private data, images, addresses or secrets in public files/packages.

## Scope and verification
- Work only in this development copy; do not change live HA or ESPHome, publish or deploy without an explicit request.
- Start/rebuild locally with `docker compose up -d --build`; URL `http://localhost:8099`. Dev uses real configured brokers; tests use isolated brokers and synthetic data.
- Run `./scripts/test.sh` and `./scripts/test-mqtt.sh`. Check all JSON values, ID conflicts, deduplication, restart, retained requests, delivery failures, disabled subscriptions, legacy preservation, secrets and cycle protection.
- In IAB check creation, editing, draft test, activation, deactivation, deletion, desktop/tablet and Ingress subpaths including plugin editor imports.
- Only amd64 is supported. Live HA authentication and production TLS need separate validation.

## Optional Home Assistant discovery
- Central Discovery is explicitly enabled on one selected broker, independent of Action routes; never publish discovery automatically from Input connections.
- Preserve stored identities and existing status unique IDs. Only advertise supported configured instances; disabled remains a diagnostic state.
- Persist exact owned topics before publication. Empty retained cleanup must be durable, scoped to owned topics, and retried before broker/prefix migration completes.
- Keep private broker connection snapshots for pending cleanup; protect referenced broker deletion/endpoint edits. Never expose snapshots or payloads in diagnostics or browser responses.
- Reject Action routes overlapping discovery/configuration/state/HA-birth topics, including cached retry destinations. Publish request/result messages with retain off.
- Test birth, real reconnect, clean offline, hard-kill LWT, A/B/C isolation, interrupted cleanup/restart/recovery, persistence failures and UI-test isolation. Distinguish isolated MQTT validation from actual HA integration testing.

- Side panels use a shared 640px width capped at the viewport width and share a contrasting 64px header aligned with the blue app header. Group connection identity/status in one card with a traffic-light indicator plus explicit text; logs use neon green on black, fill remaining height and scroll without wrapping.

- Side panels have a fixed footer for primary and confirmation buttons. Keep the header and footer visible while only the body scrolls; associate footer submit buttons with their forms.
