# Container and GitHub releases

Only pushing a version tag runs `.github/workflows/release.yml`. Regular branch pushes and pull requests run checks but do not publish images. Creating a tag only on your laptop does not trigger GitHub Actions. There is no manual release trigger and no `latest` image tag.

## AI release notes setup

In **GitHub → Settings → Secrets and variables → Actions → Secrets**, add a repository secret named **`OPENAI_API_KEY`**. Never commit an API key or put it in a repository variable. The key is only passed to the release-notes step, not to the application or container build. Use an OpenAI project with an appropriate budget and API permissions.

Optionally add the repository **variable** `OPENAI_RELEASE_MODEL` to select a model supporting Responses API Structured Outputs. The default is `gpt-4o-mini`. One bounded request is made per release run, with a 60-second timeout and no automatic retries. API usage is billed to your OpenAI project.

Only the current version's changelog section and up to 100 commit subjects (12,000 characters) since the preceding reachable version tag are sent to OpenAI. For the first release, the history at that tag is used. No source code, runtime configuration, broker credentials or MQTT data are read or sent. Keep commit messages and the changelog free of private data. Responses use `store: false`; this does not override OpenAI's applicable retention policies.

The AI writes an English summary and highlights; the maintained changelog, installation instructions and source link are always included. Review the changelog before tagging: AI wording can be inaccurate. Missing keys, timeouts, refusals and invalid responses fall back to the changelog with a workflow notice/warning. A missing version-specific changelog stops the release. API error bodies and credentials are never logged.

## Prepare a version

1. Update the quoted `version` in `ha_ai_studio/config.yaml` and `VERSION` in `ha_ai_studio/app/discovery.py` to the same `MAJOR.MINOR.PATCH` value.
2. Update `ha_ai_studio/CHANGELOG.md`, commit the release changes and push the commit to `main`.
3. Validate locally, then create and push the matching tag. For example, after updating both version fields and the changelog to a new, unused version `0.0.4`:

```sh
python3 scripts/release_metadata.py --tag v0.0.4 --repository ha-ai-studio/ha-ai-studio
git tag -a v0.0.4 -m "HA AI Studio 0.0.4"
git push origin v0.0.4
```

These commands are instructions, not performed automatically. Use a new version for every release; do not move published tags or overwrite a released version. A workflow rerun uses the workflow at its original tagged commit. Repository-migration fixes therefore need a new commit and a new release version/tag; rerunning the skipped `v0.0.3` job does not pick up the corrected workflow. Only stable numeric tag syntax is currently supported; prerelease suffixes are rejected. The app itself remains experimental.

## What the workflow does

- Validates the tag, app version, Discovery version, amd64 support and image destination before building.
- Builds the Ubuntu-based amd64 image with version, source, revision, license and Home Assistant labels.
- Runs unit/API/package tests, isolated MQTT tests, TLS/ACL tests, secret scanning and dependency/container audits.
- Generates release notes using the OpenAI Responses API with a validated structured response, or the changelog fallback.
- Logs in to GHCR using the workflow's `GITHUB_TOKEN` with `packages: write`.
- Tags and pushes the exact tested image as `ghcr.io/ha-ai-studio/ha-ai-studio:<version>`; it does not rebuild after testing.
- Publishes a GitHub Release for the existing tag only after the container push succeeds, using `GITHUB_TOKEN` with `contents: write`. Experimental/beta app stages produce a GitHub pre-release, not the latest stable release. GitHub provides source archives automatically.

An existing GitHub Release is never overwritten: rerunning a completed release will fail at release creation. If GitHub release creation fails after the image push, the image remains published; resolve the error and rerun the failed job. Do not move the tag. AI text is passed through a notes file, never interpreted as shell code.

Any failed check stops publication. No extra registry password or personal access token is needed for the workflow. No HA deployment, tag creation or source commit is performed by the workflow.

## First publication and Home Assistant

The workflow is restricted to `ha-ai-studio/ha-ai-studio`. Enable GitHub Actions and permit package publishing for this repository. If a package with this name already exists, grant this repository Actions access to it. The OCI source label links new images to the repository.

After the first publication, check **GitHub → Packages → ha-ai-studio → Package settings** and set visibility to **Public** if needed. A public source repository does not by itself guarantee public package visibility. Public images can be pulled anonymously; private images require registry authentication. The source repository must also be accessible to Home Assistant.

Add `https://github.com/ha-ai-studio/ha-ai-studio` to HA's app repositories. Supervisor reads `repository.yaml` and the app's `config.yaml`, then pulls the image with the configured version tag, without the Git tag's `v` prefix. Wait for a successful release before installing or announcing that version. Refresh the app store to discover later version changes. Actual installation, upgrades, data retention and Ingress authentication must still be checked in a separate HA test installation before claiming a stable release.

Official references: [HA image configuration](https://contributors.home-assistant.io/apps/reference/configuration/#image), [HA repositories](https://contributors.home-assistant.io/apps/guides/repository/), [GHCR authentication and visibility](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).
