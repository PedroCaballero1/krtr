import type { JSX } from "react";
import { ArrowRight, LifeBuoy } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { OpenCaseList } from "@/components/open-case-list";
import { useOpenCases } from "@/hooks/use-open-cases";
import { CaseListLayout } from "@/lib/case-list-layout";
import { Kicker } from "@/components/ui/kicker";
import { useShellSession } from "@/hooks/use-shell-session";
import { goToSupport } from "@/lib/support";

/** The greeting block: kicker, "Hola, <customer number>" and the intro text. */
function HomeGreeting(): JSX.Element {
  const { t } = useTranslation();
  const session = useShellSession();
  return (
    <section className="flex flex-col gap-4 border-b-2 p-4 pt-10 md:border-r-2 md:p-8 md:pt-14">
      <Kicker>{t("home_kicker")}</Kicker>
      <h1 className="m-0 text-[clamp(40px,5vw,64px)] leading-none tracking-[-0.03em]">
        {t("home_greeting", { customerId: session?.customer_id ?? "" })}
      </h1>
      <p className="m-0 max-w-[420px] text-[17px] leading-normal">{t("home_body")}</p>
    </section>
  );
}

/** The large red "Ir a soporte" tile, the home screen's main call to action. */
function SupportTile(): JSX.Element {
  const { t } = useTranslation();
  const navigate = useNavigate();
  return (
    <button
      type="button"
      className="flex min-h-80 cursor-pointer flex-col justify-between gap-8 border-b-2 bg-primary p-4 pt-10 text-left text-primary-foreground hover:bg-brand-600 active:bg-brand-700 md:p-8 md:pt-14"
      onClick={() => goToSupport(navigate)}
    >
      <LifeBuoy aria-hidden className="size-12" strokeWidth={1.75} />
      <span className="flex items-end justify-between gap-4">
        <span className="font-heading text-[clamp(36px,4.5vw,56px)] leading-none font-extrabold tracking-[-0.03em]">
          {t("home_go_support")}
        </span>
        <ArrowRight aria-hidden className="size-10 shrink-0" />
      </span>
    </button>
  );
}

/** The "Casos abiertos" section: heading with a count tag, then the list. */
function HomeOpenCases(): JSX.Element {
  const { t } = useTranslation();
  const cases = useOpenCases();
  return (
    <section className="flex flex-col gap-4 p-4 md:col-span-2 md:p-8">
      <div className="flex items-baseline gap-3">
        <h2 className="m-0 text-2xl">{t("support_open_cases_heading")}</h2>
        {cases && (
          <span className="bg-brand-100 px-2.5 py-0.5 text-[11px] font-bold text-brand-800">
            {cases.length}
          </span>
        )}
      </div>
      {cases && <OpenCaseList cases={cases} layout={CaseListLayout.Row} />}
    </section>
  );
}

/**
 * The authenticated home screen (`/app`, task 5.5): a greeting with the
 * customer's number, the "Ir a soporte" tile and the open cases.
 *
 * Exists as the landing point right after login; the header, Cerrar sesión
 * and the session timeouts come from `AppShell`, which wraps this screen.
 */
export function HomePage(): JSX.Element {
  return (
    <main className="grid flex-1 content-start md:grid-cols-2">
      <HomeGreeting />
      <SupportTile />
      <HomeOpenCases />
    </main>
  );
}
