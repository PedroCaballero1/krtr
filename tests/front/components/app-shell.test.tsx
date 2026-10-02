import { render, screen, waitFor } from "@testing-library/react";
import type { JSX } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as events from "@/api/events";
import * as session from "@/api/session";
import { AppShell } from "@/components/app-shell";
import { useShellSession } from "@/hooks/use-shell-session";
import { makeSession } from "../api/fixtures";

/** A child screen that shows what it receives through the shell's outlet context. */
function SessionProbe(): JSX.Element {
  const currentSession = useShellSession();
  return <p>probe:{currentSession?.customer_id ?? "none"}</p>;
}

function renderShell() {
  return render(
    <MemoryRouter initialEntries={["/app"]}>
      <Routes>
        <Route path="/app" element={<AppShell />}>
          <Route index element={<SessionProbe />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("AppShell", () => {
  beforeEach(() => {
    vi.spyOn(events, "trackEvent").mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads /api/me once and shares it with the header and the child screen", async () => {
    const fetchSpy = vi
      .spyOn(session, "fetchCurrentSession")
      .mockResolvedValue(makeSession());

    renderShell();

    expect(await screen.findByText("probe:12345")).toBeInTheDocument();
    expect(screen.getByText("12345")).toBeInTheDocument();
    expect(fetchSpy).toHaveBeenCalledOnce();
  });

  describe("without a session", () => {
    const originalLocation = window.location;
    let assignSpy: ReturnType<typeof vi.fn>;

    beforeEach(() => {
      assignSpy = vi.fn();
      Object.defineProperty(window, "location", {
        configurable: true,
        value: { ...originalLocation, assign: assignSpy },
      });
    });

    afterEach(() => {
      Object.defineProperty(window, "location", {
        configurable: true,
        value: originalLocation,
      });
    });

    it("redirects to the landing page (via apiFetch's 401 handling)", async () => {
      // fetchCurrentSession is left un-mocked here, so it goes through the
      // real apiFetch -> the actual mechanism that redirects on 401.
      vi.spyOn(globalThis, "fetch").mockResolvedValue(
        new Response(
          JSON.stringify({
            error: "unauthorized",
            message_key: "errors.unauthorized",
          }),
          { status: 401 },
        ),
      );

      renderShell();

      await waitFor(() => expect(assignSpy).toHaveBeenCalledWith("/"));
      expect(screen.getByText("probe:none")).toBeInTheDocument();
    });
  });
});
