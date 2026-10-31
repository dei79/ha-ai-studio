import { useEffect, useRef } from "react";
import { Checkbox, Input, Select, Textarea } from "../design-system";
import { appUrl } from "../lib/api";
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
interface EditorModule {
  render: (
    host: HTMLElement,
    settings: Json,
    context: { changed: () => void },
  ) => (() => Json) | { read: () => Json; dispose: () => void };
}
// Trusted editor modules own this DOM island; React owns the surrounding form.
export function LegacyEditor({
  type,
  editor,
  settings,
  onReady,
  onError,
  onChange,
}: {
  type: string;
  editor?: string | null;
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
    let dispose: (() => void) | undefined;
    const element = host.current!;
    callbacks.current.onReady(null);
    const url = appUrl(
      editor || `action-types/${encodeURIComponent(type)}/editor.js`,
    ).href;
    import(/* @vite-ignore */ url)
      .then((module: EditorModule) => {
        if (!cancelled) {
          const result = module.render(element, structuredClone(settings), {
            changed: () => {
              if (!cancelled) callbacks.current.onChange();
            },
          });
          const read = typeof result === "function" ? result : result?.read;
          dispose = typeof result === "object" ? result.dispose : undefined;
          if (typeof read !== "function")
            throw new Error("Action editor must return a settings reader.");
          callbacks.current.onReady(read);
        }
      })
      .catch(() => {
        if (!cancelled)
          callbacks.current.onError(
            "Action editor failed to load. Check its module and render contract.",
          );
      });
    return () => {
      cancelled = true;
      try {
        dispose?.();
      } catch {
        callbacks.current.onError(
          "Action editor cleanup failed. Check its dispose contract.",
        );
      } finally {
        element.replaceChildren();
        callbacks.current.onReady(null);
      }
    };
  }, [type, editor, settings]);
  return <div ref={host} />;
}
