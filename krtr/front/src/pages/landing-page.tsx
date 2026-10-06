import type { JSX } from "react";
import { useEffect } from "react";
import { ArrowRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import { EventName } from "@/api/event-names";
import { trackEvent } from "@/api/events";
import { LOGOUT_REASON_PARAM, LogoutReason, parseLogoutReason } from "@/api/session";
import { BrandIllustration, BrandMark } from "@/components/brand-mark";
import { LanguageSelector } from "@/components/language-selector";
import { Button } from "@/components/ui/button";
import { Kicker } from "@/components/ui/kicker";
import { Notice } from "@/components/ui/notice";
import { resolveLanguage, type Language } from "@/i18n/languages";
import { getLoginUrl, LOGIN_NOTICE_PARAM, LoginNotice, parseLoginNotice } from "@/lib/auth";
import { AppPath } from "@/lib/routes";

/** The message each logout reason shows on the landing page. */
const LOGOUT_MESSAGE_KEYS: Record<LogoutReason, string> = {
  [LogoutReason.UserRequested]: "logout_message_user",
  [LogoutReason.IdleTimeout]: "session_expired_idle_message",
  [LogoutReason.AbsoluteTimeout]: "session_expired_absolute_message",
};

/** The message each login notice shows on the landing page. */
const LOGIN_NOTICE_MESSAGE_KEYS: Record<LoginNotice, string> = {
  [LoginNotice.Failed]: "login_failed",
};

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

/** The "why you were logged out" notice, when the URL carries a known reason. */
function LogoutReasonNotice(): JSX.Element | null {
  const { t } = useTranslation();
  const params = new URLSearchParams(window.location.search);
  const reason = parseLogoutReason(params.get(LOGOUT_REASON_PARAM));
  if (!reason) return null;
  return (
    <Notice role="status" className="max-w-[440px]">
      {t(LOGOUT_MESSAGE_KEYS[reason])}
    </Notice>
  );
}

/** The "your login did not complete" alert, when a rejected callback sent the user back. */
function LoginNoticeAlert(): JSX.Element | null {
  const { t } = useTranslation();
  const params = new URLSearchParams(window.location.search);
  const notice = parseLoginNotice(params.get(LOGIN_NOTICE_PARAM));
  if (!notice) return null;
  return (
    <Notice role="alert" className="max-w-[440px]">
      {t(LOGIN_NOTICE_MESSAGE_KEYS[notice])}
    </Notice>
  );
}

/** The left column: kicker, headline, tagline, the login button and any login or logout notice. */
function LandingHero(): JSX.Element {
  const { t, i18n } = useTranslation();
  return (
    <section className="flex flex-col gap-6 border-b-2 p-4 pt-12 md:border-r-2 md:border-b-0 md:p-8 md:pt-18">
      <Kicker>{t("landing_kicker")}</Kicker>
      <h1 className="m-0 text-[clamp(44px,6vw,84px)] leading-[0.95] tracking-[-0.035em] text-balance">
        {t("landing_title")}
      </h1>
      <p className="m-0 max-w-[440px] text-lg leading-normal text-pretty">
        {t("login_landing_tagline")}
      </p>
      <Button
        size="lg"
        className="mt-2 min-w-60 justify-between self-start"
        onClick={() => navigateToLogin(resolveLanguage(i18n.language))}
      >
        {t("login_button")}
        <ArrowRight aria-hidden className="size-[18px]" />
      </Button>
      <LoginNoticeAlert />
      <LogoutReasonNotice />
    </section>
  );
}

/**
 * The public landing page, which doubles as the login screen (§1: "Landing
 * = login").
 *
 * Exists as the app's only unauthenticated screen: the krtr brand, the
 * language selector, and the button that starts the OIDC login flow.
 */
export function LandingPage(): JSX.Element {
  const { t } = useTranslation();

  useEffect(() => {
    void trackEvent(EventName.PageView, { path: AppPath.Landing });
  }, []);

  return (
    <div className="flex min-h-svh flex-col">
      <header className="flex items-center gap-4 border-b-2 px-4 py-4 md:px-8">
        <BrandMark />
        <LanguageSelector />
      </header>
      <main className="grid flex-1 border-b-2 md:grid-cols-2">
        <LandingHero />
        <section className="flex items-center p-4 md:p-8">
          <BrandIllustration />
        </section>
      </main>
      <footer className="flex flex-wrap gap-x-6 gap-y-1 px-4 py-4 text-xs text-neutral-700 md:px-8">
        <span>{t("landing_footer_copyright", { year: new Date().getFullYear() })}</span>
        <span>{t("landing_footer_security")}</span>
      </footer>
    </div>
  );
}
