import type { ApiResponses } from "./types";
// document.baseURI keeps both API requests and compatibility imports inside HA Ingress.
export function appUrl(path: string): URL {
  return new URL(path, document.baseURI);
}
export async function api<K extends keyof ApiResponses>(
  endpoint: K,
  body?: unknown,
  id?: string,
  signal?: AbortSignal,
  query?: Record<string, string>,
): Promise<ApiResponses[K]> {
  const url = appUrl(`api/${endpoint}`);
  if (id) url.searchParams.set("id", id);
  for (const [key, value] of Object.entries(query ?? {}))
    url.searchParams.set(key, value);
  const response = await fetch(url, {
    method: body === undefined ? "GET" : "POST",
    signal,
    headers:
      body === undefined
        ? {}
        : { "Content-Type": "application/json", "X-HA-AI-Studio-Request": "1" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      typeof data.error === "string" ? data.error : "Request failed.",
    );
  return data as ApiResponses[K];
}
export function errorText(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed.";
}
