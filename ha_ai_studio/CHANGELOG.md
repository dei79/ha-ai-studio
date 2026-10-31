## Unreleased

- Isolate Git schema checks in cancellable worker processes with CPU, memory, concurrency and wall-time limits so expensive schemas cannot block the Studio server.
- Add HTTP liveness, validation recovery and worker cleanup regression coverage.

## 0.0.4

- Update the release workflow repository guard to the ha-ai-studio organization so release jobs run after the repository transfer.
- Publish container images under ghcr.io/ha-ai-studio/ha-ai-studio and align app metadata, repository URLs, OCI source labels and installation documentation.
- Add a regression check for consistent repository identity across release inputs.

The app remains experimental and amd64-only. The schema-validation limitation documented for 0.0.3 still applies.

## 0.0.3

- Install dynamic action types from Git repositories into isolated per-instance Python environments with pinned commits and locked dependencies.
- Move new Echo instances to the separate Actions Core repository while preserving existing bundled Echo instances and their identities.
- Include Actions Core as a protected System repository; allow deletion of unused user repositories.
- Show installation details from the Actions table, with status, version, logs and environment rebuild controls in a side panel.
- Align Settings cards and use consistent borderless repository action buttons.
- Fix environment executable lookup, manifest message schemas, optional numeric settings and visible installation errors.
- Bound subprocess output and cleanup, validate execute signatures before Ready, and validate request examples before offering Home Assistant test templates.
- Add Python and frontend regression coverage for repository lifecycle, isolated execution and failure recovery.

Known limitation: plugin schema validation still runs in the server process. Certain regular expressions can block the app; bounded schema validation remains an open high-priority issue. This release remains experimental and amd64-only.

## 0.0.2

- Add app store branding with an icon, logo and an introduction to AI Actions.
- Generate English release summaries and highlights using OpenAI, with the maintained changelog as a fallback when the API is unavailable or not configured.
- Publish GitHub Releases after successful container publication, including installation instructions and a link to the source changes.
- Mark experimental releases as pre-releases and document secure API key configuration through GitHub Actions secrets.

The app remains experimental and amd64-only. Echo is the only implemented Action type; AI release-note generation runs in CI, not in the application.

## 0.0.1

First experimental release of HA AI Studio.

- Configure Echo Actions with independent MQTT input/output brokers and validated JSON message contracts.
- Follow incoming requests, processing and outgoing replies in the per-Action live activity view.
- Use optional Home Assistant MQTT Discovery with a stable installation identity and durable cleanup.
- Configure brokers and inspect connection diagnostics through the Home Assistant-style Ingress UI.
- Persist request IDs and results, reject retained requests and route loops, and drain MQTT operations safely during shutdown.
- Run on Ubuntu 24.04 LTS; amd64 is the only supported architecture.
- Publish versioned GHCR images only from version tags after tests and security checks.
- Include MIT licensing and reproducible source archives without local filesystem metadata.

Only Echo is implemented; no AI inference model is included yet. Actual HA installation and upgrade acceptance remain to be validated before a stable release.
