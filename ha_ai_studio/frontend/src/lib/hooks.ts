import { useEffect, useRef, useState } from "react";
import { errorText } from "./api";
export function useOperation() {
  const locked = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function run(work: () => Promise<void>) {
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    setError("");
    try {
      await work();
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }
  return { busy, error, run, setError };
}
// Recursive timeouts avoid overlapping requests; cleanup aborts work when a view closes.
export function usePoll(
  work: (signal: AbortSignal) => Promise<void>,
  enabled = true,
  delay = 2000,
) {
  const latest = useRef(work);
  latest.current = work;
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function tick() {
      try {
        await latest.current(controller.signal);
      } catch {
        /* Views surface recoverable read failures. */
      }
      if (!controller.signal.aborted) timer = setTimeout(tick, delay);
    }
    timer = setTimeout(tick, delay);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [enabled, delay]);
}
