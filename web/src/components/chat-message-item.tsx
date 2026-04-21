import {
  Message,
  MessageActions,
  MessageAction,
  MessageContent,
  MessageResponse,
} from "@/components/ai-elements/message";
import { DocCard } from "@/components/documents/doc-card";
import { ThinkingBlock } from "@/components/thinking-block";
import type { MessageDocAttachment } from "@/lib/documents";
import { formatTimestamp } from "@/lib/utils";
import { CheckIcon, CopyIcon } from "lucide-react";
import { useState } from "react";

const TOOL_TITLES: Record<string, string> = {
  get_holistic_analysis: "Holistic Analysis",
  get_progress_by_date: "Daily Progress",
  get_health_goals: "Health Goals",
  get_meal_plan: "Meal Plan",
  get_initial_context: "User Context",
  search_memory: "Memory Search",
  save_memory: "Save Memory",
  create_reminder: "Create Reminder",
  list_reminders: "List Reminders",
  cancel_reminder: "Cancel Reminder",
  skill_search: "Skill Search",
  skill_load: "Load Skill",
  get_calendar_schedule: "Calendar Schedule",
  create_live150_event: "Create Event",
  delete_live150_event: "Delete Event",
  find_free_slots: "Find Free Slots",
  check_calendar_connection: "Calendar Status",
  list_available_integrations: "Integrations",
  request_integration_connect: "Connect Integration",
};

function isToolPart(part: any): boolean {
  return part.type === "dynamic-tool" || (part.type?.startsWith("tool-") && part.type !== "tool-invocation");
}

export interface ToolCallInfo {
  key: string;
  name: string;
  title: string;
  state: string;
  output: any;
  errorText: string;
}

function extractToolInfo(part: any, index: number): ToolCallInfo {
  const isDynamic = part.type === "dynamic-tool";
  const isInvocation = part.type === "tool-invocation";

  const name = isDynamic
    ? part.toolName ?? "unknown"
    : isInvocation
      ? part.toolInvocation?.toolName ?? "unknown"
      : part.type.replace("tool-", "");

  const state = isInvocation
    ? part.toolInvocation?.state ?? "input-available"
    : part.state ?? "input-available";

  const output = isInvocation
    ? part.toolInvocation?.result ?? null
    : part.output ?? null;

  const errorText = isInvocation ? "" : part.errorText ?? "";

  const callId = isInvocation
    ? part.toolInvocation?.toolCallId ?? ""
    : part.toolCallId ?? "";

  return {
    key: `${callId}-${index}`,
    name,
    title: TOOL_TITLES[name] ?? name,
    state,
    output,
    errorText,
  };
}

export function ChatMessageItem({
  message,
  isStreaming,
  phone,
}: {
  message: any;
  isStreaming: boolean;
  phone: string;
}) {
  const [copied, setCopied] = useState(false);
  const parts: any[] = message.parts ?? [];
  const attachments: MessageDocAttachment[] = Array.isArray(message.documents)
    ? message.documents
    : [];
  const textParts = parts.filter((p: any) => p.type === "text" && p.text?.trim());
  const toolParts = parts.filter((p: any) => isToolPart(p) || p.type === "tool-invocation");

  const toolCalls = toolParts.map((p, i) => extractToolInfo(p, i));

  const allToolsDone = toolCalls.length > 0 && toolCalls.every(
    (t) => t.state === "output-available" || t.state === "output-error" || t.state === "result"
  );

  const hasTools = toolCalls.length > 0;
  const hasText = textParts.length > 0;
  const isAssistant = message.role !== "user";

  const isActivelyStreaming = isAssistant && isStreaming;
  const showThinking = isAssistant && (hasTools || (isActivelyStreaming && !hasText));
  const thinkingIsStreaming = isActivelyStreaming && !(allToolsDone && hasText);

  const timestamp = !isAssistant && message.createdAt
    ? formatTimestamp(new Date(message.createdAt))
    : "";

  const handleCopy = () => {
    const text = textParts.map((p: any) => p.text).join("\n\n");
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <Message from={message.role}>
      <MessageContent>
        {attachments.length > 0 && (
          <div className="mb-2 flex flex-col gap-2">
            {attachments.map((doc) => (
              <DocCard
                key={doc.document_id}
                documentId={doc.document_id}
                phone={phone}
                filename={doc.original_filename}
                docType={doc.doc_type}
                status={doc.status}
              />
            ))}
          </div>
        )}
        {showThinking && (
          <ThinkingBlock
            toolCalls={toolCalls}
            isStreaming={thinkingIsStreaming}
            isDone={!thinkingIsStreaming && hasTools}
          />
        )}
        {textParts.map((part: any, i: number) => (
          <MessageResponse key={`text-${i}`}>{part.text}</MessageResponse>
        ))}
      </MessageContent>

      {isAssistant && hasText && !isStreaming && (
        <MessageActions>
          <MessageAction tooltip={copied ? "Copied" : "Copy"} onClick={handleCopy}>
            {copied ? <CheckIcon size={13} className="text-green-500" /> : <CopyIcon size={13} />}
          </MessageAction>
        </MessageActions>
      )}
      {timestamp && (
        <span className="text-[11px] text-muted-foreground/50 select-none self-end px-1">
          {timestamp}
        </span>
      )}
    </Message>
  );
}
