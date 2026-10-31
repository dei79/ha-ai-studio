# Complex Action capabilities

Trusted Action manifests can opt into `"capabilities": ["assets", "preview"]`. Existing two-argument Actions retain their existing contract. With capabilities, the runner supplies a `context` keyword argument to `execute(data, settings, *, context)` and `preview(data, settings, *, context)`. Preview is available only when declared and implemented.

The private runtime context supplies `mode`, `assets_dir`, and, for preview, `output_dir`. Browser code receives no filesystem paths or broker credentials. A preview returns the normal output-schema result and may write PNG/JPEG output images into its supplied output directory. These are returned separately as scoped URLs. Both paths belong to the current instance. Trusted plugins are process-isolated, not sandboxed against malicious code.

## Editor SDK

The existing custom ES-module editor context additionally provides:

- `uploadImage(file)`: upload a private PNG/JPEG; returns `{id, width, height}`.
- `assetUrl(id)`: obtain the current instance's image URL.
- `removeImage(id)`: remove an unused image; saved configuration and job references are protected.
- `preview(data, settings)`: run the draft configuration without modifying saved configuration, jobs, last execution or MQTT delivery.
- `previewImageUrl(run, name)`: obtain a generated preview image URL.
- `changed()`: mark the draft as edited.

Use SDK URLs and relative module imports for Home Assistant Ingress compatibility. Pending SDK operations disable parent save/navigation and are aborted when the editor is disposed. Editors should ignore stale async results and implement their own busy indicators.

## Limits and isolation

Images are immutable, content-addressed and scoped per Action: 8 MiB, 16 MP, 8192 pixels per side, at most 128 images / 256 MiB. Assets remain private and are not part of repository exports. Upload validation checks supported headers and dimensions; the Action must safely decode the image too.

Preview requires an idle instance, validates input/settings/output schemas, uses a separate runner and retains at most eight preview directories for one hour. Each run permits 40 output images / 32 MiB. Failed, cancelled and timed-out runs are cleaned up. The usual 30-second runner timeout applies. Preview execution itself is trusted plugin code; plugins must implement a side-effect-free preview contract.

HTTP routes are `action-asset`, `action-asset-delete`, `action-preview` and `preview-image` under the existing API prefix and request protections. Do not construct direct filesystem URLs.

The sibling Analog Meter Reader demonstrates a TypeScript + SCSS editor compiled into portable JS/CSS, uploaded references, region editing and local inference. See its README for build commands and recognition limits.

## Home Assistant entities and device acquisition

Editors receive `context.pickEntity({domains: ['camera'], title: 'Camera'})`, a Promise resolving to `{entity_id, name, state, available}` or `null` on cancellation. Studio owns the searchable, accessible side dialog. It returns only entity ID, display name, state and availability, never attributes, camera access tokens or HA credentials. Supported filters: camera, light, switch. Entity searches are read-only and use the same relative API base under Ingress.

Trusted Actions can declare the `home_assistant` capability. In **execute only**, `context['home_assistant']` provides synchronous `state(entity_id)`, `capture(camera_entity)` (PNG/JPEG bytes), `light_on(light_or_switch)` and `restore(light_or_switch)`. Access is restricted to supported entity IDs present in that execution's immutable settings. A local private socket grants access only for the lifetime of the process. No HA token is included in runner JSON, environment or editor responses. These are trusted plugins, not a security sandbox.

Studio reserves the configured camera/illumination entities on first device operation; conflicting runs fail without switching devices. Capture count is bounded to two and image size to 8 MiB/16 MP. A light already on is left unchanged; brightness/color are not changed. Before switching a previously-off entity on, Studio durably records the required off-restoration. The Action restores it after acquisition and Studio repeats cleanup on error, cancellation or process timeout. Failed restoration remains journaled, is reported in Action issues and retried after restart; the original HA endpoint fingerprint must match. Studio cannot restore while HA or Studio is offline. New captures using a pending entity are blocked. External users/automations should not share the illumination entity during acquisition.

Acquisition sequencing remains in the Action. Studio supplies bounded operations and cleanup, not triggers, schedules or a workflow editor. Runtime budget for capability-bearing Actions is 180 seconds; editor previews remain 30 seconds and receive no device client. Camera still-image freshness depends on the camera integration; two fetches do not guarantee independent captures.

Local development reads `HA_URL` and `HA_ACCESS_TOKEN` from private `.env` through Compose. Optional `HA_ADDRESS_FAMILY=ipv4` resolves Docker IPv6 routing problems without disabling TLS checks. No `VITE_` credentials. Installed Apps use `SUPERVISOR_TOKEN` via the Core API proxy and declare `homeassistant_api: true`. Deployment permissions and real device switching require separate live validation.

`context.cameraTest(data, settings)` explicitly runs a device-enabled `camera_test` through the execute handler with a private output directory. It requires both preview and home_assistant capabilities and uses the execution device scope, timeout and restoration. Unlike ordinary preview it may switch configured illumination and fetch camera images. It never creates jobs, changes saved configuration or publishes MQTT. Actions may generate diagnostic images using output_dir. Automated UI tests must use synthetic HA fixtures only.

Camera tests accept an optional progress callback as the third `cameraTest` argument. Studio polls an instance- and run-scoped ephemeral log while the request runs. It contains timestamps, configured entity IDs, operation names and sanitized failures, never HA response bodies or credentials. Logs are bounded to 100 entries, eight runs per instance and one hour. They are not persisted to job history.
