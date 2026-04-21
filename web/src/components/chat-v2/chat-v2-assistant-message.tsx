import { MessagePrimitive, useMessage, useThread } from "@assistant-ui/react";

import { MessageResponse } from "@/components/ai-elements/message";
import { ThinkingBlock } from "@/components/thinking-block";

function MarkdownText({ text }: { text: string }) {
  return <MessageResponse>{text}</MessageResponse>;
}

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
  list_documents: "List Documents",
  get_document: "Get Document",
  doc_analyst: "Analyze Document",
};

export function ChatV2AssistantMessage() {
  const message = useMessage();
  const thread = useThread();

  const toolCalls = (message.content ?? [])
    .filter((p) => p.type === "tool-call")
    .map((p, i) => {
      const tc = p as {
        toolCallId?: string;
        toolName: string;
        args?: unknown;
        result?: unknown;
      };
      const name = tc.toolName ?? "unknown";
      const hasResult = tc.result !== undefined && tc.result !== null;
      return {
        key: `${tc.toolCallId ?? "tc"}-${i}`,
        name,
        title: TOOL_TITLES[name] ?? name,
        state: hasResult ? "output-available" : "input-available",
        output: tc.result ?? null,
        errorText: "",
      };
    });

  // The runtime doesn't always mirror its `isRunning` flag onto the last
  // message's status when the stream hasn't produced any parts yet (e.g. we're
  // server-side blocked on doc processing). Use thread-level isRunning combined
  // with isLast to decide whether to render the thinking pulse.
  const isStreaming =
    message.status?.type === "running" || (thread.isRunning && message.isLast);
  const hasText = (message.content ?? []).some(
    (p) => p.type === "text" && "text" in p && (p as { text?: string }).text,
  );
  const showThinking = toolCalls.length > 0 || (isStreaming && !hasText);

  return (
    <MessagePrimitive.Root className="group is-assistant flex w-full">
      <div className="flex w-full flex-col gap-2 text-sm text-foreground">
        {showThinking && (
          <ThinkingBlock
            toolCalls={toolCalls}
            isStreaming={isStreaming && !hasText}
            isDone={!isStreaming && toolCalls.length > 0}
          />
        )}
        {/* Tool-calls are rendered above via ThinkingBlock — suppress the
            default tool-part rendering to avoid duplicate output. */}
        <MessagePrimitive.Parts
          components={{
            Text: MarkdownText,
            tools: { Fallback: () => null },
          }}
        />
      </div>
    </MessagePrimitive.Root>
  );
}
