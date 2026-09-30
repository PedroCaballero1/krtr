import type { JSX, KeyboardEvent } from "react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { MAX_MESSAGE_LENGTH, sendChatMessage } from "@/api/chat";
import { ApiError } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import i18n from "@/i18n/config";
import { resolveLanguage } from "@/i18n/languages";

const TYPING_INDICATOR_DELAY_MS = 2000;

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
}

interface ChatSendHandlers {
  appendExchange: (userText: string, reply: string) => void;
  setIsSending: (sending: boolean) => void;
  setErrorMessage: (message: string | null) => void;
  clearInput: () => void;
}

/** Translates a failed send into the message shown to the user. */
function resolveChatErrorMessage(error: unknown): string {
  if (error instanceof DOMException && error.name === "TimeoutError") {
    return i18n.t("chat_error_timeout");
  }
  if (error instanceof ApiError && error.status === 429) {
    return i18n.t("chat_error_rate_limited");
  }
  if (error instanceof ApiError) {
    return error.message;
  }
  return i18n.t("chat_error_generic");
}

/**
 * Sends one chat message and reports the outcome through `handlers`.
 *
 * Exists as the module-level function every send path (Enviar click,
 * Enter key) delegates to, per the frontend rules in CLAUDE.md.
 */
async function sendChatText(
  incidentId: string,
  text: string,
  handlers: ChatSendHandlers,
): Promise<void> {
  const trimmedText = text.trim();
  if (!trimmedText) return;
  handlers.setIsSending(true);
  handlers.setErrorMessage(null);
  try {
    const response = await sendChatMessage(incidentId, trimmedText, resolveLanguage(i18n.language));
    handlers.appendExchange(trimmedText, response.reply);
    handlers.clearInput();
  } catch (error) {
    handlers.setErrorMessage(resolveChatErrorMessage(error));
  } finally {
    handlers.setIsSending(false);
  }
}

/** Enter sends; Shift+Enter inserts a newline (§5.8). */
function handleComposerKeyDown(
  event: KeyboardEvent<HTMLTextAreaElement>,
  incidentId: string,
  text: string,
  handlers: ChatSendHandlers,
): void {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    void sendChatText(incidentId, text, handlers);
  }
}

/**
 * Shows "Escribiendo…" once a request has been pending for 2 seconds.
 *
 * The reset lives in the effect's cleanup (run before the next effect,
 * whenever `isSending` changes, and on unmount), not in the effect body
 * itself — calling setState synchronously in an effect body is a
 * react-hooks lint error, since it schedules an avoidable extra render.
 */
function useTypingIndicator(isSending: boolean): boolean {
  const [showTyping, setShowTyping] = useState(false);
  useEffect(() => {
    if (!isSending) return;
    const timeout = setTimeout(() => setShowTyping(true), TYPING_INDICATOR_DELAY_MS);
    return () => {
      clearTimeout(timeout);
      setShowTyping(false);
    };
  }, [isSending]);
  return showTyping;
}

function MessageList({ messages }: { messages: ChatMessage[] }): JSX.Element {
  const { t } = useTranslation();
  return (
    <ul aria-label={t("chat_messages_label")} className="flex-1 space-y-2 overflow-y-auto p-4">
      {messages.map((message) => (
        <li key={message.id} className={message.role === "user" ? "text-right" : "text-left"}>
          <span className="inline-block rounded-lg bg-muted px-3 py-2">{message.text}</span>
        </li>
      ))}
    </ul>
  );
}

/**
 * The chat text input: a textarea (Enter sends, Shift+Enter newline), a
 * character counter, and the send button (disabled while sending).
 */
function ChatComposer({
  incidentId,
  text,
  setText,
  isSending,
  handlers,
}: {
  incidentId: string;
  text: string;
  setText: (text: string) => void;
  isSending: boolean;
  handlers: ChatSendHandlers;
}): JSX.Element {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-2 border-t p-4">
      <Textarea
        value={text}
        maxLength={MAX_MESSAGE_LENGTH}
        placeholder={t("chat_placeholder")}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => handleComposerKeyDown(event, incidentId, text, handlers)}
      />
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {text.length}/{MAX_MESSAGE_LENGTH}
        </span>
        <Button
          type="button"
          disabled={isSending || !text.trim()}
          onClick={() => void sendChatText(incidentId, text, handlers)}
        >
          {t("chat_send")}
        </Button>
      </div>
    </div>
  );
}

/**
 * The chat screen (`/app/chat/:incidentId`, G7/G9): message list, composer,
 * the "escribiendo…" indicator, and error handling (generic, 429, timeout).
 */
export function ChatPage(): JSX.Element {
  const { incidentId } = useParams<{ incidentId: string }>();
  const { t } = useTranslation();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [text, setText] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const showTyping = useTypingIndicator(isSending);

  const handlers: ChatSendHandlers = {
    appendExchange: (userText, reply) =>
      setMessages((previous) => [
        ...previous,
        { id: crypto.randomUUID(), role: "user", text: userText },
        { id: crypto.randomUUID(), role: "assistant", text: reply },
      ]),
    setIsSending,
    setErrorMessage,
    clearInput: () => setText(""),
  };

  return (
    <div className="flex min-h-svh flex-col">
      <MessageList messages={messages} />
      {showTyping && (
        <p className="px-4 text-sm text-muted-foreground">{t("chat_typing_indicator")}</p>
      )}
      {errorMessage && (
        <p role="alert" className="px-4 text-sm text-destructive">
          {errorMessage}
        </p>
      )}
      <ChatComposer
        incidentId={incidentId ?? ""}
        text={text}
        setText={setText}
        isSending={isSending}
        handlers={handlers}
      />
    </div>
  );
}
