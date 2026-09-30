/** The languages the krtr interface and login support (§1 of the guide). */
export const Language = {
  Spanish: "es",
  Portuguese: "pt-BR",
} as const;

export type Language = (typeof Language)[keyof typeof Language];

/** The language used when nothing else has been chosen (D14). */
export const DEFAULT_LANGUAGE: Language = Language.Spanish;

/**
 * Checks whether a string is one of the supported languages.
 *
 * Exists as the one place that validates an arbitrary string (from
 * storage, i18next, or a URL) against the known set, so callers never
 * duplicate the comparison.
 *
 * @param value - The string to check, or null.
 * @returns Whether `value` is a valid `Language`.
 */
export function isSupportedLanguage(value: string | null | undefined): value is Language {
  return value === Language.Spanish || value === Language.Portuguese;
}

/**
 * Resolves an arbitrary string to a supported `Language`, falling back to
 * the default (D14) when it isn't one.
 *
 * Exists so call sites reading a language from somewhere untyped (e.g.
 * i18next's `i18n.language`) get back a `Language`, not a bare string.
 *
 * @param value - The string to resolve, or null.
 * @returns `value` itself if supported, otherwise `DEFAULT_LANGUAGE`.
 */
export function resolveLanguage(value: string | null | undefined): Language {
  return isSupportedLanguage(value) ? value : DEFAULT_LANGUAGE;
}

/**
 * Each language's own name, in itself — never translated, so the selector
 * always reads "Español" / "Português" regardless of the active language.
 */
export const LANGUAGE_LABELS: Record<Language, string> = {
  [Language.Spanish]: "Español",
  [Language.Portuguese]: "Português",
};

/** The compact code the selector shows on screen (its accessible name stays the full label). */
export const LANGUAGE_SHORT_LABELS: Record<Language, string> = {
  [Language.Spanish]: "ES",
  [Language.Portuguese]: "PT",
};
