import { useEffect, useRef, useState } from "react";
import { Button, LogView } from "../design-system";
import { api } from "../lib/api";
import type { LiveEvent } from "../lib/types";
export function LivePage({ id, back }: { id: string; back: () => void }) {
  const [paused, setPaused] = useState(false);
  const [status, setStatus] = useState("Connecting…");
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const cursor = useRef(0);
  const epoch = useRef<string | null>(null);
  useEffect(() => {
    if (paused) {
      setStatus("Display paused · Action continues running");
      return;
    }
    const abort = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const data = await api("live", undefined, id, abort.signal, {
          after: String(cursor.current),
        });
        if (abort.signal.aborted) return;
        if (epoch.current && epoch.current !== data.epoch) {
          cursor.current = 0;
          setEvents([]);
        } else {
          cursor.current = data.cursor;
          setEvents((previous) => [...previous, ...data.events].slice(-200));
        }
        epoch.current = data.epoch;
        setStatus(
          data.mqtt + " · Live" + (data.gap ? " · Older events expired" : ""),
        );
      } catch {
        if (!abort.signal.aborted)
          setStatus("Live activity unavailable. Retrying…");
      }
      if (!abort.signal.aborted) timer = setTimeout(poll, 1000);
    }
    void poll();
    return () => {
      abort.abort();
      clearTimeout(timer);
    };
  }, [id, paused]);
  return (
    <section>
      <Button variant="text" onClick={back}>
        ← Actions
      </Button>
      <div className="heading">
        <div>
          <h1>{id} · Live activity</h1>
          <p role="status">{status}</p>
        </div>
        <Button onClick={() => setPaused(!paused)}>
          {paused ? "Resume" : "Pause"}
        </Button>
      </div>
      <p className="small muted">
        Latest 200 events · memory only, cleared on app restart · message
        payloads shown here
      </p>
      <LogView label="Live action activity" live>
        {events
          .map(
            (e) =>
              `[${e.timestamp}] ${e.kind.toUpperCase()}  ${e.message}${e.topic ? "\n  Topic: " + e.topic : ""}${e.payload !== undefined ? "\n" + e.payload : ""}${e.truncated ? "\n[Payload truncated]" : ""}`,
          )
          .join("\n\n") || "Waiting for MQTT messages…"}
      </LogView>
    </section>
  );
}
