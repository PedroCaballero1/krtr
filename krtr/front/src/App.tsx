import type { JSX } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { LandingPage } from "@/pages/landing-page";
import "@/i18n/config";

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
        <Route path="/" element={<LandingPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
