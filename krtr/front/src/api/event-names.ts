/**
 * Mirrors `krtr/back/security/audit/event_names.py`'s `EventName` catalog.
 *
 * Kept as a separate copy (not shared code) because the frontend and
 * backend are different language runtimes; the backend's `EventName` is
 * still the source of truth — `POST /api/events` validates against it, so
 * a value added here without a matching backend member would 422 at
 * runtime rather than silently succeed.
 */
export const EventName = {
  // Login / session (emitted by the backend; listed for type completeness).
  AuthLoginStarted: "auth_login_started",
  AuthLoginSucceeded: "auth_login_succeeded",
  AuthLoginFailed: "auth_login_failed",
  AuthLogout: "auth_logout",
  SessionCreated: "session_created",
  SessionRevokedByNewLogin: "session_revoked_by_new_login",
  SessionIdleWarningShown: "session_idle_warning_shown",
  SessionAbsoluteWarningShown: "session_absolute_warning_shown",
  SessionExtended: "session_extended",
  SessionExpiredIdle: "session_expired_idle",
  SessionExpiredAbsolute: "session_expired_absolute",

  // Interface.
  PageView: "page_view",
  LanguageChanged: "language_changed",
  SupportClicked: "support_clicked",
  CaseModeSelected: "case_mode_selected",
  CaseListViewed: "case_list_viewed",
  CaseCreated: "case_created",
  CaseResumeSucceeded: "case_resume_succeeded",
  CaseResumeFailed: "case_resume_failed",

  // Chat.
  ChatMessageSent: "chat_message_sent",
  ChatResponseReceived: "chat_response_received",
  TypingIndicatorShown: "typing_indicator_shown",

  // Voice.
  VoiceRecordingStarted: "voice_recording_started",
  VoiceRecordingCancelled: "voice_recording_cancelled",
  VoiceRecordingSent: "voice_recording_sent",
  VoicePermissionDenied: "voice_permission_denied",

  // Security.
  RateLimitExceeded: "rate_limit_exceeded",
  CsrfRejected: "csrf_rejected",
  ClientError: "client_error",
} as const;

export type EventName = (typeof EventName)[keyof typeof EventName];
