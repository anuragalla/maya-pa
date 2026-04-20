import { useEffect, useRef, useState, useCallback } from "react";

export interface Notification {
  type: string;
  title: string;
  body: string;
  reminder_id?: string;
  message_id?: string;
  user_id?: string;
}

const POLL_INTERVAL = 5000; // 5 seconds

export function useNotifications(
  phone: string,
  onInjectMessage?: (n: Notification) => void,
) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const onInjectRef = useRef(onInjectMessage);
  onInjectRef.current = onInjectMessage;
  // Tracks message_ids the user has explicitly dismissed so re-polls don't
  // resurrect them (the endpoint is idempotent within its lookback window).
  const dismissedRef = useRef<Set<string>>(new Set());

  const dismiss = useCallback((index: number) => {
    setNotifications((prev) => {
      const n = prev[index];
      if (n?.message_id) dismissedRef.current.add(n.message_id);
      return prev.filter((_, i) => i !== index);
    });
  }, []);

  useEffect(() => {
    if (!phone) return;

    const poll = async () => {
      try {
        const res = await fetch("/api/v1/notifications", {
          headers: { "X-Phone-Number": phone },
        });
        if (!res.ok) return;
        const data = await res.json();
        if (data.notifications?.length > 0) {
          // Dedupe by message_id — the endpoint is idempotent (returns the
          // same rows across polls within the 15-min lookback), so without
          // dedup every poll stacks another banner.
          setNotifications((prev) => {
            const seen = new Set(prev.map((n) => n.message_id).filter(Boolean));
            const fresh = data.notifications.filter(
              (n: Notification) =>
                n.message_id &&
                !seen.has(n.message_id) &&
                !dismissedRef.current.has(n.message_id),
            );
            return fresh.length ? [...prev, ...fresh] : prev;
          });
          // Chat injection already dedupes by message_id inside the callback.
          data.notifications.forEach((n: Notification) => {
            if (n.message_id && n.body && onInjectRef.current) {
              onInjectRef.current(n);
            }
          });
        }
      } catch {
        // Silently ignore poll failures
      }
    };

    poll();
    intervalRef.current = setInterval(poll, POLL_INTERVAL);

    // Chrome throttles setInterval to 1/min in backgrounded tabs, so
    // reminders that fire while the tab is idle can be missed entirely
    // (notification TTL is 5 min server-side). Catch up the moment the
    // tab is foregrounded again.
    const onVisible = () => {
      if (document.visibilityState === "visible") poll();
    };
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onVisible);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onVisible);
    };
  }, [phone]);

  // Clear on user switch
  useEffect(() => {
    setNotifications([]);
    dismissedRef.current = new Set();
  }, [phone]);

  return { notifications, dismiss };
}
