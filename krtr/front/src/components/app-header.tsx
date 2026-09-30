import type { JSX } from "react";
import { LifeBuoy, LogOut } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { logout, type CurrentSession } from "@/api/session";
import { BrandMark } from "@/components/brand-mark";
import { LanguageSelector } from "@/components/language-selector";
import { Button } from "@/components/ui/button";
import { LabeledValue } from "@/components/ui/labeled-value";
import { useNow } from "@/hooks/use-now";
import { formatMinutesSeconds } from "@/lib/format";
import { goToSupport } from "@/lib/support";

/** Shown in place of a value the session hasn't provided yet. */
const PENDING_VALUE = "—";
const MS_PER_SECOND = 1000;

/** The header's live "Sesión" timer: time left before the idle timeout. */
function SessionCountdown({ session }: { session: CurrentSession | null }): JSX.Element {
  const { t } = useTranslation();
  const now = useNow();
  const remainingSeconds = session
    ? Math.ceil((new Date(session.idle_expires_at).getTime() - now) / MS_PER_SECOND)
    : null;
  return (
    <LabeledValue label={t("header_session")} className="border-r-2 pr-4">
      {remainingSeconds === null ? PENDING_VALUE : formatMinutesSeconds(remainingSeconds)}
    </LabeledValue>
  );
}

/**
 * The authenticated header (task 5.5): brand, the customer's number, the
 * session timer, the language selector, and the Soporte / Cerrar sesión
 * buttons.
 *
 * Exists as the one header every `/app/*` screen shares (mounted by
 * `AppShell`), matching the design's app shell.
 *
 * @param props.session - The current session, or null while it loads.
 * @returns The header bar.
 */
export function AppHeader({ session }: { session: CurrentSession | null }): JSX.Element {
  const { t } = useTranslation();
  const navigate = useNavigate();
  return (
    <header className="flex flex-wrap items-center gap-4 border-b-2 px-4 py-3 md:px-8">
      <BrandMark />
      <LabeledValue label={t("header_customer_number")} className="border-r-2 pr-4">
        {session?.customer_id ?? PENDING_VALUE}
      </LabeledValue>
      <SessionCountdown session={session} />
      <LanguageSelector />
      <Button onClick={() => goToSupport(navigate)}>
        <LifeBuoy aria-hidden />
        {t("support_button")}
      </Button>
      <Button variant="outline" onClick={() => void logout()}>
        <LogOut aria-hidden />
        {t("logout_button")}
      </Button>
    </header>
  );
}
