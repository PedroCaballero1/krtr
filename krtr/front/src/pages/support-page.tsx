import type { FormEvent, JSX } from "react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { createCase, listOpenCases, resumeCase, type CaseSummary } from "@/api/cases";
import { ApiError } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type SupportMode = "choice" | "existing";

const MAX_CASE_ID_LENGTH = 64;

/** Builds the chat route for a confirmed incident_id (task 5.8 implements it). */
function buildChatPath(incidentId: string): string {
  return `/app/chat/${encodeURIComponent(incidentId)}`;
}

/** Creates a new case and navigates to its chat, for "Caso nuevo". */
async function startNewCase(navigate: (path: string) => void): Promise<void> {
  const { incident_id } = await createCase();
  navigate(buildChatPath(incident_id));
}

/** Loads the customer's open cases for the "Caso existente" list. */
async function loadOpenCases(setCases: (cases: CaseSummary[]) => void): Promise<void> {
  try {
    setCases(await listOpenCases());
  } catch {
    setCases([]);
  }
}

/**
 * Resumes a case by its typed id, per §3.4: exact match on incident_id +
 * the session's customer_id, with 404 for both "not found" and "someone
 * else's case" (IDOR protection) — surfaced here as "Caso no encontrado".
 */
async function submitCaseId(
  rawValue: string,
  navigate: (path: string) => void,
  setNotFound: (notFound: boolean) => void,
): Promise<void> {
  const trimmedValue = rawValue.trim().slice(0, MAX_CASE_ID_LENGTH);
  setNotFound(false);
  try {
    const { incident_id } = await resumeCase(trimmedValue);
    navigate(buildChatPath(incident_id));
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      setNotFound(true);
      return;
    }
    throw error;
  }
}

interface ModeChoiceProps {
  onSelectNew: () => void;
  onSelectExisting: () => void;
}

/** The initial choice: "Caso nuevo" or "Caso existente" (§3.2). */
function ModeChoice({ onSelectNew, onSelectExisting }: ModeChoiceProps): JSX.Element {
  const { t } = useTranslation();
  return (
    <div className="flex gap-4">
      <Button type="button" onClick={onSelectNew}>
        {t("support_new_case")}
      </Button>
      <Button type="button" variant="outline" onClick={onSelectExisting}>
        {t("support_existing_case")}
      </Button>
    </div>
  );
}

interface CaseListProps {
  cases: CaseSummary[];
  onSelect: (incidentId: string) => void;
}

/** The list of open cases (ID, date, summary), each clickable to resume it directly. */
function CaseList({ cases, onSelect }: CaseListProps): JSX.Element {
  const { t } = useTranslation();
  if (cases.length === 0) {
    return <p className="text-muted-foreground">{t("support_no_open_cases")}</p>;
  }
  return (
    <ul className="flex flex-col gap-2">
      {cases.map((caseSummary) => (
        <li key={caseSummary.incident_id}>
          <button
            type="button"
            className="w-full rounded border p-2 text-left hover:bg-accent"
            onClick={() => onSelect(caseSummary.incident_id)}
          >
            <span className="block font-medium">{caseSummary.incident_id}</span>
            <span className="block text-sm text-muted-foreground">
              {new Date(caseSummary.opened_at).toLocaleDateString()} — {caseSummary.summary}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

interface CaseIdFormProps {
  navigate: (path: string) => void;
}

/** The free-text incident_id field, verified server-side via resumeCase. */
function CaseIdForm({ navigate }: CaseIdFormProps): JSX.Element {
  const { t } = useTranslation();
  const [value, setValue] = useState("");
  const [notFound, setNotFound] = useState(false);

  return (
    <form
      className="flex flex-col gap-2"
      onSubmit={(event: FormEvent) => {
        event.preventDefault();
        void submitCaseId(value, navigate, setNotFound);
      }}
    >
      <label htmlFor="case-id" className="text-sm font-medium">
        {t("support_case_id_label")}
      </label>
      <Input
        id="case-id"
        value={value}
        maxLength={MAX_CASE_ID_LENGTH}
        onChange={(event) => setValue(event.target.value)}
      />
      <Button type="submit">{t("support_case_id_submit")}</Button>
      {notFound && (
        <p role="alert" className="text-sm text-destructive">
          {t("support_case_not_found")}
        </p>
      )}
    </form>
  );
}

/** "Caso existente": the open-cases list plus the free-text id field. */
function ExistingCaseChooser({ navigate }: CaseIdFormProps): JSX.Element {
  const { t } = useTranslation();
  const [cases, setCases] = useState<CaseSummary[]>([]);

  useEffect(() => {
    void loadOpenCases(setCases);
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="mb-2 font-medium">{t("support_open_cases_heading")}</h2>
        <CaseList cases={cases} onSelect={(incidentId) => navigate(buildChatPath(incidentId))} />
      </div>
      <CaseIdForm navigate={navigate} />
    </div>
  );
}

/**
 * Case selection (`/app/support`, §3.2/G18): "Caso nuevo" or "Caso
 * existente" (list of open cases, or a typed incident_id).
 *
 * Exists as the screen `HomePage`'s Soporte button navigates to; every
 * path ends by navigating to `/app/chat/:incidentId` (task 5.8).
 */
export function SupportPage(): JSX.Element {
  const [mode, setMode] = useState<SupportMode>("choice");
  const navigate = useNavigate();

  if (mode === "existing") {
    return <ExistingCaseChooser navigate={navigate} />;
  }
  return (
    <ModeChoice
      onSelectNew={() => void startNewCase(navigate)}
      onSelectExisting={() => setMode("existing")}
    />
  );
}
