import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { mimeIcon } from "@/lib/documents";
import { cn } from "@/lib/utils";

interface Props {
  filename: string;
  sizeBytes: number;
  mimeType: string;
  onRemove: () => void;
  uploadProgress?: number;
  error?: string | null;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function DocAttachmentChip({
  filename,
  sizeBytes,
  mimeType,
  onRemove,
  uploadProgress,
  error,
}: Props) {
  const Icon = mimeIcon(mimeType);
  const isUploading = typeof uploadProgress === "number" && uploadProgress < 100;

  return (
    <div
      className={cn(
        "mx-3 mt-3 flex items-center gap-2 rounded-md border bg-muted/40 px-2.5 py-2 text-sm",
        error && "border-destructive/40 bg-destructive/10",
      )}
    >
      <Icon className="size-4 shrink-0 text-muted-foreground" />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <div className="flex items-center gap-2">
          <span className="truncate max-w-xs font-medium text-foreground">
            {filename}
          </span>
          <span className="shrink-0 text-xs text-muted-foreground">
            {formatSize(sizeBytes)}
          </span>
        </div>
        {isUploading && (
          <Progress value={uploadProgress} className="h-1" />
        )}
        {error && (
          <Tooltip>
            <TooltipTrigger
              render={(props) => (
                <span
                  {...props}
                  className="truncate text-xs text-destructive cursor-help"
                >
                  {error}
                </span>
              )}
            />
            <TooltipContent side="top">{error}</TooltipContent>
          </Tooltip>
        )}
      </div>
      <Button
        variant="ghost"
        size="icon"
        className="size-6 shrink-0 text-muted-foreground"
        aria-label="Remove attachment"
        onClick={onRemove}
        type="button"
      >
        <X className="size-3.5" />
      </Button>
    </div>
  );
}
