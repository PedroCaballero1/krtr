import { apiFetch } from "@/api/client";

/** The `GET /api/me` / `POST /api/session/activity` response contract (§3.4). */
export interface CurrentSession {
  customer_id: string;
  idle_expires_at: string;
  absolute_expires_at: string;
}

/**
 * Fetches the current session's details.
 *
 * Exists as the one place that calls `GET /api/me`; if there is no valid
 * session, `apiFetch` itself handles the 401 (redirect to the landing page),
 * so callers only need to handle the successful case.
 *
 * @returns The current session's customer_id and expiry timestamps.
 */
export async function fetchCurrentSession(): Promise<CurrentSession> {
  const response = await apiFetch("/api/me");
  return (await response.json()) as CurrentSession;
}

/**
 * Logs the user out: calls `POST /auth/logout`, then always returns to the
 * landing page, whether or not the request succeeded.
 *
 * Exists as the one logout action, used by the authenticated header (task
 * 5.5) so a failed logout request never leaves the user stuck on `/app`.
 *
 * @returns Nothing; navigates away rather than resolving to a value the
 * caller would act on.
 */
export async function logout(): Promise<void> {
  try {
    await apiFetch("/auth/logout", { method: "POST" });
  } catch {
    // A failed logout request must not strand the user on /app: the
    // server-side session may already be gone, or unreachable, either way.
  } finally {
    window.location.assign("/");
  }
}
