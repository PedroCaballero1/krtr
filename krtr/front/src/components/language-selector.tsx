import type { i18n as I18nInstance } from "i18next";
import type { JSX } from "react";
import { useTranslation } from "react-i18next";
import { EventName } from "@/api/event-names";
import { trackEvent } from "@/api/events";
import { Button } from "@/components/ui/button";
import { LANGUAGE_LABELS, Language } from "@/i18n/languages";
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
 * persist) lives in exactly one place.
 */
export function LanguageSelector(): JSX.Element {
  const { i18n } = useTranslation();

  return (
    <div role="group" aria-label="Language" className="flex gap-1">
      {Object.values(Language).map((language) => (
        <Button
          key={language}
          type="button"
          variant={i18n.language === language ? "default" : "outline"}
          size="sm"
          aria-pressed={i18n.language === language}
          onClick={() => selectLanguage(i18n, language)}
        >
          {LANGUAGE_LABELS[language]}
        </Button>
      ))}
    </div>
  );
}
