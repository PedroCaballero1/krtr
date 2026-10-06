import { describe, expect, it } from "vitest";
import { Language } from "@/i18n/languages";
import { getLoginUrl, LoginNotice, parseLoginNotice } from "@/lib/auth";

describe("getLoginUrl", () => {
  it("forwards the current language as the lang query parameter", () => {
    expect(getLoginUrl(Language.Spanish)).toBe("/auth/login?lang=es");
    expect(getLoginUrl(Language.Portuguese)).toBe("/auth/login?lang=pt-BR");
  });
});

describe("parseLoginNotice", () => {
  it("accepts the notice the backend sends", () => {
    expect(parseLoginNotice("failed")).toBe(LoginNotice.Failed);
  });

  it("ignores an absent or unknown value", () => {
    expect(parseLoginNotice(null)).toBeNull();
    expect(parseLoginNotice("<script>")).toBeNull();
  });
});
