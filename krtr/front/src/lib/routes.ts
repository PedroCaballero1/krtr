/** The SPA's fixed client-side paths, so screens never hardcode a route string. */
export const AppPath = {
  Landing: "/",
  Home: "/app",
  Support: "/app/support",
} as const;

export type AppPath = (typeof AppPath)[keyof typeof AppPath];

/**
 * Builds the chat route for a confirmed incident_id.
 *
 * Exists as the one place that encodes an incident_id into `/app/chat/:id`,
 * shared by every screen that opens a case (home's open-cases list and the
 * support screen's three paths: new, picked from the list, typed id).
 *
 * @param incidentId - The case to open.
 * @returns The chat path for that case, with the id URL-encoded.
 */
export function buildChatPath(incidentId: string): string {
  return `/app/chat/${encodeURIComponent(incidentId)}`;
}
