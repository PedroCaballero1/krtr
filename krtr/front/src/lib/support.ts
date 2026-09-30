import type { NavigateFunction } from "react-router-dom";
import { EventName } from "@/api/event-names";
import { trackEvent } from "@/api/events";
import { AppPath } from "@/lib/routes";

/**
 * Records support_clicked and navigates to the case selection screen.
 *
 * Exists as the one action behind every "Soporte" entry point: the header
 * button and the home screen's "Ir a soporte" tile.
 *
 * @param navigate - The router's navigate function.
 * @returns Nothing.
 */
export function goToSupport(navigate: NavigateFunction): void {
  void trackEvent(EventName.SupportClicked);
  navigate(AppPath.Support);
}
