import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { JSX } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EventName } from "@/api/event-names";
import * as events from "@/api/events";
import * as session from "@/api/session";
import { AppHeader } from "@/components/app-header";
import { makeSession } from "../api/fixtures";

function SupportPlaceholder(): JSX.Element {
  return <p>support screen</p>;
}

function renderHeader(currentSession: session.CurrentSession | null) {
  return render(
    <MemoryRouter initialEntries={["/app"]}>
      <Routes>
        <Route path="/app" element={<AppHeader session={currentSession} />} />
        <Route path="/app/support" element={<SupportPlaceholder />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("AppHeader", () => {
  beforeEach(() => {
    vi.spyOn(events, "trackEvent").mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("shows the customer's number", () => {
    renderHeader(makeSession());

    expect(screen.getByText("12345")).toBeInTheDocument();
  });

  it("shows placeholders instead of values while the session loads", () => {
    renderHeader(null);

    expect(screen.queryByText("12345")).not.toBeInTheDocument();
    expect(screen.getAllByText("—")).toHaveLength(2);
  });

  it("counts down the idle time left, once per second", async () => {
    vi.useFakeTimers();
    renderHeader(
      makeSession({
        idle_expires_at: new Date(Date.now() + 90_000).toISOString(),
      }),
    );
    expect(screen.getByText("1:30")).toBeInTheDocument();

    await act(() => vi.advanceTimersByTimeAsync(31_000));

    expect(screen.getByText("0:59")).toBeInTheDocument();
  });

  it("navigates to /app/support when Soporte is clicked", async () => {
    const user = userEvent.setup();
    renderHeader(makeSession());

    await user.click(screen.getByRole("button", { name: "Soporte" }));

    expect(await screen.findByText("support screen")).toBeInTheDocument();
    expect(events.trackEvent).toHaveBeenCalledWith(EventName.SupportClicked);
  });

  it("logs out as a user-requested logout when Cerrar sesión is clicked", async () => {
    const logoutSpy = vi.spyOn(session, "logout").mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderHeader(makeSession());

    await user.click(screen.getByRole("button", { name: "Cerrar sesión" }));

    expect(logoutSpy).toHaveBeenCalledOnce();
    expect(logoutSpy).toHaveBeenCalledWith();
  });
});
