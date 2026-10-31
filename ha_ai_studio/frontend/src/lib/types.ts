export type Json =
  null | boolean | number | string | Json[] | { [key: string]: Json };
export interface Schema {
  type?: string;
  title?: string;
  description?: string;
  enum?: Json[];
  properties?: Record<string, Schema>;
  required?: string[];
  additionalProperties?: boolean | Schema;
  patternProperties?: Record<string, Schema>;
}
export interface Route {
  broker_id: string | null;
  topic: string;
}
export interface Configuration {
  name: string;
  input: Route;
  output: Route;
  settings: Json;
}
export interface ActionType {
  type: string;
  name: string;
  dynamic?: boolean;
  local?: boolean;
  editor?: string | null;
  version?: string;
  commit?: string;
  example?: { request_id?: string; data: Json } | null;
  input_schema: Schema;
  output_schema: Schema;
  settings_schema: Schema;
}
export interface ActionState {
  definition: { id: string; name: string; type: string };
  supported: boolean;
  enabled: boolean;
  busy: boolean;
  config: { draft: Configuration; active: Configuration | null } | null;
  plugin: ActionType | null;
  environment: { status: string; logs: string[] };
  issues: string[];
  mqtt: string;
}
export interface Broker {
  id: string;
  name: string;
  host: string;
  port: number;
  tls: boolean;
  source: string;
  editable: boolean;
  secrets: { username: boolean; password: boolean };
}
export interface Brokers {
  brokers: Broker[];
  default_id: string | null;
}
export interface Discovery {
  config: {
    enabled: boolean;
    broker_id: string | null;
    prefix: string;
    ha_status_topic: string;
  };
  status: string;
  pending_cleanup: number;
  legacy_pending: boolean;
}
export interface Repository {
  kind?: "git" | "local";
  id: string;
  url: string;
  ref: string;
  status: string;
  system: boolean;
  refreshing: boolean;
  can_delete: boolean;
  delete_reason: string | null;
  logs: string[];
  actions: { manifest: { name: string; version: string } }[];
}
export interface BrokerProbe {
  ok: boolean;
  message: string;
  scope: string;
  logs: { elapsed_ms: number; message: string }[];
}
export interface LiveEvent {
  timestamp: string;
  kind: string;
  message: string;
  topic?: string;
  payload?: string;
  truncated?: boolean;
}
export interface LiveData {
  epoch: string;
  cursor: number;
  mqtt: string;
  gap: boolean;
  events: LiveEvent[];
}
export interface ApiResponses {
  actions: { actions: ActionState[]; types: ActionType[] };
  action: ActionState;
  deactivate: ActionState;
  environment: ActionState;
  "reload-source": ActionState;
  brokers: Brokers;
  "broker-refresh": Brokers;
  "broker-delete": Brokers;
  "broker-test": BrokerProbe;
  discovery: Discovery;
  repositories: { repositories: Repository[]; local_available?: boolean };
  "repository-refresh": { repositories: Repository[] };
  "repository-delete": { repositories: Repository[] };
  "delete-action": unknown;
  test: { mode: string; delivery: string; result: Json };
  live: LiveData;
}
