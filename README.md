# HA AI Studio — Actions

Home Assistant orchestrates; HA AI Studio executes single configured Actions. This release includes only **Echo**, a technical MQTT test that returns JSON data unchanged. No workflows, mappings or model runtimes are included.

## Local development

```sh
docker compose up -d --build
```

Open http://localhost:8099. Add real MQTT brokers in **Settings**, then create an Action with a name and type. Edit Input broker/topic and Output broker/topic (default: Same as input). Under **General**, select **Active** and click **Save** to enable the production subscription. Clear **Active** and save to stop it. Changes remain local to the editor until saved. **Message schemas** opens a side panel; **Test in Home Assistant** provides a copyable MQTT test automation.

Local state persists in private `.dev-data`, excluded from builds/packages. `.env` is optional: copy `.env.example` and supply `DEV_MQTT_HOST`, port, username, password and TLS to add a read-only broker. Recreate the container after changes. No HA API token is needed. Production discovers HA's MQTT service through Supervisor only when available; otherwise add a broker manually. MQTT v5 brokers are required. No simulation fallback exists.

Optional **Settings → edit broker → Enable MQTT Discovery** announces Studio and configured Actions with availability and diagnostic entities. Explicitly select the broker used by HA and enable discovery; Input and Output remain independent.

## Install

After the first successful container release, add `https://github.com/ha-ai-studio/ha-ai-studio` under **Settings → Apps → Install app → ⋮ → Repositories**, then install **HA AI Studio** and open its web UI through Ingress. This requires Home Assistant with Supervisor on amd64. The repository and GHCR package must be public for installation without registry credentials. The app is marked experimental. Action types are installed from Git repositories in Settings. Echo is maintained in the separate `ha-ai-studio-actions-core` repository; existing bundled Echo instances remain supported without automatic migration.

Home Assistant pulls `ghcr.io/ha-ai-studio/ha-ai-studio:<version>` using the version in `ha_ai_studio/config.yaml`; it does not build the image on the device. Before the first successful tag workflow, that image does not exist. Repository metadata can become visible before a tag build finishes, so announce an update only after publication succeeds.

`python3 scripts/package.py` also creates an archive in `dist/`. To build that source locally inside HA instead of pulling the released image, extract `ha_ai_studio` into HA's local apps directory and remove the `image:` line from the extracted `config.yaml` before refreshing/installing. The source slug is `ha_ai_studio`; repository and local installations may have different full app IDs and data locations. Back up data before switching. Nothing is installed in live HA by local development commands.

See [release instructions](docs/RELEASING.md).

Existing Agents are shown as **Unsupported · Disabled**. Their files, identities and credentials remain intact; create a new Echo Action explicitly. They are not converted. Deletion removes an Action from the active registry and stops subscriptions but retains files and reserves its ID; there is no restore UI.

See [the guide and HA automation examples](ha_ai_studio/DOCS.md), [plugin contract](ha_ai_studio/app/action_types/README.md) and [architecture](docs/ARCHITECTURE.md).

```sh
./scripts/test.sh
./scripts/test-ui.sh  # Frontend regressions; requires Node.js 22.7+, no npm dependencies
./scripts/test-mqtt.sh
./scripts/test-mqtt-security.sh
python3 -m unittest discover -s tests -p test_package.py -v
./scripts/security-check.sh
python3 scripts/package.py
```

The MQTT check uses three temporary isolated Mosquitto brokers, never personal credentials. For local subpath testing run `docker compose --profile ingress up -d` and open http://localhost:8100/api/hassio_ingress/dev-check/. This is not a live HA authentication test.

## Repository layout

- `ha_ai_studio/`: installable HA app, runtime code, static UI, dependency manifest/lock and user guide.
- `ha_ai_studio/app/action_types/`: explicitly registered Action plugins; currently Echo only.
- `tests/`: unit/API checks and isolated MQTT integration checks.
- `scripts/`: test runners, local Ingress proxy and source packaging.
- `docs/`: architecture and verification report.

`requirements.txt` lists direct dependencies; `requirements.lock.txt` pins the complete runtime environment used by Docker. Keep both when updating dependencies. The app directory is `ha_ai_studio/`, the Compose service is `studio`, and the development image is `ha-ai-studio:dev`.

Generated archives, browser captures and local caches do not belong in the source tree. Keep private `.env` and `.dev-data/` out of source control and packages. The packager includes only approved app files and rejects symlinks.

## Naming migration

This development copy uses the app slug `ha_ai_studio`, environment variables `HA_AI_STUDIO_DATA` and `HA_AI_STUDIO_DEV`, and request header `X-HA-AI-Studio-Request`. A changed app slug is a separate installation in Home Assistant: existing installations do not receive an automatic in-place upgrade. Back up and transfer app data explicitly before switching installations.

Changing stored MQTT identities changes Discovery entities and request/result topics. Recreate copied HA test automations using the current topics. Preserve the Discovery ownership manifest and its cleanup credentials until the old retained topics have been removed. Do not run two copies against the same data directory or identities.

## License

MIT — see [LICENSE](LICENSE). Third-party notices are listed in [THIRD_PARTY.md](ha_ai_studio/THIRD_PARTY.md).

## Automated checks

GitHub Actions runs unit/API tests, isolated MQTT integration tests, TLS and publish-ACL checks, reproducible packaging checks, full-history and working-tree secret scans, Python dependency auditing, and container vulnerability scanning. Security scanner images and checkout are pinned to immutable identifiers. Python advisories and High/Critical container findings fail the checks; scanner failures also fail closed. The separate release workflow publishes a versioned GHCR image only when a `vMAJOR.MINOR.PATCH` tag is pushed. After the image push, it creates a GitHub Release with AI-assisted English notes and the maintained changelog (changelog fallback if OpenAI is unavailable). See [release setup](docs/RELEASING.md) for the `OPENAI_API_KEY` Actions secret. It never deploys to Home Assistant.

The security check downloads public advisory databases and requires Internet access. All MQTT integration checks use disposable containers, generated test certificates and synthetic credentials. They never use `.env` or `.dev-data`.

Actual Supervisor/Ingress authentication and install/upgrade acceptance still require a separate Home Assistant test installation. The local subpath proxy does not verify HA authentication. No live HA installation is changed by these scripts.

The runtime uses the official Ubuntu 24.04 LTS container base, pinned by digest. Only Python, virtual-environment support and CA certificates are installed, without recommended packages. App dependencies live in `/opt/venv`; Ubuntu manages the system Python. Support remains limited to amd64.
