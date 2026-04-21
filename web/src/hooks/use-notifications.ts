import { useCallback, useEffect, useRef, useState } from "react";

import { readSseFrames } from "@/lib/sse";

export interface Notification {
  type: string;
  title: string;
  body: string;
  reminder_id?: string;
  message_id?: string;
  user_id?: string;
}

/**
 * Live reminder feed. One-shot catchup fetch on mount (for reminders that
 * fired while the tab was closed), then an SSE stream for real-time delivery.
 */
export function useNotifications(
  phone: string,
  onInjectMessage?: (n: Notification) => void,
) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const onInjectRef = useRef(onInjectMessage);
  onInjectRef.current = onInjectMessage;
  const dismissedRef = useRef<Set<string>>(new Set());
  const seenRef = useRef<Set<string>>(new Set());

  const ingestOne = useCallback((n: Notification) => {
    if (!n.message_id || dismissedRef.current.has(n.message_id)) return;
    if (seenRef.current.has(n.message_id)) return;
    seenRef.current.add(n.message_id);
    setNotifications((prev) => [...prev, n]);
    if (n.body) onInjectRef.current?.(n);
  }, []);

  const dismiss = useCallback((index: number) => {
    setNotifications((prev) => {
      const n = prev[index];
      if (n?.message_id) dismissedRef.current.add(n.message_id);
      return prev.filter((_, i) => i !== index);
    });
  }, []);

  useEffect(() => {
    setNotifications([]);
    dismissedRef.current = new Set();
    seenRef.current = new Set();
  }, [phone]);

  useEffect(() => {
    if (!phone) return;
    const controller = new AbortController();

    const run = async () => {
      try {
        const res = await fetch("/api/v1/notifications/catchup", {
          headers: { "X-Phone-Number": phone },
          signal: controller.signal,
        });
        if (res.ok) {
          const data = (await res.json()) as { notifications?: Notification[] };
          for (const n of data.notifications ?? []) ingestOne(n);
        }
      } catch {
        // Ignore — SSE will still connect.
      }

      try {
        const res = await fetch("/api/v1/notifications/events", {
          headers: { "X-Phone-Number": phone, Accept: "text/event-stream" },
          signal: controller.signal,
        });
        for await (const frame of readSseFrames(res, controller.signal)) {
          if (frame.event !== "notification") continue;
          try {
            ingestOne(JSON.parse(frame.data) as Notification);
          } catch {
            // drop malformed frame
          }
        }
      } catch {
        // Aborted or transport error — component unmount or user switch.
      }
    };

    void run();
    return () => controller.abort();
  }, [phone, ingestOne]);

  return { notifications, dismiss };
}
