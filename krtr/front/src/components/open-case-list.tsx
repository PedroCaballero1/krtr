import type { JSX } from "react";
import { ArrowRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import type { CaseSummary } from "@/api/cases";
import { EventName } from "@/api/event-names";
import { trackEvent } from "@/api/events";
import { cn } from "cn";
import { CaseListLayout } from "@/lib/case-list-layout";
import { formatShortDate } from "@/lib/format";
import { buildChatPath } from "@/lib/routes";

/** Records the resume and opens a case picked directly from the list. */
function selectListedCase(incidentId: string, navigate: (path: string) => void): void {
  void trackEvent(EventName.CaseResumeSucceeded, { incident_id: incidentId });
  navigate(buildChatPath(incidentId));
}

interface CaseRowProps {
  caseSummary: CaseSummary;
  layout: CaseListLayout;
  onSelect: (incidentId: string) => void;
}

/** One clickable case: ID, opening date and summary, with a trailing arrow. */
function CaseRow({ caseSummary, layout, onSelect }: CaseRowProps): JSX.Element {
  const { i18n } = useTranslation();
  const isRow = layout === CaseListLayout.Row;
  return (
    <button
      type="button"
      className={cn(
        "grid w-full cursor-pointer grid-cols-[auto_minmax(0,1fr)_24px] items-center gap-x-4 gap-y-1 border-b-2 py-4 text-left hover:bg-surface",
        isRow && "md:grid-cols-[minmax(120px,160px)_minmax(100px,140px)_minmax(0,1fr)_24px]",
      )}
      onClick={() => onSelect(caseSummary.incident_id)}
    >
      <strong className="text-[15px] tabular-nums">{caseSummary.incident_id}</strong>
      <span className="text-sm text-neutral-700">
        {formatShortDate(caseSummary.opened_at, i18n.language)}
      </span>
      <span
        className={cn(
          "col-span-2 row-start-2 text-[15px] leading-snug",
          isRow && "md:col-span-1 md:col-start-3 md:row-start-1",
        )}
      >
        {caseSummary.summary}
      </span>
      <ArrowRight
        aria-hidden
        className={cn(
          "col-start-3 row-span-2 row-start-1 size-[18px]",
          isRow && "md:col-start-4 md:row-span-1",
        )}
      />
    </button>
  );
}

interface OpenCaseListProps {
  cases: CaseSummary[];
  layout: CaseListLayout;
}

/**
 * The list of open cases (ID, date, summary), each clickable to resume it
 * directly (G18) — the design's ruled list under a heavy top rule.
 *
 * @param props.cases - The open cases to show (see `useOpenCases`).
 * @param props.layout - `Row` for full-width screens, `Stacked` for narrow columns.
 * @returns The list, or a short message when there are no open cases.
 */
export function OpenCaseList({ cases, layout }: OpenCaseListProps): JSX.Element {
  const { t } = useTranslation();
  const navigate = useNavigate();
  if (cases.length === 0) {
    return <p className="text-neutral-700">{t("support_no_open_cases")}</p>;
  }
  return (
    <ul className="border-t-2 border-foreground">
      {cases.map((caseSummary) => (
        <li key={caseSummary.incident_id}>
          <CaseRow
            caseSummary={caseSummary}
            layout={layout}
            onSelect={(incidentId) => selectListedCase(incidentId, navigate)}
          />
        </li>
      ))}
    </ul>
  );
}
