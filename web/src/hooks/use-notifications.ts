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

  const dismiss = useCallback((index: number) => {
    setNotifications((prev) => prev.filter((_, i) => i !== index));
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
          setNotifications((prev) => [...prev, ...data.notifications]);
          // Inject reminder messages into chat immediately
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

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [phone]);

  // Clear on user switch
  useEffect(() => {
    setNotifications([]);
  }, [phone]);

  return { notifications, dismiss };
}
