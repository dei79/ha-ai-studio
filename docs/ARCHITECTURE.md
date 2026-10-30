# Actions architecture

Home Assistant orchestrates. The aiohttp app serves an Actions table, a configuration page and Settings over relative paths that remain under HA Ingress. No workflow/activity engine or JSON mapping runtime remains.

`Studio` retains `agents.json`, private `agents/<id>/` directories, stored identity prefixes and MQTT namespaces for compatibility. Only records explicitly created with an installed `action_type` can execute. Unsupported records expose a disabled legacy state without rewriting original configuration files.

Each `ActionService` owns `action-config.json` (draft, active, enabled), `action-jobs.json` (256 durable intents/results and execution/delivery states) and `action-last.json`. Atomic writes and private filesystem permissions come from the existing Store. A service lock serializes production requests and mutations. Subscription generations travel with queue entries and are checked again under the execution lock, preventing dequeued old requests from crossing activation boundaries.

`action_types/echo/` supplies schemas, validation, async execution and its editor. An explicit registry controls which plugins and editor files are available. Plugins run directly; no internal MQTT dispatch remains. Future side-effecting plugins require a separate safe test contract before enabling previews.

Shared broker infrastructure stores manual credentials privately; optional environment and discovered Supervisor credentials normally stay in memory; Discovery pins private cleanup connection snapshots while it owns retained topics. The route validator builds a graph of active input/output destinations, rejects duplicate inputs and cycles, and rechecks topology on manual broker endpoint changes. Result-envelope suppression protects against external routing and unrecognized aliases.

MQTT uses v5 with Retain As Published so live retained messages are rejected as well as stored replay. Connections become ready only after successful subscription acknowledgement. Input handles requests only; each output attempt uses a publisher-only connection to the configured output broker. Results use QoS 1, retain false. There is no exactly-once delivery or automatic resend promise.

Production stores a digest and configuration snapshot before invoking the plugin. A saved result is replayed without execution; unfinished intents are interrupted. Delivery state is separate and becomes unknown after a crash during pending delivery. UI tests call a separate endpoint with the submitted draft, and never write production jobs or open MQTT connections.

## Central discovery (0.11.0)

`Discovery` is a Studio-owned background service, separate from Action subscriptions and output publishers. `discovery.json` holds optional configuration and an exact-topic ownership manifest. The manifest is atomically persisted before any retained publication; failed writes restore committed memory state. Each acknowledged empty retained cleanup removes one topic from the durable manifest. Retry is idempotent. All old-target cleanup completes before announcements at the new target.

`broker-cleanup.json` is a private broker-registry snapshot keyed by broker reference and endpoint digest. It preserves required connections if Supervisor/environment lookup disappears or changes; matching live credentials take precedence. Snapshots are pruned after their ownership records are cleared. Public discovery responses contain configuration, safe status and cleanup counts only. No addresses or credentials are embedded in ownership records or Discovery payloads.

The dedicated MQTT v5 client subscribes to HA birth (including retained online), declares an availability Last Will and publishes offline on orderly close. Its stable installation-specific client ID is separate from Input and Output clients. A reconnect clears the publication cache; repeated announcements use the same unique IDs. Diagnostic refresh is asynchronous, normally every 500 ms, and never blocks on an Action's calculation. Brief transient execution/delivery states may not be observed. Unknown delivery after restart remains explicit.

Broker and discovery locks serialize reconfiguration with reconciliation. Action route validation reserves owned diagnostic/configuration topics on the corresponding broker endpoints, including saved retry destinations, preventing payload leakage into sensors. These checks recognize normalized host/port endpoints, not arbitrary DNS aliases or broker bridges. MQTT ACLs should isolate Studio-owned topics from other publishers.
