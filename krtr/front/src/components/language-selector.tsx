import type { i18n as I18nInstance } from "i18next";
import type { JSX } from "react";
import { useTranslation } from "react-i18next";
import { EventName } from "@/api/event-names";
import { trackEvent } from "@/api/events";
import { cn } from "cn";
import { LANGUAGE_LABELS, LANGUAGE_SHORT_LABELS, Language } from "@/i18n/languages";
import { storeLanguage } from "@/i18n/storage";

/**
 * Switches the active language and persists the choice (D14).
 *
 * Exists as the module-level handler the selector's buttons delegate to
 * (per the frontend rules in CLAUDE.md, an inline JSX callback must
 * delegate rather than contain the logic itself).
 *
 * @param i18nInstance - The active i18next instance, from `useTranslation`.
 * @param language - The language the user just picked.
 * @returns Nothing.
 */
function selectLanguage(i18nInstance: I18nInstance, language: Language): void {
  void i18nInstance.changeLanguage(language);
  storeLanguage(language);
  void trackEvent(EventName.LanguageChanged, { language });
}

/**
 * Lets the user switch between the supported interface languages (ES/PT).
 *
 * Exists as the one language switcher used on both the landing page (task
 * 5.4) and the authenticated header (task 5.5), so the behavior (change +
 * persist) lives in exactly one place. Rendered as the design's segmented
 * ES | PT control; each button's accessible name is the full language name.
 */
export function LanguageSelector(): JSX.Element {
  const { t, i18n } = useTranslation();

  return (
    <div
      role="group"
      aria-label={t("language_selector_label")}
      className="flex border-2 border-foreground"
    >
      {Object.values(Language).map((language) => (
        <button
          key={language}
          type="button"
          aria-label={LANGUAGE_LABELS[language]}
          aria-pressed={i18n.language === language}
          className={cn(
            "cursor-pointer px-3 py-1.5 text-[13px] font-bold",
            i18n.language === language
              ? "bg-foreground text-background"
              : "bg-transparent text-foreground hover:bg-foreground/7",
          )}
          onClick={() => selectLanguage(i18n, language)}
        >
          {LANGUAGE_SHORT_LABELS[language]}
        </button>
      ))}
    </div>
  );
}
