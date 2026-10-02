import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EventName } from "@/api/event-names";
import * as events from "@/api/events";
import i18n from "@/i18n/config";
import { Language } from "@/i18n/languages";
import es from "@/i18n/locales/es.json";
import { LandingPage } from "@/pages/landing-page";

describe("LandingPage", () => {
  const originalLocation = window.location;
  let assignSpy: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    await i18n.changeLanguage(Language.Spanish);
    assignSpy = vi.fn();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...originalLocation, assign: assignSpy },
    });
    vi.spyOn(events, "trackEvent").mockResolvedValue(undefined);
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      configurable: true,
      value: originalLocation,
    });
    vi.restoreAllMocks();
  });

  it("shows the brand, headline, tagline and the Spanish login button by default", () => {
    render(<LandingPage />);

    expect(screen.getByText("krtr")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Tu banco, cuando lo necesitas." }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Inicia sesión con tu número de cliente para abrir un caso o retomar uno que ya tengas abierto.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Iniciar sesión" }),
    ).toBeInTheDocument();
  });

  it('shows "Entrar" as the login button label in Portuguese', async () => {
    await i18n.changeLanguage(Language.Portuguese);

    render(<LandingPage />);

    expect(screen.getByRole("button", { name: "Entrar" })).toBeInTheDocument();
  });

  it("navigates to /auth/login with the current language on click", async () => {
    const user = userEvent.setup();
    render(<LandingPage />);

    await user.click(screen.getByRole("button", { name: "Iniciar sesión" }));

    expect(assignSpy).toHaveBeenCalledWith("/auth/login?lang=es");
  });

  it("forwards the switched language once Português is picked", async () => {
    const user = userEvent.setup();
    render(<LandingPage />);

    await user.click(screen.getByRole("button", { name: "Português" }));
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(assignSpy).toHaveBeenCalledWith("/auth/login?lang=pt-BR");
  });

  it("records a page_view event for the landing path on mount", () => {
    render(<LandingPage />);

    expect(events.trackEvent).toHaveBeenCalledWith(EventName.PageView, {
      path: "/",
    });
  });

  describe("logout reason notice", () => {
    function renderWithSearch(search: string) {
      Object.defineProperty(window, "location", {
        configurable: true,
        value: { ...originalLocation, assign: assignSpy, search },
      });
      return render(<LandingPage />);
    }

    it.each([
      ["?logout=idle", es.session_expired_idle_message],
      ["?logout=absolute", es.session_expired_absolute_message],
      ["?logout=user", es.logout_message_user],
    ])("shows the message matching %s", (search, expectedMessage) => {
      renderWithSearch(search);

      expect(screen.getByRole("status")).toHaveTextContent(expectedMessage);
    });

    it("shows nothing without a reason, or for an unknown one", () => {
      const { unmount } = renderWithSearch("");
      expect(screen.queryByRole("status")).not.toBeInTheDocument();
      unmount();

      renderWithSearch("?logout=<script>");
      expect(screen.queryByRole("status")).not.toBeInTheDocument();
    });
  });
});
