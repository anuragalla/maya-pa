import { useChat } from "@ai-sdk/react";
import type { Message } from "@ai-sdk/ui-utils";
import { AnimatePresence, motion } from "framer-motion";
import { nanoid } from "nanoid";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import { Suggestions, Suggestion } from "@/components/ai-elements/suggestion";
import { ChatComposer } from "@/components/chat-composer";
import { ChatMessageItem } from "@/components/chat-message-item";
import { DocPreviewPane } from "@/components/documents/doc-preview-pane";
import { NotificationBanner } from "@/components/notification-banner";
import { Button } from "@/components/ui/button";
import { useDocPane } from "@/hooks/use-doc-pane";
import { useDocUpload } from "@/hooks/use-doc-upload";
import { useNotifications, type Notification } from "@/hooks/use-notifications";
import { useSuggestions } from "@/hooks/use-suggestions";
import type { MessageDocAttachment } from "@/lib/documents";
import { cn } from "@/lib/utils";

type Live150Message = Message & { documents?: MessageDocAttachment[] };

interface RawHistoryMessage {
  id: string;
  role: "user" | "model" | "assistant";
  content: string | Record<string, unknown>;
  createdAt?: string;
  documents?: MessageDocAttachment[];
}

interface HistoryResponse {
  messages?: RawHistoryMessage[];
}

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
      .then((data: HistoryResponse) => {
        if (data.messages?.length) {
          const mapped: Live150Message[] = data.messages.map((m) => ({
            id: m.id,
            role: m.role === "model" ? "assistant" : m.role,
            content:
              typeof m.content === "string" ? m.content : JSON.stringify(m.content),
            createdAt: m.createdAt ? new Date(m.createdAt) : undefined,
            documents: Array.isArray(m.documents) ? m.documents : undefined,
          }));
          setMessages(mapped as Message[]);
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
  const pane = useDocPane();
  const { upload } = useDocUpload();

  const isStreaming = status === "streaming" || status === "submitted";
  const isEmpty = historyLoaded && messages.length === 0;

  const handleSuggestion = (text: string) => {
    append({ role: "user", content: text });
  };

  const handleSubmit = useCallback(
    async (text: string, files: File[]) => {
      const trimmed = text.trim();
      if (!trimmed && files.length === 0) return;

      const uploaded: MessageDocAttachment[] = [];
      for (const f of files) {
        try {
          const res = await upload(f, phone);
          uploaded.push({
            document_id: res.document_id,
            original_filename: f.name,
            doc_type: "other",
            status: res.status,
          });
        } catch (err) {
          console.error("[chat-view] upload failed", err);
          toast.error(`Upload failed for ${f.name}`);
          return;
        }
      }

      // Optimistic inject so the user sees the bubble + cards instantly,
      // then send a payload-only request that carries the doc IDs but no
      // duplicate echo from useChat.
      if (uploaded.length > 0) {
        const id = nanoid();
        const msg: Live150Message = {
          id,
          role: "user",
          content: trimmed,
          createdAt: new Date(),
          documents: uploaded,
        };
        setMessages((prev) => [...prev, msg as Message]);
        await append(
          { role: "user", content: trimmed || "(attached document)" },
          {
            body: { documents: uploaded.map((d) => d.document_id) },
            allowEmptySubmit: true,
          } as Parameters<typeof append>[1],
        );
      } else {
        await append({ role: "user", content: trimmed });
      }
      setInput("");
    },
    [append, phone, setInput, setMessages, upload],
  );

  return (
    <div className="flex min-h-0 flex-1 bg-background">
      <div
        className={cn(
          "flex min-h-0 flex-col transition-[width] duration-200",
          pane.open ? "w-0 overflow-hidden lg:w-1/2" : "w-full",
        )}
      >
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
                  phone={phone}
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
              <Button variant="link" size="sm" onClick={() => reload()}>
                Retry
              </Button>
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
          <ChatComposer
            value={input}
            onChange={setInput}
            onSubmit={handleSubmit}
            disabled={isStreaming}
            status={isStreaming ? "streaming" : error ? "error" : "ready"}
          />
        </div>
      </div>
      </div>
      <AnimatePresence>
        {pane.open && (
          <motion.aside
            key="doc-pane"
            initial={{ x: "100%", opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: "100%", opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.32, 0.72, 0, 1] }}
            className="w-full border-l border-border bg-card lg:w-1/2"
          >
            <DocPreviewPane phone={phone} />
          </motion.aside>
        )}
      </AnimatePresence>
    </div>
  );
}
