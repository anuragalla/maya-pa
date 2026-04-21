import { useMemo } from "react";

import { ChatV2Thread } from "@/components/chat-v2/chat-v2-thread";
import { useDocUpload } from "@/hooks/use-doc-upload";
import { useLive150Runtime } from "@/hooks/use-live150-runtime";

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

  const { runtime, messages } = useLive150Runtime({
    phone,
    uploadDoc: upload,
  });

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
      <ChatV2Thread
        runtime={runtime}
        greeting={greeting}
        suggestions={suggestions}
        phone={phone}
      />
    </div>
  );
}
