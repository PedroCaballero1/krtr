import { describe, expect, it } from "vitest";
import es from "@/i18n/locales/es.json";
import ptBR from "@/i18n/locales/pt-BR.json";

describe("locale completeness", () => {
  it("has exactly the same keys in es.json and pt-BR.json", () => {
    // Guards "no quedan textos sin traducir" (task 5.2's acceptance): a key
    // present in one locale but missing in the other would fall back
    // silently to the other language's text instead of failing a build.
    expect(Object.keys(ptBR).sort()).toEqual(Object.keys(es).sort());
  });

  it("has no empty translation values in either locale", () => {
    for (const [locale, translations] of Object.entries({
      es,
      "pt-BR": ptBR,
    })) {
      for (const [key, value] of Object.entries(translations)) {
        expect(value.trim(), `${locale}.${key} must not be empty`).not.toBe("");
      }
    }
  });
});
