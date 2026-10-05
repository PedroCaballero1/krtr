import type { ChatMessageResponse } from "@/api/chat";
import { apiFetch } from "@/api/client";
import type { Language } from "@/i18n/languages";

/**
 * Sends a recorded voice note for a case and returns the assistant's reply.
 *
 * Exists as the one place that calls `POST /api/chat/voice` (multipart,
 * §3.4); the response shape is the same as text chat's.
 *
 * @param incidentId - The case this voice note belongs to.
 * @param audio - The recorded audio (WebM/Opus or MP4/AAC, ≤60s, ≤2MB).
 * @param language - The interface's current language.
 * @returns The backend's reply and when it responded.
 */
export async function sendVoiceMessage(
  incidentId: string,
  audio: Blob,
  language: Language,
): Promise<ChatMessageResponse> {
  const formData = new FormData();
  formData.append("audio", audio);
  formData.append("incident_id", incidentId);
  formData.append("language", language);
  const response = await apiFetch("/api/chat/voice", { method: "POST", body: formData });
  return (await response.json()) as ChatMessageResponse;
}
