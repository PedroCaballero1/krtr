import { isSupportedLanguage, type Language } from "@/i18n/languages";

const LANGUAGE_STORAGE_KEY = "krtr.language";

/**
 * Reads the persisted language preference, if any (D14).
 *
 * Exists so i18next can be initialized with the user's last choice, across
 * page loads and sessions.
 *
 * @returns The stored language, or null if none was stored or storage is unavailable.
 */
export function readStoredLanguage(): Language | null {
  try {
    const storedValue = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    return isSupportedLanguage(storedValue) ? storedValue : null;
  } catch {
    return null;
  }
}

/**
 * Persists the language preference (D14).
 *
 * Exists so a language choice survives a page reload; never throws, since a
 * failed write should not break the language switch itself.
 *
 * @param language - The language the user just chose.
 * @returns Nothing.
 */
export function storeLanguage(language: Language): void {
  try {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  } catch {
    // Storage may be unavailable (private browsing, quota); the in-memory
    // i18next state still reflects the change for this session.
  }
}
