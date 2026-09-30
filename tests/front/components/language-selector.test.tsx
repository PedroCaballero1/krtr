import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import App from "@/App";
import i18n from "@/i18n/config";
import { Language } from "@/i18n/languages";
import es from "@/i18n/locales/es.json";
import ptBR from "@/i18n/locales/pt-BR.json";

describe("LanguageSelector, through the app", () => {
  beforeEach(async () => {
    // i18next is a module-level singleton, so each test starts from a known
    // language regardless of what an earlier test switched to.
    await i18n.changeLanguage(Language.Spanish);
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("switches every translated text on the page when Português is picked", async () => {
    const user = userEvent.setup();
    render(<App />);
    expect(screen.getByText(es.login_landing_tagline)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Português" }));

    expect(screen.getByText(ptBR.login_landing_tagline)).toBeInTheDocument();
    expect(
      screen.queryByText(es.login_landing_tagline),
    ).not.toBeInTheDocument();
  });

  it("persists the choice to localStorage (D14)", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "Português" }));

    expect(localStorage.getItem("krtr.language")).toBe("pt-BR");
  });

  it("marks the active language button as pressed", async () => {
    const user = userEvent.setup();
    render(<App />);
    expect(screen.getByRole("button", { name: "Español" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    await user.click(screen.getByRole("button", { name: "Português" }));

    expect(screen.getByRole("button", { name: "Português" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "Español" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });
});
