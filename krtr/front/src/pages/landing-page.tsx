import type { JSX } from "react";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { EventName } from "@/api/event-names";
import { trackEvent } from "@/api/events";
import { LanguageSelector } from "@/components/language-selector";
import { Button } from "@/components/ui/button";
import { resolveLanguage, type Language } from "@/i18n/languages";
import { getLoginUrl } from "@/lib/auth";

const LANDING_PATH = "/";

/**
 * Navigates the browser to `/auth/login`, in the given language.
 *
 * Exists as the module-level function the login button's `onClick`
 * delegates to (full page navigation, not client-side routing: `/auth/login`
 * is a backend route that starts the OIDC flow).
 *
 * @param language - The interface's current language, forwarded as `lang`.
 * @returns Nothing.
 */
function navigateToLogin(language: Language): void {
  window.location.assign(getLoginUrl(language));
}

/**
 * The public landing page, which doubles as the login screen (§1: "Landing
 * = login").
 *
 * Exists as the app's only unauthenticated screen: the krtr brand, the
 * language selector, and the button that starts the OIDC login flow.
 */
export function LandingPage(): JSX.Element {
  const { t, i18n } = useTranslation();

  useEffect(() => {
    void trackEvent(EventName.PageView, { path: LANDING_PATH });
  }, []);

  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-6 px-4">
      <LanguageSelector />
      <h1 className="text-3xl font-semibold text-foreground">{t("app_name")}</h1>
      <p className="max-w-sm text-center text-muted-foreground">{t("login_landing_tagline")}</p>
      <Button type="button" onClick={() => navigateToLogin(resolveLanguage(i18n.language))}>
        {t("login_button")}
      </Button>
    </main>
  );
}
