import type { Language } from "@/i18n/languages";

/**
 * Builds the URL the "Iniciar sesión" / "Entrar" button navigates to.
 *
 * Exists so the current UI language is always forwarded to `GET
 * /auth/login`, which passes it to Keycloak as `ui_locales` (§3.2 of the
 * guide) so the login form itself renders in the same language. Consumed
 * by the landing page (task 5.4).
 *
 * @param language - The currently active interface language.
 * @returns The `/auth/login` URL with `lang` set to `language`.
 */
export function getLoginUrl(language: Language): string {
  return `/auth/login?lang=${language}`;
}

/**
 * What the landing page tells the user about a login that came back to it.
 *
 * Mirrors `LoginNotice` in `krtr/back/web/routers/auth.py`: a rejected
 * `/auth/callback` redirects to `/?login=failed` instead of answering a raw
 * JSON error (task 4.4). The reason itself never reaches the URL.
 */
export const LoginNotice = {
  Failed: "failed",
} as const;

export type LoginNotice = (typeof LoginNotice)[keyof typeof LoginNotice];

/** The landing page query parameter that carries the `LoginNotice`. */
export const LOGIN_NOTICE_PARAM = "login";

/**
 * Parses a raw query-string value back into a `LoginNotice`.
 *
 * Exists so the landing page only shows a notice the backend actually
 * sends, never one for an arbitrary value typed into the URL.
 *
 * @param value - The raw `?login=` value, or null when absent.
 * @returns The matching notice, or null if absent or unknown.
 */
export function parseLoginNotice(value: string | null): LoginNotice | null {
  const notices: readonly string[] = Object.values(LoginNotice);
  return value !== null && notices.includes(value) ? (value as LoginNotice) : null;
}
