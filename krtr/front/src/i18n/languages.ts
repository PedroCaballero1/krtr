/** The languages the krtr interface and login support (§1 of the guide). */
export const Language = {
  Spanish: "es",
  Portuguese: "pt-BR",
} as const;

export type Language = (typeof Language)[keyof typeof Language];

/** The language used when nothing else has been chosen (D14). */
export const DEFAULT_LANGUAGE: Language = Language.Spanish;

/**
 * Each language's own name, in itself — never translated, so the selector
 * always reads "Español" / "Português" regardless of the active language.
 */
export const LANGUAGE_LABELS: Record<Language, string> = {
  [Language.Spanish]: "Español",
  [Language.Portuguese]: "Português",
};
