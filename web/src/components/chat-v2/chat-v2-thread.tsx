import {
  AssistantRuntimeProvider,
  AttachmentPrimitive,
  ComposerPrimitive,
  ThreadPrimitive,
  type AssistantRuntime,
} from "@assistant-ui/react";
import { FileIcon, Paperclip, Send, Square, X } from "lucide-react";
import { type FC } from "react";

import { ChatV2UserMessage } from "@/components/chat-v2/chat-v2-user-message";
import { ChatV2AssistantMessage } from "@/components/chat-v2/chat-v2-assistant-message";
import { ChatV2SuggestionPills } from "@/components/chat-v2/chat-v2-suggestion-pills";
import { Button } from "@/components/ui/button";

interface ChatV2ThreadProps {
  runtime: AssistantRuntime;
  greeting: string;
  suggestions: string[];
  phone: string;
}

export const ChatV2Thread: FC<ChatV2ThreadProps> = ({
  runtime,
  greeting,
  suggestions,
  phone,
}) => {
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ThreadPrimitive.Root className="flex h-full w-full flex-col bg-background">
        <ThreadPrimitive.Viewport className="flex-1 overflow-y-auto">
          <div className="mx-auto flex min-h-full max-w-[680px] flex-col gap-5 px-4 py-6 sm:px-6">
            <ThreadPrimitive.Empty>
              <div className="flex flex-col items-start gap-1 py-8">
                <h2 className="text-xl font-semibold text-foreground">{greeting}</h2>
                <p className="text-sm text-muted-foreground">What would you like to know?</p>
              </div>
            </ThreadPrimitive.Empty>

            <ThreadPrimitive.Messages
              components={{
                UserMessage: () => <ChatV2UserMessage phone={phone} />,
                AssistantMessage: () => <ChatV2AssistantMessage />,
              }}
            />
          </div>
        </ThreadPrimitive.Viewport>

        <div className="border-t border-border bg-background px-4 pb-4 pt-3">
          <div className="mx-auto max-w-[680px] space-y-3">
            <ChatV2SuggestionPills suggestions={suggestions} />
            <Composer />
          </div>
        </div>
      </ThreadPrimitive.Root>
    </AssistantRuntimeProvider>
  );
};

function Composer() {
  return (
    <ComposerPrimitive.Root className="w-full rounded-2xl border border-border bg-card shadow-sm transition-shadow focus-within:shadow-md">
      <div className="flex flex-wrap gap-2 px-3 pt-3 empty:hidden">
        <ComposerPrimitive.Attachments components={{ Attachment: ComposerAttachmentChip }} />
      </div>
      <ComposerPrimitive.Input
        asChild
        rows={1}
        autoFocus
        placeholder="Reply…"
      >
        <textarea className="min-h-10 w-full resize-none bg-transparent px-4 pt-3 pb-2 text-sm outline-none placeholder:text-muted-foreground" />
      </ComposerPrimitive.Input>
      <div className="flex items-center justify-between px-2 pb-2">
        <ComposerPrimitive.AddAttachment asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Attach document"
            className="text-muted-foreground"
          >
            <Paperclip className="size-4" />
          </Button>
        </ComposerPrimitive.AddAttachment>
        <SendOrCancel />
      </div>
    </ComposerPrimitive.Root>
  );
}

function SendOrCancel() {
  return (
    <>
      <ThreadPrimitive.If running={false}>
        <ComposerPrimitive.Send asChild>
          <Button
            type="submit"
            size="icon"
            aria-label="Send message"
            className="size-8 rounded-lg"
          >
            <Send className="size-4" />
          </Button>
        </ComposerPrimitive.Send>
      </ThreadPrimitive.If>
      <ThreadPrimitive.If running>
        <ComposerPrimitive.Cancel asChild>
          <Button
            type="button"
            size="icon"
            variant="secondary"
            aria-label="Stop"
            className="size-8 rounded-lg"
          >
            <Square className="size-3" />
          </Button>
        </ComposerPrimitive.Cancel>
      </ThreadPrimitive.If>
    </>
  );
}

function ComposerAttachmentChip() {
  return (
    <AttachmentPrimitive.Root className="inline-flex items-center gap-2 rounded-lg border border-border bg-muted/60 px-2.5 py-1.5 text-xs">
      <FileIcon className="size-3.5 text-muted-foreground" />
      <span className="font-medium max-w-[220px] truncate">
        <AttachmentPrimitive.Name />
      </span>
      <AttachmentPrimitive.Remove asChild>
        <button
          type="button"
          aria-label="Remove attachment"
          className="text-muted-foreground hover:text-foreground"
        >
          <X className="size-3.5" />
        </button>
      </AttachmentPrimitive.Remove>
    </AttachmentPrimitive.Root>
  );
}
