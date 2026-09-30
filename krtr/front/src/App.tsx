import type { JSX } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { ChatPage } from "@/pages/chat-page";
import { HomePage } from "@/pages/home-page";
import { LandingPage } from "@/pages/landing-page";
import { SupportPage } from "@/pages/support-page";
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
        <Route path="/app" element={<HomePage />} />
        <Route path="/app/support" element={<SupportPage />} />
        <Route path="/app/chat/:incidentId" element={<ChatPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
