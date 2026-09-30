import type { FormEvent, JSX } from "react";
import { useId, useState } from "react";
import { ArrowRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { createCase, resumeCase } from "@/api/cases";
import { ApiError } from "@/api/client";
import { EventName } from "@/api/event-names";
import { trackEvent } from "@/api/events";
import { OpenCaseList } from "@/components/open-case-list";
import { useOpenCases } from "@/hooks/use-open-cases";
import { CaseListLayout } from "@/lib/case-list-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Kicker } from "@/components/ui/kicker";
import { Notice } from "@/components/ui/notice";
import { cn } from "cn";
import { buildChatPath } from "@/lib/routes";

/** The two ways into support (§3.2/G18); also the `case_mode_selected` payload. */
const CaseMode = {
  New: "new",
  Existing: "existing",
} as const;

type CaseMode = (typeof CaseMode)[keyof typeof CaseMode];

const MAX_CASE_ID_LENGTH = 64;

/** Records which mode the user picked, per the §3.5 catalog, and shows its panel. */
function selectCaseMode(mode: CaseMode, setMode: (mode: CaseMode) => void): void {
  void trackEvent(EventName.CaseModeSelected, { mode });
  setMode(mode);
}

/** Creates a new case and navigates to its chat, for "Caso nuevo". */
async function startNewCase(navigate: (path: string) => void): Promise<void> {
  const { incident_id } = await createCase();
  void trackEvent(EventName.CaseCreated, { incident_id });
  navigate(buildChatPath(incident_id));
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
    void trackEvent(EventName.CaseResumeSucceeded, { incident_id });
    navigate(buildChatPath(incident_id));
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      setNotFound(true);
      void trackEvent(EventName.CaseResumeFailed);
      return;
    }
    throw error;
  }
}

interface ModeTileProps {
  marker: string;
  title: string;
  description: string;
  isSelected: boolean;
  onSelect: () => void;
  className?: string;
}

/** One of the two big A/B choice tiles; inverted (ink on paper → paper on ink) when selected. */
function ModeTile(props: ModeTileProps): JSX.Element {
  const titleId = useId();
  const descriptionId = useId();
  return (
    <button
      type="button"
      aria-pressed={props.isSelected}
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
      className={cn(
        "flex cursor-pointer flex-col gap-2 px-4 py-6 text-left md:px-8",
        props.isSelected ? "bg-foreground text-background" : "hover:bg-surface",
        props.className,
      )}
      onClick={props.onSelect}
    >
      <span aria-hidden className="text-[13px] font-bold tracking-[0.08em]">
        {props.marker}
      </span>
      <strong id={titleId} className="font-heading text-[28px] font-extrabold tracking-[-0.02em]">
        {props.title}
      </strong>
      <span id={descriptionId} className="text-[15px] leading-snug">
        {props.description}
      </span>
    </button>
  );
}

interface ModeChoiceProps {
  mode: CaseMode | null;
  onSelect: (mode: CaseMode) => void;
}

/** The choice between "Caso nuevo" (A) and "Caso existente" (B). */
function ModeChoice({ mode, onSelect }: ModeChoiceProps): JSX.Element {
  const { t } = useTranslation();
  return (
    <div className="grid border-b-2 md:grid-cols-2">
      <ModeTile
        marker="A"
        title={t("support_new_case")}
        description={t("support_new_case_description")}
        isSelected={mode === CaseMode.New}
        onSelect={() => onSelect(CaseMode.New)}
        className="border-b-2 md:border-r-2 md:border-b-0"
      />
      <ModeTile
        marker="B"
        title={t("support_existing_case")}
        description={t("support_existing_case_description")}
        isSelected={mode === CaseMode.Existing}
        onSelect={() => onSelect(CaseMode.Existing)}
      />
    </div>
  );
}

interface NavigateProps {
  navigate: (path: string) => void;
}

/** "Caso nuevo": explains the new case gets its own ID, then creates it on confirm. */
function NewCasePanel({ navigate }: NavigateProps): JSX.Element {
  const { t } = useTranslation();
  return (
    <section className="flex max-w-[640px] flex-col gap-4 p-4 md:p-8">
      <p className="m-0 text-base leading-normal">{t("support_new_case_explanation")}</p>
      <Button
        size="lg"
        className="min-w-70 justify-between self-start"
        onClick={() => void startNewCase(navigate)}
      >
        {t("support_start_chat")}
        <ArrowRight aria-hidden className="size-[18px]" />
      </Button>
    </section>
  );
}

/** The free-text incident_id field, verified server-side via resumeCase. */
function CaseIdForm({ navigate }: NavigateProps): JSX.Element {
  const { t } = useTranslation();
  const [value, setValue] = useState("");
  const [notFound, setNotFound] = useState(false);

  return (
    <form
      className="flex flex-col gap-3 p-4 md:p-8"
      onSubmit={(event: FormEvent) => {
        event.preventDefault();
        void submitCaseId(value, navigate, setNotFound);
      }}
    >
      <label htmlFor="case-id" className="text-[13px] font-extrabold tracking-[0.08em] uppercase">
        {t("support_case_id_label")}
      </label>
      <div className="flex">
        <Input
          id="case-id"
          value={value}
          maxLength={MAX_CASE_ID_LENGTH}
          className="flex-1 border-r-0"
          onChange={(event) => setValue(event.target.value)}
        />
        <Button type="submit" size="lg" className="px-6">
          {t("support_case_id_submit")}
        </Button>
      </div>
      {notFound && (
        <Notice role="alert" className="font-semibold">
          {t("support_case_not_found")}
        </Notice>
      )}
      <span className="text-[13px] text-neutral-700">{t("support_case_id_hint")}</span>
    </form>
  );
}

/** "Caso existente": the open-cases list beside the free-text id field. */
function ExistingCaseChooser({ navigate }: NavigateProps): JSX.Element {
  const { t } = useTranslation();
  const cases = useOpenCases();

  return (
    <section className="grid md:grid-cols-2">
      <div className="flex flex-col gap-4 border-b-2 p-4 md:border-r-2 md:border-b-0 md:p-8">
        <h2 className="m-0 text-[13px] tracking-[0.08em] uppercase">
          {t("support_open_cases_heading")}
          {cases && ` · ${cases.length}`}
        </h2>
        {cases && <OpenCaseList cases={cases} layout={CaseListLayout.Stacked} />}
      </div>
      <CaseIdForm navigate={navigate} />
    </section>
  );
}

/**
 * Case selection (`/app/support`, §3.2/G18): "Caso nuevo" or "Caso
 * existente" (list of open cases, or a typed incident_id).
 *
 * Exists as the screen the Soporte buttons navigate to; every path ends by
 * navigating to `/app/chat/:incidentId` (task 5.8).
 */
export function SupportPage(): JSX.Element {
  const { t } = useTranslation();
  const [mode, setMode] = useState<CaseMode | null>(null);
  const navigate = useNavigate();

  return (
    <main className="flex flex-1 flex-col">
      <section className="flex flex-col gap-3 border-b-2 p-4 pt-10 md:p-8 md:pt-12">
        <Kicker>{t("support_button")}</Kicker>
        <h1 className="m-0 text-[clamp(36px,4.5vw,56px)] leading-none tracking-[-0.03em]">
          {t("support_title")}
        </h1>
      </section>
      <ModeChoice mode={mode} onSelect={(selected) => selectCaseMode(selected, setMode)} />
      {mode === CaseMode.New && <NewCasePanel navigate={navigate} />}
      {mode === CaseMode.Existing && <ExistingCaseChooser navigate={navigate} />}
    </main>
  );
}
