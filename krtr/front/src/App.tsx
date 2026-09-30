import type { JSX } from "react";
import { useTranslation } from "react-i18next";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "@/i18n/config";

/**
 * Placeholder landing screen.
 *
 * Exists only to prove the routing/i18n/Tailwind stack renders end to end
 * for task 5.1; task 5.4 replaces this with the real landing/login page.
 */
function LandingPlaceholder(): JSX.Element {
  const { t } = useTranslation();
  return (
    <main className="flex min-h-svh items-center justify-center">
      <h1 className="text-2xl font-semibold text-foreground">{t("app_name")}</h1>
    </main>
  );
}

/**
 * Root application component: wires up client-side routing.
 *
 * Exists as the single place that maps URL paths to screens; each screen
 * itself lives in its own component (added by later tasks under 5.x).
 */
function App(): JSX.Element {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPlaceholder />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
