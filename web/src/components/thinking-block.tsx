import { useState } from "react";
import {
  CheckCircleIcon,
  ChevronDownIcon,
  Loader2Icon,
  SparklesIcon,
  XCircleIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Shimmer } from "@/components/ai-elements/shimmer";
import { Button } from "@/components/ui/button";
import type { ToolCallInfo } from "@/components/chat-message-item";

interface ThinkingBlockProps {
  toolCalls: ToolCallInfo[];
  isStreaming: boolean;
  isDone: boolean;
}

export function ThinkingBlock({ toolCalls, isStreaming, isDone }: ThinkingBlockProps) {
  const [isOpen, setIsOpen] = useState(false);

  const completedCount = toolCalls.filter(
    (t) => t.state === "output-available" || t.state === "result"
  ).length;
  const failedCount = toolCalls.filter((t) => t.state === "output-error").length;
  const totalCount = toolCalls.length;

  return (
    <div className="mb-2">
      {/* Trigger row */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full justify-start gap-2 px-1 py-1.5 text-left text-sm hover:bg-card"
      >
        {isStreaming ? (
          <Loader2Icon className="size-4 animate-spin text-accent" />
        ) : failedCount > 0 ? (
          <XCircleIcon className="size-4 text-destructive" />
        ) : (
          <SparklesIcon className="size-4 text-accent" />
        )}

        {isStreaming ? (
          <Shimmer duration={1.5} className="text-sm">
            Thinking...
          </Shimmer>
        ) : (
          <span className="text-xs text-muted-foreground">
            {failedCount > 0
              ? `${completedCount} completed, ${failedCount} failed`
              : `${completedCount} tool${completedCount !== 1 ? "s" : ""} used`}
          </span>
        )}

        {totalCount > 0 && (
          <ChevronDownIcon
            className={cn(
              "ml-auto size-3.5 text-muted-foreground transition-transform",
              isOpen && "rotate-180"
            )}
          />
        )}
      </Button>

      {/* Expanded tool list */}
      {isOpen && totalCount > 0 && (
        <div className="mt-1 space-y-0.5 rounded-lg border border-border bg-card p-2">
          {toolCalls.map((tool) => (
            <ToolCallRow key={tool.key} tool={tool} />
          ))}
        </div>
      )}
    </div>
  );
}

function ToolCallRow({ tool }: { tool: ToolCallInfo }) {
  const [showResult, setShowResult] = useState(false);
  const isRunning = tool.state === "input-available" || tool.state === "input-streaming";
  const isDone = tool.state === "output-available" || tool.state === "result";
  const isFailed = tool.state === "output-error";
  const hasOutput = tool.output || tool.errorText;

  return (
    <div>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => hasOutput && setShowResult(!showResult)}
        className={cn(
          "w-full justify-start gap-2 px-2 py-1.5 text-left text-xs",
          hasOutput && "hover:bg-background",
          !hasOutput && "cursor-default hover:bg-transparent"
        )}
      >
        {/* Status icon */}
        {isRunning ? (
          <Loader2Icon className="size-3.5 animate-spin text-accent" />
        ) : isDone ? (
          <CheckCircleIcon className="size-3.5 text-success" />
        ) : isFailed ? (
          <XCircleIcon className="size-3.5 text-destructive" />
        ) : (
          <Loader2Icon className="size-3.5 animate-spin text-muted-foreground" />
        )}

        {/* Tool name */}
        <span className="text-muted-foreground">{tool.title}</span>

        {/* Status label */}
        <span
          className={cn(
            "ml-auto text-[10px]",
            isRunning && "text-accent",
            isDone && "text-success",
            isFailed && "text-destructive"
          )}
        >
          {isRunning ? "running" : isDone ? "done" : isFailed ? "failed" : "pending"}
        </span>

        {/* Expand indicator */}
        {hasOutput && (
          <ChevronDownIcon
            className={cn(
              "size-3 text-muted-foreground transition-transform",
              showResult && "rotate-180"
            )}
          />
        )}
      </Button>

      {/* Result (collapsed by default) */}
      {showResult && hasOutput && (
        <div className="mx-2 mb-1 mt-0.5 overflow-x-auto rounded-md bg-background p-2">
          {tool.errorText ? (
            <pre className="whitespace-pre-wrap text-[11px] text-destructive">
              {tool.errorText}
            </pre>
          ) : (
            <pre className="whitespace-pre-wrap text-[11px] text-muted-foreground">
              {typeof tool.output === "object"
                ? JSON.stringify(tool.output, null, 2)
                : String(tool.output)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
