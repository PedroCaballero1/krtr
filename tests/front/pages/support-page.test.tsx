import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { JSX } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as cases from "@/api/cases";
import { ApiError } from "@/api/client";
import { EventName } from "@/api/event-names";
import * as events from "@/api/events";
import { SupportPage } from "@/pages/support-page";

function ChatPlaceholder(): JSX.Element {
  return <p>chat screen</p>;
}

function renderSupportPage() {
  return render(
    <MemoryRouter initialEntries={["/app/support"]}>
      <Routes>
        <Route path="/app/support" element={<SupportPage />} />
        <Route path="/app/chat/:incidentId" element={<ChatPlaceholder />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("SupportPage", () => {
  beforeEach(() => {
    vi.spyOn(events, "trackEvent").mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('route "nuevo": creates a case and navigates to its chat', async () => {
    vi.spyOn(cases, "createCase").mockResolvedValue({ incident_id: "new-1" });
    const user = userEvent.setup();
    renderSupportPage();

    await user.click(screen.getByRole("button", { name: "Caso nuevo" }));
    expect(cases.createCase).not.toHaveBeenCalled();
    expect(events.trackEvent).toHaveBeenCalledWith(EventName.CaseModeSelected, {
      mode: "new",
    });

    await user.click(
      screen.getByRole("button", { name: "Crear caso y empezar" }),
    );

    expect(await screen.findByText("chat screen")).toBeInTheDocument();
    expect(events.trackEvent).toHaveBeenCalledWith(EventName.CaseCreated, {
      incident_id: "new-1",
    });
  });

  it('route "elegir de la lista": shows open cases and navigates on click', async () => {
    vi.spyOn(cases, "listOpenCases").mockResolvedValue([
      {
        incident_id: "case-1",
        opened_at: "2026-01-15T00:00:00Z",
        summary: "Tarjeta bloqueada",
      },
    ]);
    const user = userEvent.setup();
    renderSupportPage();
    await user.click(screen.getByRole("button", { name: "Caso existente" }));
    expect(await screen.findByText("case-1")).toBeInTheDocument();
    expect(screen.getByText(/Tarjeta bloqueada/)).toBeInTheDocument();
    expect(events.trackEvent).toHaveBeenCalledWith(EventName.CaseModeSelected, {
      mode: "existing",
    });
    expect(events.trackEvent).toHaveBeenCalledWith(EventName.CaseListViewed, {
      count: 1,
    });

    await user.click(screen.getByRole("button", { name: /case-1/ }));

    expect(await screen.findByText("chat screen")).toBeInTheDocument();
    expect(events.trackEvent).toHaveBeenCalledWith(
      EventName.CaseResumeSucceeded,
      {
        incident_id: "case-1",
      },
    );
  });

  it('route "escribir el ID": resumes a valid case and navigates', async () => {
    vi.spyOn(cases, "listOpenCases").mockResolvedValue([]);
    vi.spyOn(cases, "resumeCase").mockResolvedValue({ incident_id: "typed-1" });
    const user = userEvent.setup();
    renderSupportPage();
    await user.click(screen.getByRole("button", { name: "Caso existente" }));

    await user.type(screen.getByLabelText("Buscar por ID"), "typed-1");
    await user.click(screen.getByRole("button", { name: "Retomar" }));

    expect(await screen.findByText("chat screen")).toBeInTheDocument();
    expect(cases.resumeCase).toHaveBeenCalledWith("typed-1");
    expect(events.trackEvent).toHaveBeenCalledWith(
      EventName.CaseResumeSucceeded,
      {
        incident_id: "typed-1",
      },
    );
  });

  it('shows "Caso no encontrado" for an unknown or foreign id, without navigating', async () => {
    vi.spyOn(cases, "listOpenCases").mockResolvedValue([]);
    vi.spyOn(cases, "resumeCase").mockRejectedValue(
      new ApiError(404, "not_found", "x"),
    );
    const user = userEvent.setup();
    renderSupportPage();
    await user.click(screen.getByRole("button", { name: "Caso existente" }));

    await user.type(screen.getByLabelText("Buscar por ID"), "wrong-id");
    await user.click(screen.getByRole("button", { name: "Retomar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Caso no encontrado",
    );
    expect(screen.queryByText("chat screen")).not.toBeInTheDocument();
    expect(events.trackEvent).toHaveBeenCalledWith(EventName.CaseResumeFailed);
  });

  it("trims leading and trailing spaces from the typed id", async () => {
    vi.spyOn(cases, "listOpenCases").mockResolvedValue([]);
    const resumeSpy = vi
      .spyOn(cases, "resumeCase")
      .mockResolvedValue({ incident_id: "x" });
    const user = userEvent.setup();
    renderSupportPage();
    await user.click(screen.getByRole("button", { name: "Caso existente" }));

    await user.type(screen.getByLabelText("Buscar por ID"), "  case-42  ");
    await user.click(screen.getByRole("button", { name: "Retomar" }));

    expect(resumeSpy).toHaveBeenCalledWith("case-42");
  });

  it("the input rejects more than 64 characters", async () => {
    vi.spyOn(cases, "listOpenCases").mockResolvedValue([]);
    const user = userEvent.setup();
    renderSupportPage();
    await user.click(screen.getByRole("button", { name: "Caso existente" }));

    const input = screen.getByLabelText("Buscar por ID");
    await user.type(input, "a".repeat(80));

    expect((input as HTMLInputElement).value).toHaveLength(64);
  });

  it("marks the picked mode tile as pressed", async () => {
    vi.spyOn(cases, "listOpenCases").mockResolvedValue([]);
    const user = userEvent.setup();
    renderSupportPage();
    const existingTile = screen.getByRole("button", { name: "Caso existente" });
    expect(existingTile).toHaveAttribute("aria-pressed", "false");

    await user.click(existingTile);

    expect(existingTile).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Caso nuevo" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });
});
