import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useMemo } from "react";

import { ChatV2Thread } from "@/components/chat-v2/chat-v2-thread";
import { DocPreviewPane } from "@/components/documents/doc-preview-pane";
import { useDocPane } from "@/hooks/use-doc-pane";
import { useDocUpload } from "@/hooks/use-doc-upload";
import { useLive150Runtime } from "@/hooks/use-live150-runtime";
import { useNotifications, type Notification } from "@/hooks/use-notifications";
import { cn } from "@/lib/utils";

function getGreeting(name: string): string {
  const hour = new Date().getHours();
  if (hour < 5) return `Up late, ${name}?`;
  if (hour < 12) return `Good morning, ${name}`;
  if (hour < 17) return `Good afternoon, ${name}`;
  if (hour < 21) return `Good evening, ${name}`;
  return `Winding down, ${name}?`;
}

interface Props {
  phone: string;
  userName: string;
}

export function ChatV2View({ phone, userName }: Props) {
  const { upload } = useDocUpload();
  const pane = useDocPane();

  const { runtime, messages, injectAssistantMessage } = useLive150Runtime({
    phone,
    uploadDoc: upload,
  });

  const onReminderFired = useCallback(
    (n: Notification) => {
      if (!n.message_id || !n.body) return;
      injectAssistantMessage(n.message_id, n.body, new Date());
    },
    [injectAssistantMessage],
  );

  // Banner intentionally omitted on /chatv2 — reminder text lands inline as
  // a chat message via onReminderFired; useNotifications still runs for its
  // SSE subscribe + catchup side effects.
  useNotifications(phone, onReminderFired);

  const greeting = useMemo(() => getGreeting(userName), [userName]);

  // Suggestions come from the most recent assistant message's metadata.
  const suggestions = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (m.role === "assistant" && m.suggestions && m.suggestions.length > 0) {
        return m.suggestions;
      }
    }
    return [];
  }, [messages]);

  return (
    <div className="flex h-[calc(100vh-56px)] w-full">
      <div
        className={cn(
          "flex min-h-0 flex-col transition-[width] duration-200",
          pane.open ? "w-0 overflow-hidden lg:w-1/2" : "w-full",
        )}
      >
        <ChatV2Thread
          runtime={runtime}
          greeting={greeting}
          suggestions={suggestions}
          phone={phone}
        />
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
