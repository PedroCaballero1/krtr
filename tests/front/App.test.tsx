import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "@/App";
import es from "@/i18n/locales/es.json";

describe("App", () => {
  it("renders the landing page, with the krtr brand, on the root route", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { level: 1, name: es.landing_title }),
    ).toBeInTheDocument();
    expect(screen.getByText("krtr")).toBeInTheDocument();
  });
});
