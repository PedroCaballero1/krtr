import type { JSX, KeyboardEvent, RefObject } from "react";
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Mic, Send } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { MAX_MESSAGE_LENGTH, sendChatMessage } from "@/api/chat";
import { ApiError } from "@/api/client";
import { EventName } from "@/api/event-names";
import { trackEvent } from "@/api/events";
import { Button } from "@/components/ui/button";
import { LabeledValue } from "@/components/ui/labeled-value";
import { Notice } from "@/components/ui/notice";
import { Textarea } from "@/components/ui/textarea";
import { VoiceRecorder } from "@/components/voice-recorder";
import i18n from "@/i18n/config";
import { resolveLanguage } from "@/i18n/languages";
import { cn } from "cn";
import { formatClockTime } from "@/lib/format";
import { AppPath } from "@/lib/routes";

const TYPING_INDICATOR_DELAY_MS = 2000;

const TYPING_DOT_COUNT = 3;

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  sentAt: Date;
  isVoice: boolean;
}

interface ChatSendHandlers {
  appendExchange: (userText: string, reply: string, isVoice?: boolean) => void;
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
  void trackEvent(EventName.ChatMessageSent, { incident_id: incidentId });
  const startedAt = Date.now();
  try {
    const response = await sendChatMessage(incidentId, trimmedText, resolveLanguage(i18n.language));
    handlers.appendExchange(trimmedText, response.reply);
    handlers.clearInput();
    void trackEvent(EventName.ChatResponseReceived, {
      incident_id: incidentId,
      latency_ms: Date.now() - startedAt,
    });
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
    const timeout = setTimeout(() => {
      setShowTyping(true);
      void trackEvent(EventName.TypingIndicatorShown);
    }, TYPING_INDICATOR_DELAY_MS);
    return () => {
      clearTimeout(timeout);
      setShowTyping(false);
    };
  }, [isSending]);
  return showTyping;
}

/** Builds one message stamped with the current time. */
function buildMessage(role: ChatMessage["role"], text: string, isVoice: boolean): ChatMessage {
  return { id: crypto.randomUUID(), role, text, sentAt: new Date(), isVoice };
}

/**
 * Holds the conversation shown on screen and appends each user/assistant exchange.
 *
 * @returns The messages so far, and the function that appends one exchange.
 */
function useChatMessages(): {
  messages: ChatMessage[];
  appendExchange: ChatSendHandlers["appendExchange"];
} {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const appendExchange = (userText: string, reply: string, isVoice = false): void =>
    setMessages((previous) => [
      ...previous,
      buildMessage("user", userText, isVoice),
      buildMessage("assistant", reply, false),
    ]);
  return { messages, appendExchange };
}

/** The bar above the conversation: back to the case selection, and the case id. */
function ChatHeader({ incidentId }: { incidentId: string }): JSX.Element {
  const { t } = useTranslation();
  const navigate = useNavigate();
  return (
    <section className="flex flex-wrap items-center gap-6 border-b-2 px-4 py-4 md:px-8">
      <Button variant="ghost" onClick={() => navigate(AppPath.Support)}>
        <ArrowLeft aria-hidden />
        {t("chat_back_to_cases")}
      </Button>
      <LabeledValue label={t("chat_case_label")}>
        <span className="text-lg">{incidentId}</span>
      </LabeledValue>
    </section>
  );
}

/** One message: the customer's on the right in ink, krtr's on the left under a red rule. */
function MessageBubble({ message }: { message: ChatMessage }): JSX.Element {
  const { t, i18n: i18nInstance } = useTranslation();
  const isUser = message.role === "user";
  return (
    <li
      className={cn(
        "flex max-w-[min(560px,85%)] flex-col gap-1",
        isUser ? "items-end self-end" : "self-start",
      )}
    >
      {!isUser && (
        <span className="text-[11px] font-bold tracking-[0.08em] text-brand-700 uppercase">
          {t("app_name")}
        </span>
      )}
      <div
        className={cn(
          "flex items-center gap-2 px-4 py-3 text-[15px] leading-normal whitespace-pre-wrap",
          isUser ? "bg-foreground text-background" : "border-t-2 border-primary bg-surface",
        )}
      >
        {message.isVoice && <Mic aria-hidden className="size-4 shrink-0" />}
        <span>{message.text}</span>
      </div>
      <span className="text-[11px] text-neutral-700">
        {formatClockTime(message.sentAt, i18nInstance.language)}
      </span>
    </li>
  );
}

/** "krtr está escribiendo…" with three pulsing red squares. */
function TypingIndicator(): JSX.Element {
  const { t } = useTranslation();
  return (
    <li className="flex items-center gap-2 self-start text-[13px] text-neutral-700">
      <span aria-hidden className="inline-flex gap-1">
        {Array.from({ length: TYPING_DOT_COUNT }, (_, index) => (
          <span
            key={index}
            className="inline-block size-2 animate-typing-dot bg-primary [&:nth-child(2)]:[animation-delay:0.2s] [&:nth-child(3)]:[animation-delay:0.4s]"
          />
        ))}
      </span>
      <span>{t("chat_typing_indicator")}</span>
    </li>
  );
}

/** Keeps the newest message in view whenever the conversation grows. */
function useScrollToEnd(dependency: unknown): RefObject<HTMLLIElement | null> {
  const endRef = useRef<HTMLLIElement | null>(null);
  useEffect(() => {
    // jsdom (tests) doesn't implement scrollIntoView.
    endRef.current?.scrollIntoView?.({ block: "end" });
  }, [dependency]);
  return endRef;
}

/** The scrollable conversation, with the typing indicator as its last row. */
function MessageList({
  messages,
  showTyping,
}: {
  messages: ChatMessage[];
  showTyping: boolean;
}): JSX.Element {
  const { t } = useTranslation();
  const endRef = useScrollToEnd(`${messages.length}-${showTyping}`);
  return (
    <ul
      aria-label={t("chat_messages_label")}
      className="flex min-h-80 flex-1 flex-col gap-4 overflow-y-auto p-4 md:p-8"
    >
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      {showTyping && <TypingIndicator />}
      <li ref={endRef} aria-hidden />
    </ul>
  );
}

interface ChatComposerProps {
  incidentId: string;
  text: string;
  setText: (text: string) => void;
  isSending: boolean;
  handlers: ChatSendHandlers;
}

/**
 * The text row: a borderless textarea (Enter sends, Shift+Enter newline),
 * the character counter, the voice button and Enviar (disabled while sending).
 */
function ComposerRow({
  recordButton,
  ...props
}: ChatComposerProps & { recordButton: JSX.Element }): JSX.Element {
  const { t } = useTranslation();
  const { incidentId, text, setText, isSending, handlers } = props;
  return (
    <div className="grid md:grid-cols-[minmax(0,1fr)_auto]">
      <Textarea
        value={text}
        rows={2}
        maxLength={MAX_MESSAGE_LENGTH}
        placeholder={t("chat_placeholder")}
        className="min-h-0 resize-none border-0 bg-transparent px-4 py-4 focus-visible:bg-surface/60 md:px-8"
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => handleComposerKeyDown(event, incidentId, text, handlers)}
      />
      <div className="flex items-center justify-end gap-2 px-4 pb-3 md:py-3 md:pr-8 md:pl-4">
        <span className="min-w-18 text-right text-xs text-neutral-700 tabular-nums">
          {text.length} / {MAX_MESSAGE_LENGTH}
        </span>
        {recordButton}
        <Button
          size="lg"
          className="h-12 min-w-30 justify-start"
          disabled={isSending || !text.trim()}
          onClick={() => void sendChatText(incidentId, text, handlers)}
        >
          <Send aria-hidden className="size-[18px]" />
          {t("chat_send")}
        </Button>
      </div>
    </div>
  );
}

/** The composer area: the text row, swapped for the recording bar while recording a voice note. */
function ChatComposer(props: ChatComposerProps): JSX.Element {
  const { incidentId, isSending, handlers } = props;
  return (
    <section className="border-t-2 border-foreground bg-background">
      <VoiceRecorder
        incidentId={incidentId}
        disabled={isSending}
        onSent={(userText, reply) => handlers.appendExchange(userText, reply, true)}
        onError={handlers.setErrorMessage}
        renderIdle={(recordButton) => <ComposerRow {...props} recordButton={recordButton} />}
      />
    </section>
  );
}

/**
 * The chat screen (`/app/chat/:incidentId`, G7/G9): message list, composer,
 * the "escribiendo…" indicator, and error handling (generic, 429, timeout).
 */
export function ChatPage(): JSX.Element {
  const { incidentId = "" } = useParams<{ incidentId: string }>();
  const { messages, appendExchange } = useChatMessages();
  const [text, setText] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const showTyping = useTypingIndicator(isSending);

  const handlers: ChatSendHandlers = {
    appendExchange,
    setIsSending,
    setErrorMessage,
    clearInput: () => setText(""),
  };

  return (
    <main className="flex min-h-0 flex-1 flex-col">
      <ChatHeader incidentId={incidentId} />
      <MessageList messages={messages} showTyping={showTyping} />
      {errorMessage && (
        <Notice role="alert" className="mx-4 mb-4 md:mx-8">
          {errorMessage}
        </Notice>
      )}
      <ChatComposer
        incidentId={incidentId}
        text={text}
        setText={setText}
        isSending={isSending}
        handlers={handlers}
      />
    </main>
  );
}
