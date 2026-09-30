import { Language } from "@/i18n/languages";

const LANGUAGE_STORAGE_KEY = "krtr.language";

/**
 * Checks whether a stored string is one of the supported languages.
 *
 * Exists so a value read from localStorage (which could hold anything, or
 * nothing) is only trusted once it is verified against the known set.
 *
 * @param value - The raw string read from storage, or null.
 * @returns Whether `value` is a valid `Language`.
 */
function isSupportedLanguage(value: string | null): value is Language {
  return value === Language.Spanish || value === Language.Portuguese;
}

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
