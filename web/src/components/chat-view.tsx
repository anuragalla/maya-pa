import { useChat } from "@ai-sdk/react";
import type { Message } from "@ai-sdk/ui-utils";
import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import {
  PromptInput,
  PromptInputTextarea,
  PromptInputSubmit,
} from "@/components/ai-elements/prompt-input";
import { Suggestions, Suggestion } from "@/components/ai-elements/suggestion";
import { ChatMessageItem } from "@/components/chat-message-item";
import { NotificationBanner } from "@/components/notification-banner";
import { useNotifications, type Notification } from "@/hooks/use-notifications";
import { useSuggestions } from "@/hooks/use-suggestions";

function getGreeting(name: string): { greeting: string } {
  const hour = new Date().getHours();

  if (hour < 5) return { greeting: `Up late, ${name}?` };
  if (hour < 12) return { greeting: `Good morning, ${name}` };
  if (hour < 17) return { greeting: `Good afternoon, ${name}` };
  if (hour < 21) return { greeting: `Good evening, ${name}` };
  return { greeting: `Winding down, ${name}?` };
}

interface ChatViewProps {
  phone: string;
  userName: string;
}

export function ChatView({ phone, userName }: ChatViewProps) {
  const [historyLoaded, setHistoryLoaded] = useState(false);

  const {
    messages,
    setMessages,
    input,
    setInput,
    status,
    error,
    reload,
    append,
    data,
  } = useChat({
    api: "/api/v1/stream/chat",
    headers: { "X-Phone-Number": phone },
  });

  // Load chat history on mount / phone change. useChat only reads
  // initialMessages once at init — which happens before this async fetch
  // resolves — so we push into the live messages array via setMessages.
  useEffect(() => {
    if (!phone) return;
    setHistoryLoaded(false);
    fetch("/api/v1/stream/history", {
      headers: { "X-Phone-Number": phone },
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.messages?.length) {
          const mapped: Message[] = data.messages.map((m: any) => ({
            id: m.id,
            role: m.role === "model" ? "assistant" : m.role,
            content: typeof m.content === "string" ? m.content : JSON.stringify(m.content),
            createdAt: m.createdAt ? new Date(m.createdAt) : undefined,
          }));
          setMessages(mapped);
        } else {
          setMessages([]);
        }
      })
      .catch(() => {})
      .finally(() => setHistoryLoaded(true));
  }, [phone, setMessages]);

  const injectReminderMessage = useCallback((n: Notification) => {
    if (!n.message_id || !n.body) return;
    setMessages((prev) => {
      if (prev.some((m) => m.id === n.message_id)) return prev;
      return [
        ...prev,
        {
          id: n.message_id!,
          role: "assistant" as const,
          content: n.body,
          createdAt: new Date(),
        },
      ];
    });
  }, [setMessages]);

  const { notifications, dismiss } = useNotifications(phone, injectReminderMessage);
  const { greeting } = useMemo(() => getGreeting(userName), [userName]);

  const suggestions = useSuggestions(data);

  const isStreaming = status === "streaming" || status === "submitted";
  const isEmpty = historyLoaded && messages.length === 0;

  const handleSuggestion = (text: string) => {
    append({ role: "user", content: text });
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-background">
      <Conversation className="flex-1">
        <ConversationContent className="mx-auto max-w-[640px] gap-5 px-4 py-6 sm:px-6">
          {isEmpty && (
            <div className="flex flex-col items-start gap-1 py-8">
              <h2 className="text-xl font-semibold text-foreground">
                {greeting}
              </h2>
              <p className="text-sm text-muted-foreground">
                What would you like to know?
              </p>
            </div>
          )}

          <AnimatePresence initial={false}>
            {messages.map((message: any, idx: number) => (
              <motion.div
                key={message.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.2, ease: "easeOut" }}
              >
                <ChatMessageItem
                  message={message}
                  isStreaming={isStreaming && idx === messages.length - 1}
                />
              </motion.div>
            ))}
          </AnimatePresence>

          {error && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="rounded-2xl border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-primary"
            >
              Something went wrong.{" "}
              <button onClick={() => reload()} className="cursor-pointer underline">
                Retry
              </button>
            </motion.div>
          )}
        </ConversationContent>
        <ConversationScrollButton />
      </Conversation>

      {/* Notifications */}
      <AnimatePresence>
        {notifications.map((n, i) => (
          <motion.div
            key={`notif-${i}`}
            initial={{ opacity: 0, y: -16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -16 }}
            transition={{ duration: 0.4, type: "spring", bounce: 0.3 }}
            className="px-4 py-2"
          >
            <NotificationBanner
              title={n.title}
              body={n.body}
              onDismiss={() => dismiss(i)}
            />
          </motion.div>
        ))}
      </AnimatePresence>

      {/* Suggestions — shown after each assistant response */}
      {!isStreaming && suggestions.length > 0 && (
        <div className="px-4 pb-3">
          <div className="mx-auto max-w-[640px]">
            <Suggestions>
              {suggestions.map((s) => (
                <Suggestion key={s} suggestion={s} onClick={handleSuggestion} />
              ))}
            </Suggestions>
          </div>
        </div>
      )}

      {/* Input */}
      <div className="border-t border-border px-4 pb-4 pt-3">
        <div className="mx-auto max-w-[640px]">
          <PromptInput
            onSubmit={(msg) => {
              append({ role: "user", content: msg.text });
              setInput("");
            }}
          >
            <PromptInputTextarea
              placeholder="Ask anything"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={isStreaming}
            />
            <PromptInputSubmit
              status={isStreaming ? "streaming" : error ? "error" : "ready"}
              disabled={isStreaming || !input.trim()}
            />
          </PromptInput>
        </div>
      </div>
    </div>
  );
}
