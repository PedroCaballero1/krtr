import { useEffect, useState } from "react";
import { listOpenCases, type CaseSummary } from "@/api/cases";
import { EventName } from "@/api/event-names";
import { trackEvent } from "@/api/events";

/** Loads the customer's open cases, falling back to an empty list on failure. */
async function loadOpenCases(setCases: (cases: CaseSummary[]) => void): Promise<void> {
  try {
    const cases = await listOpenCases();
    setCases(cases);
    void trackEvent(EventName.CaseListViewed, { count: cases.length });
  } catch {
    setCases([]);
  }
}

/**
 * Loads the current customer's open cases once, on mount.
 *
 * Exists so the home screen and the support screen's "Caso existente" both
 * read the list the same way (and record `case_list_viewed` the same way).
 *
 * @returns The open cases, or null while they are still loading.
 */
export function useOpenCases(): CaseSummary[] | null {
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  useEffect(() => {
    void loadOpenCases(setCases);
  }, []);
  return cases;
}
