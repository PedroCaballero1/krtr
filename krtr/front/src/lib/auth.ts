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
