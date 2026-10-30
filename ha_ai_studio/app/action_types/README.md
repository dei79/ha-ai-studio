# Action plugins

Each trusted action type owns a directory under `action_types/`, registered explicitly in `__init__.py`. Currently only `echo` is installed. Bundled types are explicitly registered; trusted Git types use the separate process contract below. No workflow graph is supported.

A plugin provides:

- `metadata`: stable `type`, English `name` and `description`, `input_schema`, `output_schema`, and an example request.
- `validate(settings)`: validate type-specific configuration without side effects; raise a safe English `Invalid` error.
- `validate_input(message)`: validate the request envelope after common request-ID, JSON and size checks.
- `async execute(data, settings)`: return independent JSON data. Do not mutate inputs or access broker credentials. The runtime limits execution to 30 seconds.
- `editor.js`: export `render(host, settings, context)`; render safe DOM content and return a getter for settings. Call `context.changed()` on edits. Do not silently materialize defaults when merely viewing configuration.

Common infrastructure owns brokers, lifecycle, envelope validation, durable intent, deduplication, execution and delivery state. Production dispatch calls a single plugin directly; no internal MQTT activity messages exist. Input and output use configured external MQTT routes.

The UI test endpoint runs the submitted draft without connecting MQTT, writing production jobs or publishing results. Future plugins with side effects require an explicit safe preview design before they may be offered in this endpoint. Plugins are trusted code, not a sandbox. Adding a bundled type requires rebuilding and testing the app.

## Trusted Git action repositories

Settings → Action repositories accepts public HTTPS Git repositories and a branch,
tag or commit. Refresh reads metadata only. Existing instances stay pinned to their
original commit; refreshing changes the catalog for newly created instances only.
Local sources, private Git credentials and in-place version upgrades are not yet supported.

Repository layout:

```text
actions/example/action.json
actions/example/action.py
actions/example/requirements.lock
```

Example `action.json` (Python must match the app runtime, currently 3.12):

```json
{
  "id": "example",
  "name": "Example",
  "description": "Return JSON data unchanged.",
  "version": "1.0.0",
  "python": "3.12",
  "entrypoint": "action.py",
  "settings_schema": {"type": "object", "additionalProperties": false},
  "input_schema": {},
  "output_schema": {},
  "example": {"request_id": "example-001", "data": {"message": "Hello"}}
}
```

`input_schema` and `output_schema` validate the JSON **data**, not the transport
envelope. Schemas use JSON Schema Draft 2020-12; references are unsupported.
The settings editor supports primitive properties and falls back to a JSON editor
for complex schemas. Repository JavaScript is never served to the browser.

`action.py` exports `execute(data, settings)`, either sync or async, returning finite
JSON. Sibling Python modules are supported. Stdout and stderr are discarded; the
application shows safe lifecycle diagnostics rather than arbitrary plugin output.
Execution is limited to 30 seconds and 65536 bytes of runner output.

`requirements.lock` can be empty for stdlib-only actions. Otherwise each requirement
must have an exact version and SHA256 hashes, including all transitive dependencies:

```text
package-name==1.2.3 --hash=sha256:<64 hexadecimal characters>
```

Standard backslash continuations are supported. Only registry wheels are installed;
source builds, direct URLs, editable/local requirements and installer options are
unsupported. No system packages are installed dynamically.

Creating an instance queues installation into its own persistent venv. Only Ready
environments can execute or activate. Rebuild requires an inactive, idle instance.
Interrupted installations fail closed and require an explicit rebuild. Environments
are checked for interpreter compatibility on restart. Failed installations expose
only fixed English diagnostics. Raw subprocess output and inherited app credentials
are never exposed. The immutable plugin binding is persisted with each job before
execution; execution and MQTT delivery retain their separate durable states.

**Trust boundary:** a venv isolates dependencies, not files, processes or networking.
Repository code runs with the app's OS permissions and must be trusted. A separate
process and filtered environment do not provide a security sandbox. Git Actions have
no draft preview until a safe preview contract is implemented. Use isolated brokers
and synthetic data for integration testing. Built-in Echo remains unchanged.
