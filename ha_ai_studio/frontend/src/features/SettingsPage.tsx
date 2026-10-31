import { Fragment, useEffect, useState } from "react";
import {
  Button,
  Card,
  DataTable,
  IconButton,
  Input,
  Notice,
  SidePanel,
  Select,
} from "../design-system";
import { api, errorText } from "../lib/api";
import { useOperation, usePoll } from "../lib/hooks";
import type { Broker, Brokers, Discovery, Repository } from "../lib/types";
import { ConfirmDelete } from "./ActionPanels";
import { BrokerPanel, BrokerTestPanel } from "./BrokerPanels";
function RepositoryPanel({
  close,
  saved,
  localAvailable,
}: {
  close: () => void;
  saved: () => Promise<void>;
  localAvailable: boolean;
}) {
  const [kind, setKind] = useState("git");
  const [path, setPath] = useState(".");
  const [url, setUrl] = useState("");
  const [ref, setRef] = useState("main");
  const op = useOperation();
  return (
    <SidePanel
      title="Add action repository"
      onClose={close}
      busy={op.busy}
      footer={
        <Button
          form="repository-form"
          type="submit"
          variant="primary"
          disabled={op.busy}
        >
          Add repository
        </Button>
      }
    >
      <form
        id="repository-form"
        onSubmit={(e) => {
          e.preventDefault();
          void op.run(async () => {
            await api(
              "repositories",
              kind === "local"
                ? { kind, path }
                : kind === "release"
                  ? { kind, url, ref }
                  : { url, ref },
            );
            await saved();
            close();
          });
        }}
      >
        <fieldset disabled={op.busy}>
          <Select
            label="Source type"
            value={kind}
            onChange={(e) => {
              setKind(e.target.value);
              setRef(e.target.value === "release" ? "latest" : "main");
            }}
          >
            <option value="git">Git repository</option>
            <option value="release">GitHub Release</option>
            {localAvailable && <option value="local">Local directory</option>}
          </Select>
          {kind === "local" ? (
            <Input
              label="Local directory"
              required
              value={path}
              hint="Relative to the server's mounted actions root. Use . for the root itself."
              onChange={(e) => setPath(e.target.value)}
            />
          ) : (
            <>
              <Input
                label={
                  kind === "release" ? "GitHub repository URL" : "Git HTTPS URL"
                }
                type="url"
                required
                placeholder="https://github.com/owner/actions.git"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
              <Input
                label={
                  kind === "release"
                    ? "Release tag or latest"
                    : "Branch, tag or commit"
                }
                hint={
                  kind === "release"
                    ? "latest downloads the latest stable release on refresh. Existing actions keep their installed version."
                    : undefined
                }
                required
                maxLength={128}
                value={ref}
                onChange={(e) => setRef(e.target.value)}
              />
            </>
          )}
          <p>
            Each action needs an action.json manifest, a Python entrypoint and a
            hashed requirements.lock. No code runs during catalog refresh.
            Creating an action installs and checks trusted code.
          </p>
        </fieldset>
        <Notice error>{op.error}</Notice>
      </form>
    </SidePanel>
  );
}
type Panel =
  | { kind: "broker"; broker: Broker | null }
  | { kind: "test" | "delete-broker"; broker: Broker }
  | { kind: "repository" }
  | { kind: "delete-repository"; repo: Repository };
export function SettingsPage() {
  const [brokers, setBrokers] = useState<Brokers>();
  const [discovery, setDiscovery] = useState<Discovery>();
  const [localAvailable, setLocalAvailable] = useState(false);
  const [repos, setRepos] = useState<Repository[]>([]);
  const [panel, setPanel] = useState<Panel>();
  const [loadError, setLoadError] = useState("");
  const [message, setMessage] = useState("");
  const op = useOperation();
  async function refresh(signal?: AbortSignal) {
    const [b, d, r] = await Promise.all([
      api("brokers", undefined, undefined, signal),
      api("discovery", undefined, undefined, signal),
      api("repositories", undefined, undefined, signal),
    ]);
    if (!signal?.aborted) {
      setBrokers(b);
      setDiscovery(d);
      setRepos(r.repositories);
      setLocalAvailable(!!r.local_available);
      setLoadError("");
    }
  }
  useEffect(() => {
    const c = new AbortController();
    void refresh(c.signal).catch((error) => {
      if (!c.signal.aborted) setLoadError(errorText(error));
    });
    return () => c.abort();
  }, []);
  usePoll(async (signal) => {
    try {
      await refresh(signal);
    } catch (error) {
      if (!signal.aborted) setLoadError(errorText(error));
    }
  }, !panel && !op.busy);
  const close = () => setPanel(undefined);
  return (
    <section>
      <div className="heading">
        <h1>Settings</h1>
      </div>
      <Notice error>{loadError || op.error}</Notice>
      <Notice>{message}</Notice>
      <Card
        title="MQTT brokers"
        actions={
          <>
            <Button
              disabled={op.busy}
              onClick={() =>
                void op.run(async () => {
                  const value = await api("broker-refresh", {});
                  await refresh();
                  setMessage(
                    value.default_id
                      ? "Home Assistant MQTT broker found."
                      : "No Home Assistant MQTT service found. You can add a broker manually.",
                  );
                })
              }
            >
              Find HA broker
            </Button>
            <Button
              variant="primary"
              disabled={!brokers || !discovery || op.busy}
              onClick={() => setPanel({ kind: "broker", broker: null })}
            >
              Add broker
            </Button>
          </>
        }
      >
        <p>
          Home Assistant's broker appears automatically when its MQTT service is
          available. Select a broker in each action's Input and Output.
        </p>
        <DataTable
          label="MQTT brokers"
          columns={[
            "Broker",
            "Connection",
            "Source",
            "HA discovery",
            "Actions",
          ]}
        >
          {brokers?.brokers.map((b) => (
            <tr key={b.id}>
              <td>{b.name}</td>
              <td>
                {b.host}:{b.port}
                {b.tls ? " · TLS" : ""}
              </td>
              <td>
                {b.source === "supervisor"
                  ? "Home Assistant · default"
                  : b.source === "environment"
                    ? ".env"
                    : "Manual"}
              </td>
              <td>
                {discovery?.config.broker_id === b.id &&
                discovery.config.enabled
                  ? "Enabled"
                  : "Disabled"}
              </td>
              <td className="row-actions">
                <IconButton
                  icon="test"
                  label={`Test ${b.name}`}
                  disabled={op.busy}
                  onClick={() => setPanel({ kind: "test", broker: b })}
                />
                <IconButton
                  icon="edit"
                  label={`Edit broker ${b.name}`}
                  disabled={op.busy}
                  onClick={() => setPanel({ kind: "broker", broker: b })}
                />
                {b.editable && (
                  <IconButton
                    icon="delete"
                    label={`Delete broker ${b.name}`}
                    disabled={op.busy}
                    onClick={() =>
                      setPanel({ kind: "delete-broker", broker: b })
                    }
                  />
                )}
              </td>
            </tr>
          ))}
        </DataTable>
        {brokers && !brokers.brokers.length && (
          <p>No brokers configured. Add a broker to activate an action.</p>
        )}
      </Card>
      <Card
        title="Action repositories"
        actions={
          <Button
            variant="primary"
            disabled={op.busy}
            onClick={() => setPanel({ kind: "repository" })}
          >
            Add repository
          </Button>
        }
      >
        <p>
          Install only repositories you trust. Python environments isolate
          dependencies; repository code can access files and the network. Public
          HTTPS repositories are supported.{" "}
          {localAvailable &&
            "Local directories are also available on this server. "}
          Custom editors run trusted JavaScript in Studio; install only code you
          trust.
        </p>
        <DataTable
          label="Action repositories"
          columns={[
            "Repository",
            "Source",
            "Ref",
            "Status",
            "Types",
            "Actions",
          ]}
        >
          {repos.map((repo) => (
            <Fragment key={repo.id}>
              <tr>
                <td>{repo.url}</td>
                <td>
                  {repo.kind === "local"
                    ? "Local"
                    : repo.kind === "release"
                      ? "GitHub Release"
                      : repo.system
                        ? "System"
                        : "User"}
                </td>
                <td>
                  {repo.ref}
                  {repo.release ? ` · ${repo.release.tag}` : ""}
                </td>
                <td>{repo.status}</td>
                <td>
                  {repo.actions
                    .map((a) => a.manifest.name + " " + a.manifest.version)
                    .join(", ") || "—"}
                </td>
                <td className="row-actions">
                  <IconButton
                    icon="refresh"
                    label={`Refresh repository ${repo.url}`}
                    disabled={repo.refreshing || op.busy}
                    onClick={() =>
                      void op.run(async () => {
                        await api("repository-refresh", { id: repo.id });
                        await refresh();
                      })
                    }
                  />
                  <IconButton
                    icon="delete"
                    label={`Delete repository ${repo.url}`}
                    title={repo.delete_reason || "Delete repository"}
                    disabled={!repo.can_delete || op.busy}
                    onClick={() =>
                      setPanel({ kind: "delete-repository", repo })
                    }
                  />
                </td>
              </tr>
              {repo.status === "Failed" && (
                <tr>
                  <td colSpan={6}>{repo.logs.join(" ")}</td>
                </tr>
              )}
            </Fragment>
          ))}
        </DataTable>
      </Card>
      {panel?.kind === "broker" && brokers && discovery && (
        <BrokerPanel
          broker={panel.broker}
          brokers={brokers}
          discovery={discovery}
          close={close}
          saved={() => refresh()}
        />
      )}
      {panel?.kind === "test" && (
        <BrokerTestPanel broker={panel.broker} close={close} />
      )}
      {panel?.kind === "delete-broker" && (
        <ConfirmDelete
          title="Delete broker"
          description={`Delete “${panel.broker.name}”?`}
          note="Brokers referenced by action drafts, active configurations or saved requests cannot be deleted."
          close={close}
          remove={async () => {
            await api("broker-delete", {
              id: panel.broker.id,
              confirmed: true,
            });
            close();
            await refresh();
          }}
        />
      )}
      {panel?.kind === "repository" && (
        <RepositoryPanel
          localAvailable={localAvailable}
          close={close}
          saved={() => refresh()}
        />
      )}
      {panel?.kind === "delete-repository" && (
        <ConfirmDelete
          title="Delete repository"
          description={`Delete “${panel.repo.url}” (${panel.repo.ref})?`}
          note="The repository and its action types will be removed from this app. The remote Git repository is unchanged. Existing action history is preserved."
          close={close}
          remove={async () => {
            await api("repository-delete", {
              id: panel.repo.id,
              confirmed: true,
            });
            close();
            await refresh();
          }}
        />
      )}
    </section>
  );
}
