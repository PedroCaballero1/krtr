import type { JSX } from "react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { fetchCurrentSession, logout } from "@/api/session";
import { Button } from "@/components/ui/button";

const SUPPORT_PATH = "/app/support";

/**
 * Loads the current session and stores its customer_id.
 *
 * Exists as the module-level function `HomePage`'s mount effect delegates
 * to. If there is no valid session, `apiFetch` (called by
 * `fetchCurrentSession`) already redirects to the landing page on 401, so
 * this only needs to handle the successful case.
 *
 * @param setCustomerId - Setter for the loaded customer_id.
 * @returns Nothing.
 */
async function loadCustomerId(setCustomerId: (customerId: string) => void): Promise<void> {
  try {
    const session = await fetchCurrentSession();
    setCustomerId(session.customer_id);
  } catch {
    // Unauthenticated: apiFetch has already redirected to "/". Any other
    // failure just leaves the header's customer number blank.
  }
}

/**
 * The authenticated home screen (`/app`): header with the customer's
 * number, and the Soporte / Cerrar sesión buttons (§1).
 *
 * Exists as the landing point right after login; task 5.7 adds the case
 * selection screen `SUPPORT_PATH` navigates to.
 */
export function HomePage(): JSX.Element {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [customerId, setCustomerId] = useState<string | null>(null);

  useEffect(() => {
    void loadCustomerId(setCustomerId);
  }, []);

  return (
    <div className="flex min-h-svh flex-col">
      <header className="flex items-center justify-between border-b p-4">
        <span className="text-sm text-muted-foreground">{customerId ? `#${customerId}` : ""}</span>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate(SUPPORT_PATH)}>
            {t("support_button")}
          </Button>
          <Button variant="outline" onClick={() => void logout()}>
            {t("logout_button")}
          </Button>
        </div>
      </header>
    </div>
  );
}
