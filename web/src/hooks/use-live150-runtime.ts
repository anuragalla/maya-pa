import {
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from "@assistant-ui/react";
import { nanoid } from "nanoid";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { MessageDocAttachment } from "@/lib/documents";
import { DeferredUploadAttachmentAdapter } from "@/lib/chat-v2/attachment-adapter";
import { parseDataStream } from "@/lib/chat-v2/stream-parser";

export interface Live150ToolCall {
  id: string;
  name: string;
  args: unknown;
  result?: unknown;
}

export interface Live150Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  toolCalls: Live150ToolCall[];
  documents?: MessageDocAttachment[];
  suggestions?: string[];
  createdAt: Date;
}

interface HistoryMessage {
  id: string;
  role: "user" | "model" | "assistant";
  content: string | Record<string, unknown>;
  createdAt?: string;
  documents?: MessageDocAttachment[];
}

interface UseLive150RuntimeArgs {
  phone: string;
  /** Called after each submission that carries document attachments.
   *  The hook uploads them, then passes the resulting doc IDs to the backend. */
  uploadDoc?: (file: File, phone: string) => Promise<{ document_id: string; status: string }>;
}

const HISTORY_URL = "/api/v1/stream/history";
const CHAT_URL = "/api/v1/stream/chat";

/** ExternalStoreRuntime adapter for our FastAPI + Google ADK backend. */
export function useLive150Runtime({ phone, uploadDoc }: UseLive150RuntimeArgs) {
  const [messages, setMessages] = useState<Live150Message[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // Load history on phone change.
  useEffect(() => {
    if (!phone) return;
    setIsLoading(true);
    let cancelled = false;
    fetch(HISTORY_URL, { headers: { "X-Phone-Number": phone } })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((data: { messages?: HistoryMessage[] }) => {
        if (cancelled) return;
        const mapped: Live150Message[] = (data.messages ?? []).map((m) => ({
          id: m.id,
          role: m.role === "model" ? "assistant" : (m.role as "user" | "assistant"),
          text: typeof m.content === "string" ? m.content : JSON.stringify(m.content),
          toolCalls: [],
          documents: Array.isArray(m.documents) ? m.documents : undefined,
          createdAt: m.createdAt ? new Date(m.createdAt) : new Date(),
        }));
        setMessages(mapped);
      })
      .catch(() => {
        if (!cancelled) setMessages([]);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [phone]);

  const runTurn = useCallback(
    async (userText: string, documentIds: string[], documents: MessageDocAttachment[]) => {
      // Append user message immediately.
      const userId = nanoid();
      const user: Live150Message = {
        id: userId,
        role: "user",
        text: userText,
        toolCalls: [],
        documents: documents.length > 0 ? documents : undefined,
        createdAt: new Date(),
      };
      const assistantId = nanoid();
      const assistant: Live150Message = {
        id: assistantId,
        role: "assistant",
        text: "",
        toolCalls: [],
        createdAt: new Date(),
      };
      setMessages((prev) => [...prev, user, assistant]);
      setIsRunning(true);

      const ac = new AbortController();
      abortRef.current = ac;

      // Build `messages` payload from current state + the new user message.
      // The server only reads the LAST user message, so this is a small payload.
      const payloadMessages = [
        ...messages.map((m) => ({ role: m.role, content: m.text })),
        { role: "user" as const, content: userText },
      ];

      try {
        const res = await fetch(CHAT_URL, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Phone-Number": phone,
          },
          body: JSON.stringify({
            messages: payloadMessages,
            documents: documentIds,
          }),
          signal: ac.signal,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        for await (const evt of parseDataStream(res, ac.signal)) {
          if (evt.type === "text") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, text: m.text + evt.value } : m,
              ),
            );
          } else if (evt.type === "tool-call") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      toolCalls: [
                        ...m.toolCalls,
                        { id: evt.toolCallId, name: evt.toolName, args: evt.args },
                      ],
                    }
                  : m,
              ),
            );
          } else if (evt.type === "tool-result") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      toolCalls: m.toolCalls.map((tc) =>
                        tc.id === evt.toolCallId ? { ...tc, result: evt.result } : tc,
                      ),
                    }
                  : m,
              ),
            );
          } else if (evt.type === "data") {
            const suggestions = evt.items.find(
              (it) =>
                typeof it === "object" &&
                it !== null &&
                (it as { type?: string }).type === "suggestions",
            ) as { type: "suggestions"; items?: string[] } | undefined;
            if (suggestions?.items) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, suggestions: suggestions.items } : m,
                ),
              );
            }
          }
          // step-finish / message-finish: nothing to do; stream end signals completion
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        console.error("[chat-v2] stream error", err);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId && m.text === ""
              ? { ...m, text: "Something went wrong." }
              : m,
          ),
        );
      } finally {
        setIsRunning(false);
        abortRef.current = null;
      }
    },
    [messages, phone],
  );

  const onNew = useCallback(
    async (msg: AppendMessage) => {
      // Extract text from the append message parts.
      const textParts = msg.content.filter(
        (p): p is { type: "text"; text: string } => p.type === "text",
      );
      const text = textParts.map((p) => p.text).join("").trim();

      // Upload staged attachments on submit.
      const documents: MessageDocAttachment[] = [];
      const documentIds: string[] = [];
      if (msg.attachments && uploadDoc) {
        for (const att of msg.attachments) {
          const file = att.file;
          if (!(file instanceof File)) continue;
          try {
            const res = await uploadDoc(file, phone);
            documents.push({
              document_id: res.document_id,
              original_filename: file.name,
              doc_type: "other",
              status: res.status as MessageDocAttachment["status"],
            });
            documentIds.push(res.document_id);
          } catch (err) {
            console.error("[chat-v2] upload failed", file.name, err);
          }
        }
      }

      if (!text && documentIds.length === 0) return;
      await runTurn(text || "(attached document)", documentIds, documents);
    },
    [phone, runTurn, uploadDoc],
  );

  const onCancel = useCallback(async () => {
    abortRef.current?.abort();
  }, []);

  // Convert our local message shape to the ThreadMessageLike the runtime expects.
  // Using `any[]` internally so we can push — the returned value is typed via
  // the ThreadMessageLike return type annotation.
  const convertMessage = useCallback((m: Live150Message): ThreadMessageLike => {
    const parts: unknown[] = [];
    if (m.role === "assistant") {
      for (const tc of m.toolCalls) {
        parts.push({
          type: "tool-call",
          toolCallId: tc.id,
          toolName: tc.name,
          args: (tc.args ?? {}) as Record<string, unknown>,
          result: tc.result,
        });
      }
    }
    if (m.text) {
      parts.push({ type: "text", text: m.text });
    }
    if (parts.length === 0) {
      parts.push({ type: "text", text: "" });
    }
    return {
      id: m.id,
      role: m.role,
      content: parts as ThreadMessageLike["content"],
      createdAt: m.createdAt,
      metadata: {
        custom: {
          documents: m.documents ?? null,
          suggestions: m.suggestions ?? null,
        },
      },
    };
  }, []);

  const attachmentAdapter = useMemo(() => new DeferredUploadAttachmentAdapter(), []);

  // Wrap setMessages so its signature matches the runtime's expected
  // `(messages: readonly T[]) => void` — React's Dispatch allows a functional
  // updater that the runtime type doesn't declare.
  const replaceMessages = useCallback(
    (next: readonly Live150Message[]) => setMessages([...next]),
    [],
  );

  const runtime = useExternalStoreRuntime({
    isRunning,
    isLoading,
    messages,
    setMessages: replaceMessages,
    onNew,
    onCancel,
    convertMessage,
    adapters: {
      attachments: attachmentAdapter,
    },
  });

  // Return the raw messages too so the UI can read suggestions / documents
  // from the last assistant / user message without going through the runtime.
  return { runtime, messages, isRunning, isLoading };
}
