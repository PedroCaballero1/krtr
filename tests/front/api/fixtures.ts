import type { CurrentSession } from "@/api/session";

/**
 * Builds a `CurrentSession` with expiry timestamps relative to now.
 *
 * Exists so tests never hardcode an absolute ISO timestamp (which would
 * silently become "already expired" as real time passes), used by any test
 * that needs a session further from expiry than it's testing for.
 *
 * @param overrides - Fields to override (e.g. to make it (near) expired).
 * @returns A session valid for the next 5 (idle) / 30 (absolute) minutes.
 */
export function makeSession(
  overrides: Partial<CurrentSession> = {},
): CurrentSession {
  const now = Date.now();
  return {
    customer_id: "12345",
    idle_expires_at: new Date(now + 5 * 60 * 1000).toISOString(),
    absolute_expires_at: new Date(now + 30 * 60 * 1000).toISOString(),
    ...overrides,
  };
}
