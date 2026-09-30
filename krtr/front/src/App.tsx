import type { JSX } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/app-shell";
import { AppPath } from "@/lib/routes";
import { ChatPage } from "@/pages/chat-page";
import { HomePage } from "@/pages/home-page";
import { LandingPage } from "@/pages/landing-page";
import { SupportPage } from "@/pages/support-page";
import "@/i18n/config";

/**
 * Root application component: wires up client-side routing.
 *
 * Exists as the single place that maps URL paths to screens. Every
 * authenticated screen is nested under `AppShell`, which provides the
 * shared header and the session timeout handling.
 */
function App(): JSX.Element {
  return (
    <BrowserRouter>
      <Routes>
        <Route path={AppPath.Landing} element={<LandingPage />} />
        <Route path={AppPath.Home} element={<AppShell />}>
          <Route index element={<HomePage />} />
          <Route path={AppPath.Support} element={<SupportPage />} />
          <Route path="/app/chat/:incidentId" element={<ChatPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
