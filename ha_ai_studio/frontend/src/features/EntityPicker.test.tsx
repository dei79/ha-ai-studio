import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { EntityPicker } from "./EntityPicker";
afterEach(() => vi.unstubAllGlobals());
it("search is read-only, filters types, preserves IDs and does not submit the parent form", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      total: 2,
      entities: [
        {
          entity_id: "camera.meter",
          name: "Meter",
          state: "idle",
          available: true,
        },
        {
          entity_id: "camera.offline",
          name: "Offline",
          state: "unavailable",
          available: false,
        },
      ],
    }),
  });
  vi.stubGlobal("fetch", fetchMock);
  const submit = vi.fn((e) => e.preventDefault()),
    selected = vi.fn();
  render(
    <form onSubmit={submit}>
      <button type="submit">Save</button>
      <EntityPicker
        options={{ domains: ["camera"] }}
        onSelect={selected}
        onClose={() => {}}
      />
    </form>,
  );
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Search entities"), "meter{Enter}");
  await screen.findByRole("button", {
    name: /Select Meter \(camera.meter\), idle/,
  });
  expect(submit).not.toHaveBeenCalled();
  expect(
    screen.getByRole("button", {
      name: /Select Offline \(camera.offline\), Unavailable/,
    }),
  ).toBeDisabled();
  await user.click(
    screen.getByRole("button", { name: /Select Meter \(camera.meter\), idle/ }),
  );
  expect(selected).toHaveBeenCalledWith(
    expect.objectContaining({ entity_id: "camera.meter" }),
  );
  expect(
    fetchMock.mock.calls.every((call) => call[1].method === undefined),
  ).toBe(true);
  await waitFor(() =>
    expect(String(fetchMock.mock.lastCall?.[0])).toContain("domains=camera"),
  );
});
it("shows a connection error without offering stale entities", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue({
        ok: false,
        json: async () => ({ error: "Home Assistant denied access." }),
      }),
  );
  render(
    <EntityPicker
      options={{ domains: ["camera"] }}
      onSelect={() => {}}
      onClose={() => {}}
    />,
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Home Assistant denied access.",
  );
  expect(screen.getByRole("button", { name: "Retry" })).toBeEnabled();
});
