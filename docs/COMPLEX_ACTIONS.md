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
