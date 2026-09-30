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
  // TEMP DEMO MOCK — revert before continuing real work.
  return {
    customer_id: "48213",
    idle_expires_at: new Date(Date.now() + 5 * 60 * 1000).toISOString(),
    absolute_expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
  };
  // eslint-disable-next-line no-unreachable
  const response = await apiFetch("/api/me");
  return (await response.json()) as CurrentSession;
}

/**
 * Reports user activity, extending the idle timeout (G15).
 *
 * Exists as the one place that calls `POST /api/session/activity`, called
 * by the session manager (task 5.6) at most every 60 s and whenever
 * "Seguir conectado" is clicked.
 *
 * @returns The refreshed session, with updated expiry timestamps.
 */
export async function reportActivity(): Promise<CurrentSession> {
  // TEMP DEMO MOCK — revert before continuing real work.
  return fetchCurrentSession();
  // eslint-disable-next-line no-unreachable
  const response = await apiFetch("/api/session/activity", { method: "POST" });
  return (await response.json()) as CurrentSession;
}

/** Why a session ended, forwarded to the landing page so it can say so. */
export const LogoutReason = {
  UserRequested: "user",
  IdleTimeout: "idle",
  AbsoluteTimeout: "absolute",
} as const;

export type LogoutReason = (typeof LogoutReason)[keyof typeof LogoutReason];

/** The landing page query parameter that carries the `LogoutReason`. */
export const LOGOUT_REASON_PARAM = "logout";

/**
 * Parses a raw query-string value back into a `LogoutReason`.
 *
 * Exists so the landing page only ever shows a message for a reason this
 * module actually emits, never for an arbitrary value typed into the URL.
 *
 * @param value - The raw `?logout=` value, or null when absent.
 * @returns The matching reason, or null if absent or unknown.
 */
export function parseLogoutReason(value: string | null): LogoutReason | null {
  const reasons: readonly string[] = Object.values(LogoutReason);
  return value !== null && reasons.includes(value) ? (value as LogoutReason) : null;
}

/**
 * Logs the user out: calls `POST /auth/logout`, then always returns to the
 * landing page, whether or not the request succeeded.
 *
 * Exists as the one logout action, used by the authenticated header (task
 * 5.5) and the session manager (task 5.6), so a failed logout request never
 * leaves the user stuck on `/app`.
 *
 * @param reason - Why the session ended; the landing page shows the matching message.
 * @returns Nothing; navigates away rather than resolving to a value the
 * caller would act on.
 */
export async function logout(reason: LogoutReason = LogoutReason.UserRequested): Promise<void> {
  try {
    await apiFetch("/auth/logout", { method: "POST" });
  } catch {
    // A failed logout request must not strand the user on /app: the
    // server-side session may already be gone, or unreachable, either way.
  } finally {
    window.location.assign(`/?${LOGOUT_REASON_PARAM}=${reason}`);
  }
}
