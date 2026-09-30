import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { JSX } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EventName } from "@/api/event-names";
import * as events from "@/api/events";
import * as session from "@/api/session";
import { HomePage } from "@/pages/home-page";
import { makeSession } from "../api/fixtures";

function SupportPlaceholder(): JSX.Element {
  return <p>support screen</p>;
}

function renderHomePage() {
  return render(
    <MemoryRouter initialEntries={["/app"]}>
      <Routes>
        <Route path="/app" element={<HomePage />} />
        <Route path="/app/support" element={<SupportPlaceholder />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("HomePage", () => {
  beforeEach(() => {
    vi.spyOn(events, "trackEvent").mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the customer's number once /api/me resolves", async () => {
    vi.spyOn(session, "fetchCurrentSession").mockResolvedValue(makeSession());

    renderHomePage();

    expect(await screen.findByText("#12345")).toBeInTheDocument();
  });

  it("navigates to /app/support when Soporte is clicked", async () => {
    vi.spyOn(session, "fetchCurrentSession").mockResolvedValue(makeSession());
    const user = userEvent.setup();
    renderHomePage();

    await user.click(screen.getByRole("button", { name: "Soporte" }));

    expect(await screen.findByText("support screen")).toBeInTheDocument();
    expect(events.trackEvent).toHaveBeenCalledWith(EventName.SupportClicked);
  });

  it("calls logout() when Cerrar sesión is clicked", async () => {
    vi.spyOn(session, "fetchCurrentSession").mockResolvedValue(makeSession());
    const logoutSpy = vi.spyOn(session, "logout").mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderHomePage();
    await screen.findByText("#12345");

    await user.click(screen.getByRole("button", { name: "Cerrar sesión" }));

    expect(logoutSpy).toHaveBeenCalledOnce();
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

      renderHomePage();

      await waitFor(() => expect(assignSpy).toHaveBeenCalledWith("/"));
    });
  });
});
