import { apiFetch } from "@/api/client";

/** One open case, as listed by `GET /api/cases?status=open` (§3.4). */
export interface CaseSummary {
  incident_id: string;
  opened_at: string;
  summary: string;
}

/** The `{incident_id}` shape both `POST /api/cases` and `.../resume` return. */
export interface CaseReference {
  incident_id: string;
}

/**
 * Lists the current customer's open cases.
 *
 * @returns The open cases, as the backend orders them.
 */
export async function listOpenCases(): Promise<CaseSummary[]> {
  const response = await apiFetch("/api/cases?status=open");
  return (await response.json()) as CaseSummary[];
}

/**
 * Creates a new case for "Caso nuevo".
 *
 * @returns The new case's incident_id.
 */
export async function createCase(): Promise<CaseReference> {
  const response = await apiFetch("/api/cases", { method: "POST" });
  return (await response.json()) as CaseReference;
}

/**
 * Resumes a case by its incident_id, typed in by the user.
 *
 * Exists as the one place that calls `POST /api/cases/resume`, which the
 * backend answers with the same 404 whether the id doesn't exist or
 * belongs to another customer (IDOR protection, §3.4) — `apiFetch` turns
 * that into a thrown `ApiError` with `status === 404`.
 *
 * @param incidentId - The case id the user typed in.
 * @returns The confirmed case's incident_id.
 */
export async function resumeCase(incidentId: string): Promise<CaseReference> {
  const response = await apiFetch("/api/cases/resume", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ incident_id: incidentId }),
  });
  return (await response.json()) as CaseReference;
}
