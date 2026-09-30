import type { JSX } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { logout } from "@/api/session";
import { SessionManager } from "@/components/session-manager";
import { Button } from "@/components/ui/button";
import { useSession } from "@/hooks/use-session";

const SUPPORT_PATH = "/app/support";

/**
 * The authenticated home screen (`/app`): header with the customer's
 * number, the Soporte / Cerrar sesión buttons (§1), and the session
 * timeout manager (task 5.6, G15).
 *
 * Exists as the landing point right after login; task 5.7 adds the case
 * selection screen `SUPPORT_PATH` navigates to.
 */
export function HomePage(): JSX.Element {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [session, setSession] = useSession();

  return (
    <div className="flex min-h-svh flex-col">
      <header className="flex items-center justify-between border-b p-4">
        <span className="text-sm text-muted-foreground">
          {session ? `#${session.customer_id}` : ""}
        </span>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate(SUPPORT_PATH)}>
            {t("support_button")}
          </Button>
          <Button variant="outline" onClick={() => void logout()}>
            {t("logout_button")}
          </Button>
        </div>
      </header>
      <SessionManager session={session} onSessionRefreshed={setSession} />
    </div>
  );
}
