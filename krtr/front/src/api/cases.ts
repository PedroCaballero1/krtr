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
  // TEMP DEMO MOCK — revert before continuing real work.
  return [
    {
      incident_id: "CASE-2026-0142",
      opened_at: "2026-09-25T14:30:00Z",
      summary: "Tarjeta de crédito bloqueada por consumo inusual",
    },
    {
      incident_id: "CASE-2026-0158",
      opened_at: "2026-09-28T09:15:00Z",
      summary: "Solicitud de aumento de cupo de crédito",
    },
  ];
  // eslint-disable-next-line no-unreachable
  const response = await apiFetch("/api/cases?status=open");
  return (await response.json()) as CaseSummary[];
}

/**
 * Creates a new case for "Caso nuevo".
 *
 * @returns The new case's incident_id.
 */
export async function createCase(): Promise<CaseReference> {
  // TEMP DEMO MOCK — revert before continuing real work.
  return { incident_id: `CASE-2026-${Math.floor(Math.random() * 9000 + 1000)}` };
  // eslint-disable-next-line no-unreachable
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
  // TEMP DEMO MOCK — revert before continuing real work.
  const { ApiError } = await import("@/api/client");
  if (incidentId.toLowerCase().includes("wrong")) {
    throw new ApiError(404, "not_found", "Caso no encontrado");
  }
  return { incident_id: incidentId };
  // eslint-disable-next-line no-unreachable
  const response = await apiFetch("/api/cases/resume", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ incident_id: incidentId }),
  });
  return (await response.json()) as CaseReference;
}
