import { Paperclip } from "lucide-react";
import { useCallback, useRef, useState } from "react";

import {
  PromptInput,
  PromptInputSubmit,
  PromptInputTextarea,
  usePromptInputAttachments,
} from "@/components/ai-elements/prompt-input";
import { DocAttachmentChip } from "@/components/documents/doc-attachment-chip";
import { Button } from "@/components/ui/button";
import {
  ACCEPT_ATTRIBUTE,
  ALLOWED_MIME_TYPES,
  MAX_UPLOAD_SIZE,
} from "@/lib/documents";

interface ChatComposerProps {
  value: string;
  onChange: (next: string) => void;
  onSubmit: (text: string, attachments: File[]) => void;
  disabled?: boolean;
  status?: "ready" | "streaming" | "error";
}

export function ChatComposer({
  value,
  onChange,
  onSubmit,
  disabled,
  status = "ready",
}: ChatComposerProps) {
  // PromptInput's attachments context only retains FileUIPart (filename, mediaType,
  // blob url) — we keep the raw File alongside so onSubmit can hand the parent
  // the real upload payload.
  const [staged, setStaged] = useState<File | null>(null);

  const handleSubmit = useCallback(
    (msg: { text: string }) => {
      const files = staged ? [staged] : [];
      if (!msg.text.trim() && files.length === 0) return;
      onSubmit(msg.text, files);
      setStaged(null);
    },
    [onSubmit, staged],
  );

  return (
    <PromptInput
      onSubmit={handleSubmit}
      accept={ACCEPT_ATTRIBUTE}
      maxFileSize={MAX_UPLOAD_SIZE}
      className="rounded-2xl border bg-background shadow-sm focus-within:shadow-md transition-shadow"
    >
      <ComposerInner
        value={value}
        onChange={onChange}
        disabled={disabled}
        status={status}
        staged={staged}
        setStaged={setStaged}
      />
    </PromptInput>
  );
}

interface InnerProps {
  value: string;
  onChange: (next: string) => void;
  disabled?: boolean;
  status: "ready" | "streaming" | "error";
  staged: File | null;
  setStaged: (next: File | null) => void;
}

function ComposerInner({ value, onChange, disabled, status, staged, setStaged }: InnerProps) {
  const attachments = usePromptInputAttachments();
  const hiddenInputRef = useRef<HTMLInputElement | null>(null);

  const openPicker = useCallback(() => {
    hiddenInputRef.current?.click();
  }, []);

  const handleFile = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.currentTarget.files?.[0];
      e.currentTarget.value = "";
      if (!file) return;

      if (!ALLOWED_MIME_TYPES.includes(file.type as never)) {
        console.warn(`[composer] rejected mime: ${file.type}`);
        return;
      }
      if (file.size > MAX_UPLOAD_SIZE) {
        console.warn(`[composer] rejected size: ${file.size}`);
        return;
      }

      if (attachments.files.length > 0) attachments.clear();
      attachments.add([file]);
      setStaged(file);
    },
    [attachments, setStaged],
  );

  const removeStaged = useCallback(() => {
    attachments.clear();
    setStaged(null);
  }, [attachments, setStaged]);

  const sendDisabled = disabled || (!value.trim() && !staged);

  return (
    <>
      <input
        ref={hiddenInputRef}
        type="file"
        accept={ACCEPT_ATTRIBUTE}
        hidden
        onChange={handleFile}
      />
      {staged && (
        <DocAttachmentChip
          filename={staged.name}
          sizeBytes={staged.size}
          mimeType={staged.type}
          onRemove={removeStaged}
        />
      )}
      <PromptInputTextarea
        placeholder="Reply…"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        rows={1}
        className="min-h-10 max-h-64 resize-none border-0 bg-transparent px-4 pt-3 pb-2 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
      />
      <div className="flex items-center justify-between px-2 pb-2">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Attach document"
          className="text-muted-foreground"
          onClick={openPicker}
        >
          <Paperclip className="size-4" />
        </Button>
        <PromptInputSubmit status={status} disabled={sendDisabled} />
      </div>
    </>
  );
}
