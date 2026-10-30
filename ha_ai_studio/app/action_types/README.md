# Action plugins

Each trusted action type owns a directory under `action_types/`, registered explicitly in `__init__.py`. Currently only `echo` is installed. No workflow graph, arbitrary code execution, model upload or runtime plugin installation is supported.

A plugin provides:

- `metadata`: stable `type`, English `name` and `description`, `input_schema`, `output_schema`, and an example request.
- `validate(settings)`: validate type-specific configuration without side effects; raise a safe English `Invalid` error.
- `validate_input(message)`: validate the request envelope after common request-ID, JSON and size checks.
- `async execute(data, settings)`: return independent JSON data. Do not mutate inputs or access broker credentials. The runtime limits execution to 30 seconds.
- `editor.js`: export `render(host, settings, context)`; render safe DOM content and return a getter for settings. Call `context.changed()` on edits. Do not silently materialize defaults when merely viewing configuration.

Common infrastructure owns brokers, lifecycle, envelope validation, durable intent, deduplication, execution and delivery state. Production dispatch calls a single plugin directly; no internal MQTT activity messages exist. Input and output use configured external MQTT routes.

The UI test endpoint runs the submitted draft without connecting MQTT, writing production jobs or publishing results. Future plugins with side effects require an explicit safe preview design before they may be offered in this endpoint. Plugins are trusted code, not a sandbox. Adding a type requires rebuilding and testing the app.
