import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EventName } from "@/api/event-names";
import * as events from "@/api/events";
import * as sessionApi from "@/api/session";
import { SessionManager } from "@/components/session-manager";
import { makeSession } from "../api/fixtures";

const FIVE_MINUTES_MS = 5 * 60 * 1000;
const THIRTY_MINUTES_MS = 30 * 60 * 1000;

describe("SessionManager", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(sessionApi, "logout").mockResolvedValue(undefined);
    vi.spyOn(events, "trackEvent").mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("shows nothing while well within both timeouts", () => {
    const session = makeSession({
      idle_expires_at: new Date(Date.now() + FIVE_MINUTES_MS).toISOString(),
      absolute_expires_at: new Date(
        Date.now() + THIRTY_MINUTES_MS,
      ).toISOString(),
    });

    render(<SessionManager session={session} onSessionRefreshed={vi.fn()} />);

    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("shows the idle warning at 4:30 and closes the session at 5:00", async () => {
    const session = makeSession({
      idle_expires_at: new Date(Date.now() + FIVE_MINUTES_MS).toISOString(),
      absolute_expires_at: new Date(
        Date.now() + THIRTY_MINUTES_MS,
      ).toISOString(),
    });
    render(<SessionManager session={session} onSessionRefreshed={vi.fn()} />);

    await vi.advanceTimersByTimeAsync(4 * 60 * 1000 + 30 * 1000); // 4:30
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Seguir conectado" }),
    ).toBeInTheDocument();
    expect(events.trackEvent).toHaveBeenCalledWith(
      EventName.SessionIdleWarningShown,
    );

    await vi.advanceTimersByTimeAsync(30 * 1000); // -> 5:00
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Sesión cerrada por inactividad.",
    );
    expect(sessionApi.logout).toHaveBeenCalledOnce();
    expect(events.trackEvent).toHaveBeenCalledWith(
      EventName.SessionExpiredIdle,
    );
  });

  it("shows the absolute warning at 29:30 (no Seguir conectado) and cuts at 30:00", async () => {
    const session = makeSession({
      // Idle timeout kept far away so only the absolute deadline applies.
      idle_expires_at: new Date(
        Date.now() + THIRTY_MINUTES_MS + FIVE_MINUTES_MS,
      ).toISOString(),
      absolute_expires_at: new Date(
        Date.now() + THIRTY_MINUTES_MS,
      ).toISOString(),
    });
    render(<SessionManager session={session} onSessionRefreshed={vi.fn()} />);

    await vi.advanceTimersByTimeAsync(29 * 60 * 1000 + 30 * 1000); // 29:30
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Seguir conectado" }),
    ).not.toBeInTheDocument();
    expect(events.trackEvent).toHaveBeenCalledWith(
      EventName.SessionAbsoluteWarningShown,
    );

    await vi.advanceTimersByTimeAsync(30 * 1000); // -> 30:00
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Sesión cerrada por tiempo máximo alcanzado.",
    );
    expect(sessionApi.logout).toHaveBeenCalledOnce();
    expect(events.trackEvent).toHaveBeenCalledWith(
      EventName.SessionExpiredAbsolute,
    );
  });

  it('"Seguir conectado" reports activity and clears the idle warning', async () => {
    const session = makeSession({
      idle_expires_at: new Date(Date.now() + FIVE_MINUTES_MS).toISOString(),
      absolute_expires_at: new Date(
        Date.now() + THIRTY_MINUTES_MS,
      ).toISOString(),
    });
    const refreshedSession = makeSession();
    vi.spyOn(sessionApi, "reportActivity").mockResolvedValue(refreshedSession);
    const onSessionRefreshed = vi.fn();
    render(
      <SessionManager
        session={session}
        onSessionRefreshed={onSessionRefreshed}
      />,
    );
    await vi.advanceTimersByTimeAsync(4 * 60 * 1000 + 30 * 1000); // 4:30

    fireEvent.click(screen.getByRole("button", { name: "Seguir conectado" }));
    await vi.advanceTimersByTimeAsync(0);

    expect(sessionApi.reportActivity).toHaveBeenCalledOnce();
    expect(onSessionRefreshed).toHaveBeenCalledWith(refreshedSession);
    expect(events.trackEvent).toHaveBeenCalledWith(EventName.SessionExtended);
  });

  it("reports activity at most once per 60 seconds", async () => {
    const session = makeSession();
    vi.spyOn(sessionApi, "reportActivity").mockResolvedValue(makeSession());
    render(<SessionManager session={session} onSessionRefreshed={vi.fn()} />);

    window.dispatchEvent(new Event("keydown"));
    window.dispatchEvent(new Event("keydown"));
    await vi.advanceTimersByTimeAsync(0);
    expect(sessionApi.reportActivity).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(59 * 1000);
    window.dispatchEvent(new Event("keydown"));
    await vi.advanceTimersByTimeAsync(0);
    expect(sessionApi.reportActivity).toHaveBeenCalledTimes(1); // Still throttled.

    await vi.advanceTimersByTimeAsync(1000); // -> 60s since the first report.
    window.dispatchEvent(new Event("keydown"));
    await vi.advanceTimersByTimeAsync(0);
    expect(sessionApi.reportActivity).toHaveBeenCalledTimes(2);
  });
});
