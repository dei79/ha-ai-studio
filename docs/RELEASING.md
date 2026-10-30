# Container releases

Only pushing a version tag runs `.github/workflows/release.yml`. Regular branch pushes and pull requests run checks but do not publish images. Creating a tag only on your laptop does not trigger GitHub Actions. There is no manual release trigger and no `latest` image tag.

## Prepare a version

1. Update the quoted `version` in `ha_ai_studio/config.yaml` and `VERSION` in `ha_ai_studio/app/discovery.py` to the same `MAJOR.MINOR.PATCH` value.
2. Update `ha_ai_studio/CHANGELOG.md`, commit the release changes and push the commit to `main`.
3. Validate locally, then create and push the matching tag. For the current version:

```sh
python3 scripts/release_metadata.py --tag v0.0.1 --repository dei79/ha-ai-studio
git tag -a v0.0.1 -m "HA AI Studio 0.0.1"
git push origin v0.0.1
```

These commands are instructions, not performed automatically. Use a new version for every release; do not move published tags or overwrite a released version. Only stable numeric tag syntax is currently supported; prerelease suffixes are rejected. The app itself remains experimental.

## What the workflow does

- Validates the tag, app version, Discovery version, amd64 support and image destination before building.
- Builds the Ubuntu-based amd64 image with version, source, revision, license and Home Assistant labels.
- Runs unit/API/package tests, isolated MQTT tests, TLS/ACL tests, secret scanning and dependency/container audits.
- Logs in to GHCR using the workflow's `GITHUB_TOKEN` with `packages: write`.
- Tags and pushes the exact tested image as `ghcr.io/dei79/ha-ai-studio:0.0.1`; it does not rebuild after testing.

Any failed check stops publication. No extra registry password or personal access token is needed for the workflow. No HA deployment, tag creation or source commit is performed by the workflow.

## First publication and Home Assistant

The workflow is restricted to `dei79/ha-ai-studio`. Enable GitHub Actions and permit package publishing for this repository. If a package with this name already exists, grant this repository Actions access to it. The OCI source label links new images to the repository.

After the first publication, check **GitHub → Packages → ha-ai-studio → Package settings** and set visibility to **Public** if needed. A public source repository does not by itself guarantee public package visibility. Public images can be pulled anonymously; private images require registry authentication. The source repository must also be accessible to Home Assistant.

Add `https://github.com/dei79/ha-ai-studio` to HA's app repositories. Supervisor reads `repository.yaml` and the app's `config.yaml`, then pulls the image with the configured version tag, without the Git tag's `v` prefix. Wait for a successful release before installing or announcing that version. Refresh the app store to discover later version changes. Actual installation, upgrades, data retention and Ingress authentication must still be checked in a separate HA test installation before claiming a stable release.

Official references: [HA image configuration](https://contributors.home-assistant.io/apps/reference/configuration/#image), [HA repositories](https://contributors.home-assistant.io/apps/guides/repository/), [GHCR authentication and visibility](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).
