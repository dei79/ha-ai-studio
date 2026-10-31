import { useRef, useState } from "react";
import {
  Button,
  Input,
  JsonBlock,
  LogView,
  Notice,
  Select,
  SidePanel,
  Status,
  Textarea,
} from "../design-system";
import { api, errorText } from "../lib/api";
import { useOperation, usePoll } from "../lib/hooks";
import { mqttTestAutomationYaml } from "../lib/ha-example";
import type {
  ActionState,
  ActionType,
  Brokers,
  Configuration,
} from "../lib/types";
export function CreateAction({
  types,
  close,
  created,
}: {
  types: ActionType[];
  close: () => void;
  created: (id: string) => void;
}) {
  const [name, setName] = useState("");
  const [type, setType] = useState(types[0]?.type ?? "");
  const op = useOperation();
  return (
    <SidePanel
      title="Create action"
      onClose={close}
      busy={op.busy}
      footer={
        <Button
          type="submit"
          form="create-action"
          variant="primary"
          disabled={op.busy || !type}
        >
          Create action
        </Button>
      }
    >
      <form
        id="create-action"
        onSubmit={(e) => {
          e.preventDefault();
          void op.run(async () => {
            const trimmed = name.trim();
            if (!trimmed) throw new Error("Provide an action name.");
            const slug = trimmed
              .toLowerCase()
              .replace(/[^a-z0-9]+/g, "-")
              .replace(/^-|-$/g, "")
              .slice(0, 36);
            const id =
              (/^[a-z]/.test(slug) ? slug : "action") +
              "-" +
              crypto.randomUUID().slice(0, 8);
            await api("actions", { id, name: trimmed, type });
            created(id);
          });
        }}
      >
        <fieldset disabled={op.busy}>
          <Input
            label="Name"
            required
            maxLength={80}
            autoComplete="off"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <Select
            label="Action type"
            value={type}
            onChange={(e) => setType(e.target.value)}
          >
            {types.map((t) => (
              <option key={t.type} value={t.type}>
                {t.name}
                {t.dynamic ? ` · ${t.version} · ${t.commit?.slice(0, 8)}` : ""}
              </option>
            ))}
          </Select>
        </fieldset>
        <Notice error>{op.error}</Notice>
      </form>
    </SidePanel>
  );
}
export function ConfirmDelete({
  title,
  description,
  note,
  close,
  remove,
}: {
  title: string;
  description: string;
  note: string;
  close: () => void;
  remove: () => Promise<void>;
}) {
  const op = useOperation();
  return (
    <SidePanel
      title={title}
      onClose={close}
      busy={op.busy}
      footer={
        <>
          <Button onClick={close} disabled={op.busy}>
            Cancel
          </Button>
          <Button
            variant="danger"
            disabled={op.busy}
            onClick={() => void op.run(remove)}
          >
            {title}
          </Button>
        </>
      }
    >
      <p>{description}</p>
      <p>{note}</p>
      <Notice error>{op.error}</Notice>
    </SidePanel>
  );
}
export function EnvironmentPanel({
  initial,
  close,
}: {
  initial: ActionState;
  close: () => void;
}) {
  const [state, setState] = useState(initial);
  const [pollError, setPollError] = useState("");
  const op = useOperation();
  const generation = useRef(0);
  usePoll(async (signal) => {
    const version = generation.current;
    try {
      const value = await api(
        "action",
        undefined,
        initial.definition.id,
        signal,
      );
      if (!signal.aborted && version === generation.current) {
        setState(value);
        setPollError("");
      }
    } catch (error) {
      if (!signal.aborted && version === generation.current)
        setPollError(errorText(error));
    }
  }, !op.busy);
  const installing = ["Queued", "Installing", "Verifying"].includes(
    state.environment.status,
  );
  const help = state.enabled
    ? "Deactivate the action before rebuilding its environment."
    : installing
      ? "Environment installation is running."
      : state.busy
        ? "Wait for the current operation to finish before rebuilding."
        : "";
  const refresh = (rebuild: boolean) => {
    generation.current++;
    void op.run(async () => {
      setPollError("");
      setState(
        await api(
          rebuild ? "environment" : "action",
          rebuild ? {} : undefined,
          state.definition.id,
        ),
      );
    });
  };
  return (
    <SidePanel
      title="Installation details"
      onClose={close}
      busy={op.busy}
      logs
      footer={
        <>
          <p className="small muted">{help}</p>
          <Button
            className="footer-secondary"
            disabled={op.busy}
            onClick={() => refresh(false)}
          >
            Refresh status
          </Button>
          <Button
            variant="primary"
            disabled={op.busy || state.enabled || state.busy || installing}
            onClick={() => refresh(true)}
          >
            Rebuild environment
          </Button>
        </>
      }
    >
      <Status
        name={state.definition.name}
        status={state.environment.status}
        detail={`Version ${state.plugin?.version} · Commit ${state.plugin?.commit}`}
        tone={
          state.environment.status === "Ready"
            ? "success"
            : state.environment.status === "Failed"
              ? "error"
              : "pending"
        }
      />
      <Notice error>{op.error || pollError}</Notice>
      <LogView label="Environment installation log">
        {state.environment.logs.join("\n")}
      </LogView>
    </SidePanel>
  );
}
export function SchemasPanel({
  type,
  close,
}: {
  type: ActionType;
  close: () => void;
}) {
  return (
    <SidePanel
      title="Message schemas"
      onClose={close}
      footer={<Button onClick={close}>Done</Button>}
    >
      <h3>Input schema</h3>
      <JsonBlock value={type.input_schema} label="Input schema JSON" />
      <h3>Success output schema</h3>
      <JsonBlock
        value={type.output_schema}
        label="Success output schema JSON"
      />
    </SidePanel>
  );
}
export function ExamplePanel({
  config,
  state,
  brokers,
  close,
}: {
  config: Configuration;
  state: ActionState;
  brokers: Brokers;
  close: () => void;
}) {
  const yaml = mqttTestAutomationYaml(config, state.plugin?.example);
  const [status, setStatus] = useState("");
  const text = useRef<HTMLTextAreaElement>(null);
  const broker = brokers.brokers.find((b) => b.id === config.input.broker_id);
  return (
    <SidePanel
      title="Test in Home Assistant"
      onClose={close}
      footer={
        <Button
          variant="primary"
          disabled={!config.input.topic || !config.output.topic}
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(yaml);
              setStatus("YAML copied.");
            } catch {
              text.current?.focus();
              text.current?.select();
              setStatus(
                "Clipboard access is unavailable. Copy the selected YAML manually.",
              );
            }
          }}
        >
          Copy YAML
        </Button>
      }
    >
      <Notice>
        {state.enabled
          ? "Uses the active configuration. Unsaved edits and draft changes are not included."
          : "Draft example. Save and activate this action before running the test."}
      </Notice>
      <ol className="test-guide">
        <li>
          <strong>Create an automation</strong>
          <span>
            Home Assistant → Settings → Automations &amp; scenes → Create
            automation.
          </span>
        </li>
        <li>
          <strong>Paste the YAML</strong>
          <span>
            Open ⋮ → Edit in YAML and replace the content with the example
            below.
          </span>
        </li>
        <li>
          <strong>Save and enable</strong>
          <span>Keep the automation enabled so it can receive replies.</span>
        </li>
        <li>
          <strong>Run and view the result</strong>
          <span>
            Select ⋮ → Run actions, then open the notification bell in Home
            Assistant.
          </span>
        </li>
      </ol>
      <details className="test-notes">
        <summary>How this test works</summary>
        <p>
          Each manual run sends a real MQTT request with a new request ID. Every
          response on this Result topic appears as a notification. No timeout
          notification is included.
        </p>
        <p>
          Home Assistant must connect to the Input broker
          {broker
            ? ` “${broker.name}”.`
            : ". Select an Input broker before activating."}{" "}
          mqtt.publish uses Home Assistant’s configured broker.
          {config.output.broker_id &&
          config.output.broker_id !== config.input.broker_id
            ? " Output uses a different broker. HA can only receive the result if that topic is bridged to its MQTT broker."
            : ""}
        </p>
      </details>
      <label className="field">
        Automation YAML
        <textarea
          ref={text}
          className="yaml-editor"
          rows={22}
          wrap="off"
          readOnly
          spellCheck={false}
          value={yaml}
        />
      </label>
      <p role="status" className="small muted">
        {status}
      </p>
    </SidePanel>
  );
}
export function DraftTest({
  config,
  id,
  close,
}: {
  config: Configuration;
  id: string;
  close: () => void;
}) {
  const [payload, setPayload] = useState(
    '{"request_id":"draft-test","data":null}',
  );
  const [result, setResult] = useState<unknown>();
  const op = useOperation();
  return (
    <SidePanel
      title="Test draft"
      onClose={close}
      busy={op.busy}
      footer={
        <Button
          form="draft-test"
          type="submit"
          variant="primary"
          disabled={op.busy}
        >
          Run draft test
        </Button>
      }
    >
      <p>
        Runs this compatibility action in memory. No MQTT messages are published
        and no job is saved.
      </p>
      <form
        id="draft-test"
        onSubmit={(e) => {
          e.preventDefault();
          void op.run(async () =>
            setResult(await api("test", { config, payload }, id)),
          );
        }}
      >
        <Textarea
          label="Request JSON"
          rows={8}
          value={payload}
          disabled={op.busy}
          onChange={(e) => setPayload(e.target.value)}
        />
        <Notice error>{op.error}</Notice>
      </form>
      {result !== undefined && (
        <JsonBlock label="Draft test result" value={result} />
      )}
    </SidePanel>
  );
}
