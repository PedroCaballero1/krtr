import { useOutletContext } from "react-router-dom";
import type { CurrentSession } from "@/api/session";

/**
 * Reads the session `AppShell` loaded, from inside any `/app/*` screen.
 *
 * Exists so screens under the shell (e.g. the home greeting) reuse the
 * shell's single `/api/me` result instead of fetching it again.
 *
 * @returns The current session, or null while loading or outside the shell.
 */
export function useShellSession(): CurrentSession | null {
  return useOutletContext<CurrentSession | null | undefined>() ?? null;
}
