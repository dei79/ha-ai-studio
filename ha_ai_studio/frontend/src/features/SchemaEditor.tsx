import { useEffect, useRef } from "react";
import { Checkbox, Input, Select, Textarea } from "../design-system";
import { appUrl, errorText } from "../lib/api";
import type { Json, Schema } from "../lib/types";
export function simpleSchema(schema: Schema): boolean {
  return (
    schema.type === "object" &&
    schema.additionalProperties === false &&
    !schema.patternProperties &&
    Object.values(schema.properties ?? {}).every((p) =>
      ["string", "number", "integer", "boolean"].includes(p.type ?? ""),
    )
  );
}
export function readSettings(
  schema: Schema,
  initial: Json,
  values: Record<string, string | boolean>,
  raw: string,
): Json {
  if (!simpleSchema(schema)) {
    try {
      return JSON.parse(raw) as Json;
    } catch {
      throw new Error("Provide valid settings JSON.");
    }
  }
  const result: Record<string, Json> =
    initial && typeof initial === "object" && !Array.isArray(initial)
      ? { ...initial }
      : {};
  for (const [key, property] of Object.entries(schema.properties ?? {})) {
    if (!(key in values)) {
      if (
        schema.required?.includes(key) &&
        ["number", "integer"].includes(property.type ?? "") &&
        !(key in result)
      )
        throw new Error(`${property.title ?? key} is required.`);
      continue;
    }
    const value = values[key];
    if (property.enum) {
      if (value === "") delete result[key];
      else result[key] = property.enum[Number(value)];
    } else if (property.type === "number" || property.type === "integer") {
      if (value === "") {
        if (schema.required?.includes(key))
          throw new Error(`${property.title ?? key} is required.`);
        delete result[key];
      } else {
        const number = Number(value);
        if (
          !Number.isFinite(number) ||
          (property.type === "integer" && !Number.isInteger(number))
        )
          throw new Error(
            `${property.title ?? key} must be a valid ${property.type}.`,
          );
        result[key] = number;
      }
    } else result[key] = value;
  }
  return result;
}
export function SchemaEditor({
  schema,
  initial,
  values,
  raw,
  onValues,
  onRaw,
}: {
  schema: Schema;
  initial: Json;
  values: Record<string, string | boolean>;
  raw: string;
  onValues: (values: Record<string, string | boolean>) => void;
  onRaw: (raw: string) => void;
}) {
  const settings =
    initial && typeof initial === "object" && !Array.isArray(initial)
      ? initial
      : {};
  return (
    <>
      <p>
        Settings are validated against the action schema. Git action preview is
        unavailable; use an isolated MQTT test instance.
      </p>
      {!simpleSchema(schema) ? (
        <Textarea
          label="Settings JSON"
          rows={12}
          value={raw}
          onChange={(e) => onRaw(e.target.value)}
        />
      ) : (
        Object.entries(schema.properties ?? {}).map(([key, p]) => {
          const label = p.title ?? key;
          const change = (value: string | boolean) =>
            onValues({ ...values, [key]: value });
          if (p.enum)
            return (
              <Select
                key={key}
                label={label}
                value={String(
                  values[key] ??
                    (key in settings ? p.enum.indexOf(settings[key]) : ""),
                )}
                onChange={(e) => change(e.target.value)}
              >
                <option value="">Select a value</option>
                {p.enum.map((v, i) => (
                  <option key={i} value={i}>
                    {String(v)}
                  </option>
                ))}
              </Select>
            );
          if (p.type === "boolean")
            return (
              <Checkbox
                key={key}
                label={label}
                checked={Boolean(values[key] ?? settings[key] ?? false)}
                onChange={(e) => change(e.target.checked)}
              />
            );
          return (
            <Input
              key={key}
              label={label}
              hint={p.description}
              type={
                ["number", "integer"].includes(p.type ?? "") ? "number" : "text"
              }
              step={p.type === "integer" ? 1 : "any"}
              value={String(values[key] ?? settings[key] ?? "")}
              onChange={(e) =>
                change(e.target.validity.badInput ? "NaN" : e.target.value)
              }
            />
          );
        })
      )}
    </>
  );
}
interface LegacyModule {
  render: (
    host: HTMLElement,
    settings: Json,
    context: { changed: () => void },
  ) => () => Json;
}
// Only the backend's allowlisted compatibility editor can use an imperative DOM island.
// Git repositories never supply browser code.
export function LegacyEditor({
  type,
  settings,
  onReady,
  onError,
  onChange,
}: {
  type: string;
  settings: Json;
  onReady: (read: (() => Json) | null) => void;
  onError: (message: string) => void;
  onChange: () => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const callbacks = useRef({ onReady, onError, onChange });
  callbacks.current = { onReady, onError, onChange };
  useEffect(() => {
    let cancelled = false;
    const element = host.current!;
    callbacks.current.onReady(null);
    const url = appUrl(
      `action-types/${encodeURIComponent(type)}/editor.js`,
    ).href;
    import(/* @vite-ignore */ url)
      .then((module: LegacyModule) => {
        if (!cancelled)
          callbacks.current.onReady(
            module.render(element, structuredClone(settings), {
              changed: () => callbacks.current.onChange(),
            }),
          );
      })
      .catch((error) => {
        if (!cancelled) callbacks.current.onError(errorText(error));
      });
    return () => {
      cancelled = true;
      element.replaceChildren();
    };
  }, [type, settings]);
  return <div ref={host} />;
}
