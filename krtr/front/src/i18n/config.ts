import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { DEFAULT_LANGUAGE, Language } from "@/i18n/languages";
import es from "@/i18n/locales/es.json";
import ptBR from "@/i18n/locales/pt-BR.json";
import { readStoredLanguage } from "@/i18n/storage";

/**
 * i18next setup: ES and PT translations, defaulting to the stored
 * preference or, absent one, to Spanish (D14).
 */
void i18n.use(initReactI18next).init({
  resources: {
    [Language.Spanish]: { translation: es },
    [Language.Portuguese]: { translation: ptBR },
  },
  lng: readStoredLanguage() ?? DEFAULT_LANGUAGE,
  fallbackLng: DEFAULT_LANGUAGE,
  interpolation: { escapeValue: false },
});

export default i18n;
