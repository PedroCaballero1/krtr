import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { JSX } from "react";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as cases from "@/api/cases";
import { EventName } from "@/api/event-names";
import * as events from "@/api/events";
import { HomePage } from "@/pages/home-page";
import { makeSession } from "../api/fixtures";

function SupportPlaceholder(): JSX.Element {
  return <p>support screen</p>;
}

function ChatPlaceholder(): JSX.Element {
  return <p>chat screen</p>;
}

/** Stands in for AppShell: hands the session to HomePage through the outlet context. */
function FakeShell(): JSX.Element {
  return <Outlet context={makeSession()} />;
}

function renderHomePage() {
  return render(
    <MemoryRouter initialEntries={["/app"]}>
      <Routes>
        <Route element={<FakeShell />}>
          <Route path="/app" element={<HomePage />} />
        </Route>
        <Route path="/app/support" element={<SupportPlaceholder />} />
        <Route path="/app/chat/:incidentId" element={<ChatPlaceholder />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("HomePage", () => {
  beforeEach(() => {
    vi.spyOn(events, "trackEvent").mockResolvedValue(undefined);
    vi.spyOn(cases, "listOpenCases").mockResolvedValue([
      {
        incident_id: "case-7",
        opened_at: "2026-09-27T10:00:00Z",
        summary: "Cargo no reconocido",
      },
    ]);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("greets the customer by the number from the shell's session", () => {
    renderHomePage();

    expect(
      screen.getByRole("heading", { level: 1, name: "Hola, 12345" }),
    ).toBeInTheDocument();
  });

  it('navigates to /app/support from the "Ir a soporte" tile', async () => {
    const user = userEvent.setup();
    renderHomePage();

    await user.click(screen.getByRole("button", { name: "Ir a soporte" }));

    expect(await screen.findByText("support screen")).toBeInTheDocument();
    expect(events.trackEvent).toHaveBeenCalledWith(EventName.SupportClicked);
  });

  it("lists the open cases with their count, and opens one on click", async () => {
    const user = userEvent.setup();
    renderHomePage();

    expect(await screen.findByText("Cargo no reconocido")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /case-7/ }));

    expect(await screen.findByText("chat screen")).toBeInTheDocument();
    expect(events.trackEvent).toHaveBeenCalledWith(
      EventName.CaseResumeSucceeded,
      { incident_id: "case-7" },
    );
  });
});
