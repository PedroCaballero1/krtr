import type { JSX } from "react";
import { Outlet } from "react-router-dom";
import { AppHeader } from "@/components/app-header";
import { SessionManager } from "@/components/session-manager";
import { useSession } from "@/hooks/use-session";

/**
 * The layout every authenticated screen (`/app`, `/app/support`,
 * `/app/chat/:id`) renders inside: the shared header, the screen itself,
 * and the session timeout manager (G15).
 *
 * Exists so the session is loaded once (`/api/me`) and the timeout rules
 * apply on every authenticated screen, not only on the home page; the
 * session is handed to the screens through the outlet context (see
 * `useShellSession`).
 *
 * @returns The header, the matched child route, and the session overlay.
 */
export function AppShell(): JSX.Element {
  const [session, setSession] = useSession();

  return (
    <div className="flex min-h-svh flex-col">
      <AppHeader session={session} />
      <Outlet context={session} />
      <SessionManager session={session} onSessionRefreshed={setSession} />
    </div>
  );
}
