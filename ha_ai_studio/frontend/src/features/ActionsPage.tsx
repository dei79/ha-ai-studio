import { useEffect, useState } from "react";
import { Button, DataTable, IconButton, Notice } from "../design-system";
import { api, errorText } from "../lib/api";
import { useOperation, usePoll } from "../lib/hooks";
import type { ActionState, ActionType } from "../lib/types";
import { ConfirmDelete, CreateAction, EnvironmentPanel } from "./ActionPanels";
export function ActionsPage({
  open,
  live,
}: {
  open: (id: string) => void;
  live: (id: string) => void;
}) {
  const [items, setItems] = useState<ActionState[]>([]);
  const [types, setTypes] = useState<ActionType[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const [create, setCreate] = useState(false);
  const [remove, setRemove] = useState<ActionState>();
  const [environment, setEnvironment] = useState<ActionState>();
  const op = useOperation();
  async function refresh(signal?: AbortSignal) {
    const data = await api("actions", undefined, undefined, signal);
    if (!signal?.aborted) {
      setItems(data.actions);
      setTypes(data.types);
      setLoaded(true);
      setError("");
    }
  }
  useEffect(() => {
    const c = new AbortController();
    void refresh(c.signal).catch((error) => {
      if (!c.signal.aborted) setError(errorText(error));
    });
    return () => c.abort();
  }, []);
  usePoll(
    async (signal) => {
      try {
        await refresh(signal);
      } catch (error) {
        if (!signal.aborted) setError(errorText(error));
      }
    },
    !create && !remove && !environment && !op.busy,
  );
  return (
    <section>
      <div className="heading">
        <div>
          <h1>Actions</h1>
          <p>Configured actions for your Home Assistant automations.</p>
        </div>
        <Button
          variant="primary"
          disabled={!types.length || op.busy}
          onClick={() => setCreate(true)}
        >
          Create action
        </Button>
      </div>
      <Notice error>{error || op.error}</Notice>
      <DataTable
        label="Actions"
        columns={["Name", "Type", "Status", "Environment", "Actions"]}
      >
        {items.map((item) => (
          <tr key={item.definition.id}>
            <td>{item.definition.name}</td>
            <td>{item.plugin?.name || "Legacy workflow"}</td>
            <td>
              {!item.supported
                ? "Unsupported · Disabled"
                : item.busy
                  ? "Busy"
                  : item.enabled
                    ? "Active"
                    : "Inactive"}
            </td>
            <td>{item.environment.status}</td>
            <td className="row-actions">
              {item.plugin?.dynamic && (
                <IconButton
                  icon="installation"
                  label={`Installation details ${item.definition.name}`}
                  disabled={op.busy}
                  onClick={() =>
                    void op.run(async () =>
                      setEnvironment(
                        await api("action", undefined, item.definition.id),
                      ),
                    )
                  }
                />
              )}
              <IconButton
                icon="live"
                label={`Live activity ${item.definition.name}`}
                onClick={() => live(item.definition.id)}
              />
              <IconButton
                icon="edit"
                label={`Edit ${item.definition.name}`}
                onClick={() => open(item.definition.id)}
              />
              <IconButton
                icon="delete"
                label={`Delete ${item.definition.name}`}
                disabled={item.busy || op.busy}
                onClick={() => setRemove(item)}
              />
            </td>
          </tr>
        ))}
      </DataTable>
      {!loaded && !error && <p role="status">Loading actions…</p>}
      {loaded && !types.length && (
        <Notice>
          Add an action repository in Settings to make action types available.
        </Notice>
      )}
      {loaded && !!types.length && !items.length && (
        <p>Create your first action to get started.</p>
      )}
      {create && (
        <CreateAction
          types={types}
          close={() => setCreate(false)}
          created={open}
        />
      )}
      {environment && (
        <EnvironmentPanel
          initial={environment}
          close={() => setEnvironment(undefined)}
        />
      )}
      {remove && (
        <ConfirmDelete
          title="Delete action"
          description={`Delete “${remove.definition.name}”?`}
          note="The action will stop receiving MQTT requests and disappear from the list. Saved files and historical statistics will be kept."
          close={() => setRemove(undefined)}
          remove={async () => {
            await api("delete-action", {
              id: remove.definition.id,
              confirmed: true,
            });
            setRemove(undefined);
            await refresh();
          }}
        />
      )}
    </section>
  );
}
