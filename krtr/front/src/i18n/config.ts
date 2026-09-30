import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { DEFAULT_LANGUAGE, Language } from "@/i18n/languages";

/**
 * Minimal i18next setup: the base library wiring for task 5.1.
 *
 * Real translations (`es.json`, `pt-BR.json`), the language selector and
 * the localStorage-persisted preference (D14) are added in task 5.2 — this
 * only proves the app renders through i18next from the start, so no screen
 * has to be retrofitted with translation keys later.
 */
void i18n.use(initReactI18next).init({
  resources: {
    [Language.Spanish]: { translation: { app_name: "krtr" } },
    [Language.Portuguese]: { translation: { app_name: "krtr" } },
  },
  lng: DEFAULT_LANGUAGE,
  fallbackLng: DEFAULT_LANGUAGE,
  interpolation: { escapeValue: false },
});

export default i18n;
