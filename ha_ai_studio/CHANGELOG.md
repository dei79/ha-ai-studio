## Unreleased

- Add the MIT license to source, install archives and runtime images.
- Drain blocking MQTT operations before closing clients during shutdown; record interrupted output delivery as unknown.
- Make source archives reproducible and remove local user, group and timestamp metadata.
- Add CI gates for unit/API tests, MQTT/TLS/ACL integration, package validation, secret scanning and vulnerability audits.
- Update aiohttp to 3.14.5, pin its new packaging dependency, use a minimal Ubuntu 24.04 LTS container with distribution Python and an isolated virtual environment.
- Remove the historical verification report.

## 0.11.0

- Persist an explicit instance ID and include it in Studio and Action Discovery device names; preserve existing MQTT and entity identifiers.

- Standardize app directory, slug, development containers, environment variables and request header on HA AI Studio naming. A renamed slug requires a separate HA installation and explicit data migration.

- Add optional Home Assistant MQTT Discovery with stable identities and durable retained-topic cleanup.
- Configure Discovery with the broker in a shared side panel and save both together.
- Add safe broker connection diagnostics and a terminal-style log.
- Standardize side-panel headers, scrolling content, fixed footers and icon actions.
- Add a copyable Home Assistant test automation with result notifications and a step-by-step guide.
- Remove historical UI captures, obsolete build artifacts, unused imports and the unused development mode setting.
- Restrict source packages to approved runtime files and derive their version from app metadata.

## 0.10.0

- Replace the workflow builder with configured Actions; Echo is the only installed type.
- Separate Input, type settings and Output configuration, with draft save, isolated test, activation and deactivation.
- Preserve old Agent files and IDs as unsupported inactive records; no automatic Echo conversion.
- Retain shared broker Settings, add active-route cycle detection and MQTT v5 live-retained rejection.
- Persist intent, result and separate delivery status; generation-guard queued requests across configuration changes.
- Add English request/result automation examples and isolated two-broker tests.

## 0.9.0

- Shared MQTT brokers in Settings, optional Supervisor-discovered default.
- Name-only agent creation; Input selects broker/topic and Output can select another broker.
- Draft isolation, persistent original retry routes, broker reference protection and feedback prevention.
- Credentials are redacted; connection tests publish no messages.

# 0.8.0

- Reduce the app to MQTT Input, chained Map JSON fields and MQTT Output.
- Isolate each activity's metadata, validation, execution and editor in its own plugin directory.
- Replace raw mapping JSON with input-path/output-field rows.
- Remove camera, recognition, calibration, model files and their dependencies/endpoints.
- Preserve old state while blocking unsupported workflows; keep stable MQTT identities.
- Retain persistent request deduplication, correlated non-retained MQTT, isolated agents and Ingress-relative loading.
- Support up to 64 linear steps, including direct Input → Output passthrough.
