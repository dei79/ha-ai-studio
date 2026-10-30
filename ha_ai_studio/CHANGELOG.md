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
