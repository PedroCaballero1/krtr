import { afterEach, describe, expect, it, vi } from "vitest";
import { Language } from "@/i18n/languages";
import { readStoredLanguage, storeLanguage } from "@/i18n/storage";

const STORAGE_KEY = "krtr.language";

describe("storeLanguage / readStoredLanguage", () => {
  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("round-trips a stored language", () => {
    storeLanguage(Language.Portuguese);

    expect(readStoredLanguage()).toBe(Language.Portuguese);
    expect(localStorage.getItem(STORAGE_KEY)).toBe("pt-BR");
  });

  it("returns null when nothing has been stored", () => {
    expect(readStoredLanguage()).toBeNull();
  });

  it("returns null for a stored value outside the supported languages", () => {
    localStorage.setItem(STORAGE_KEY, "fr");

    expect(readStoredLanguage()).toBeNull();
  });

  it("never throws when localStorage.getItem fails", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("storage disabled");
    });

    expect(readStoredLanguage()).toBeNull();
  });

  it("never throws when localStorage.setItem fails", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("quota exceeded");
    });

    expect(() => storeLanguage(Language.Spanish)).not.toThrow();
  });
});
