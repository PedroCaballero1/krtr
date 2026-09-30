import { useEffect, useState } from "react";
import { fetchCurrentSession, type CurrentSession } from "@/api/session";

/**
 * Loads the current session once and stores it.
 *
 * Exists as the module-level function `useSession`'s mount effect delegates
 * to. If there is no valid session, `apiFetch` (via `fetchCurrentSession`)
 * has already redirected to the landing page on 401.
 *
 * @param setSession - Setter for the loaded session.
 * @returns Nothing.
 */
async function loadInitialSession(setSession: (session: CurrentSession) => void): Promise<void> {
  try {
    const session = await fetchCurrentSession();
    setSession(session);
  } catch {
    // Unauthenticated: apiFetch has already redirected to "/".
  }
}

/**
 * Loads and holds the current session (`GET /api/me`), shared by every
 * authenticated screen that needs it.
 *
 * Exists so `/app`'s header (customer number) and its session manager
 * (task 5.6, idle/absolute timeouts) read and refresh the same session
 * state instead of each fetching it independently.
 *
 * @returns A tuple of the session (null until loaded) and its setter, so a
 * caller like the session manager can update it after `reportActivity`.
 */
export function useSession(): [CurrentSession | null, (session: CurrentSession) => void] {
  const [session, setSession] = useState<CurrentSession | null>(null);

  useEffect(() => {
    void loadInitialSession(setSession);
  }, []);

  return [session, setSession];
}
