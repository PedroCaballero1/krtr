import { apiFetch } from "@/api/client";
import type { Language } from "@/i18n/languages";

/** The `POST /api/chat/messages` response contract (§3.4). */
export interface ChatMessageResponse {
  incident_id: string;
  reply: string;
  responded_at: string;
}

export const MAX_MESSAGE_LENGTH = 2000;
const REQUEST_TIMEOUT_MS = 30_000;

/**
 * Sends a text message for a case and returns the assistant's reply.
 *
 * Exists as the one place that calls `POST /api/chat/messages`, with the
 * 30-second request timeout the chat view (task 5.8) needs to surface as
 * its own error state.
 *
 * @param incidentId - The case this message belongs to.
 * @param text - The message text (1–2000 characters).
 * @param language - The interface's current language.
 * @returns The backend's reply and when it responded.
 */
export async function sendChatMessage(
  incidentId: string,
  text: string,
  language: Language,
): Promise<ChatMessageResponse> {
  // TEMP DEMO MOCK — revert before continuing real work.
  await new Promise((resolve) => setTimeout(resolve, 900));
  return {
    incident_id: incidentId,
    reply:
      language === "es"
        ? `Gracias por tu mensaje: "${text}". Un asesor revisará tu caso pronto.`
        : `Obrigado pela sua mensagem: "${text}". Um consultor analisará seu caso em breve.`,
    responded_at: new Date().toISOString(),
  };
  // eslint-disable-next-line no-unreachable
  const controller = new AbortController();
  // A plain setTimeout (not AbortSignal.timeout) so the timeout is driven
  // by the same timer primitive tests fake with vi.useFakeTimers().
  const timeoutId = setTimeout(() => {
    controller.abort(new DOMException("Chat request timed out", "TimeoutError"));
  }, REQUEST_TIMEOUT_MS);
  try {
    const response = await apiFetch("/api/chat/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ incident_id: incidentId, text, language }),
      signal: controller.signal,
    });
    return (await response.json()) as ChatMessageResponse;
  } finally {
    clearTimeout(timeoutId);
  }
}
