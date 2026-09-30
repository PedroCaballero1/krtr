import { describe, expect, it } from "vitest";
import { Language } from "@/i18n/languages";
import { getLoginUrl } from "@/lib/auth";

describe("getLoginUrl", () => {
  it("forwards the current language as the lang query parameter", () => {
    expect(getLoginUrl(Language.Spanish)).toBe("/auth/login?lang=es");
    expect(getLoginUrl(Language.Portuguese)).toBe("/auth/login?lang=pt-BR");
  });
});
