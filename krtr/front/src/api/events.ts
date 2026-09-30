import { apiFetch } from "@/api/client";
import type { EventName } from "@/api/event-names";

/**
 * Reports a UI event to the backend's audit log (G21), via `POST /api/events`.
 *
 * Exists as the one function every screen calls to instrument itself (task
 * 5.10), so event submission (endpoint, shape, failure handling) lives in
 * one place. Never throws: a failed or dropped event must never break the
 * feature that triggered it — this is best-effort telemetry, not a
 * feature the UI depends on.
 *
 * @param eventName - The event's type, from the shared `EventName` catalog.
 * @param properties - The event's properties (kept under the backend's 4 KB limit).
 * @returns A promise that always resolves, once the request settles or fails.
 */
export async function trackEvent(
  eventName: EventName,
  properties: Record<string, unknown> = {},
): Promise<void> {
  try {
    await apiFetch("/api/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event_name: eventName, properties }),
    });
  } catch {
    // Best-effort: dropping a UI event must never surface to the caller.
  }
}
