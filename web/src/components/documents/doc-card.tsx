import { Sparkles } from "lucide-react";
import { useEffect, useMemo } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocPane } from "@/hooks/use-doc-pane";
import { useDocStream } from "@/hooks/use-doc-stream";
import { useDocument, useInvalidateDocument } from "@/hooks/use-document";
import { mimeIcon, type DocStatus, type DocType } from "@/lib/documents";

interface DocCardProps {
  documentId: string;
  phone: string;
  filename?: string;
  docType?: DocType;
  status?: DocStatus;
  compact?: boolean;
}

const ACTIVE_STATUSES = new Set<DocStatus>(["pending", "uploaded", "processing"]);

export function DocCard({
  documentId,
  phone,
  filename,
  docType,
  status: initialStatus,
  compact = false,
}: DocCardProps) {
  const { open, doc: openDocId, openDoc } = useDocPane();
  const invalidate = useInvalidateDocument();

  const { data: doc } = useDocument(documentId, phone);

  const effectiveStatus: DocStatus | undefined = doc?.status ?? initialStatus;
  const sseEnabled = effectiveStatus === undefined || ACTIVE_STATUSES.has(effectiveStatus);
  const sseDocId = sseEnabled ? documentId : null;

  const { stage, label } = useDocStream(sseDocId, phone);

  // When SSE flips to a terminal stage, refetch the row so the card snaps
  // to its final shape. SSE handles staleness — we never poll.
  useEffect(() => {
    if (stage === "ready" || stage === "failed" || stage === "cancelled") {
      invalidate(documentId);
    }
  }, [stage, documentId, invalidate]);

  const status: DocStatus = effectiveStatus ?? "processing";
  const displayFilename = doc?.original_filename ?? filename ?? "Document";
  const displayType: DocType = doc?.doc_type ?? docType ?? "other";
  const Icon = useMemo(() => mimeIcon(doc?.mime_type ?? ""), [doc?.mime_type]);
  const isOpen = open && openDocId === documentId;
  const isActive = ACTIVE_STATUSES.has(status);
  const isFailed = status === "failed";
  const isCancelled = status === "cancelled";

  const handleOpen = () => openDoc(documentId, "summary");

  if (compact) {
    return (
      <Button
        variant="ghost"
        size="sm"
        className="h-8 justify-start gap-2 px-2"
        aria-haspopup="dialog"
        aria-expanded={isOpen}
        onClick={handleOpen}
      >
        <Icon className="size-3.5 text-muted-foreground" />
        <span className="truncate text-xs">{displayFilename}</span>
        <span className={statusDotClass(status)} aria-label={status} />
      </Button>
    );
  }

  return (
    <Card
      className={cardClass(status)}
      role="button"
      aria-haspopup="dialog"
      aria-expanded={isOpen}
      tabIndex={0}
      onClick={handleOpen}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          handleOpen();
        }
      }}
    >
      <div className="flex items-start gap-3 p-3">
        {isActive ? (
          <Sparkles className="mt-0.5 size-4 shrink-0 text-primary" />
        ) : (
          <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
        )}
        <div className="min-w-0 flex-1">
          {isActive && !doc ? (
            <Skeleton className="h-4 w-40" />
          ) : (
            <div className="truncate text-sm font-medium">{displayFilename}</div>
          )}
          <div className="mt-0.5 flex items-center gap-2" aria-live="polite">
            {isActive && (
              <span className="text-xs text-muted-foreground">
                {label || "Maya is reading…"}
              </span>
            )}
            {isFailed && (
              <span className="text-xs text-destructive">
                {doc?.error_message ?? "Couldn't process this document."}
              </span>
            )}
            {isCancelled && (
              <span className="text-xs text-muted-foreground">Cancelled</span>
            )}
            {status === "ready" && doc?.tags?.slice(0, 3).map((t) => (
              <Badge key={t} variant="tag" className="text-[10px]">
                {t}
              </Badge>
            ))}
          </div>
        </div>
        <Badge variant={badgeVariant(status)} className="shrink-0 text-[10px]">
          {status === "ready" ? displayType : status}
        </Badge>
      </div>
    </Card>
  );
}

// DocCards live inside user bubbles (bg-primary solid). A neutral bg-card looks
// pasted-on; a violet-tinted surface reads as part of the family — deep plum in
// dark mode, pale lavender in light.
// The base Card already sets `ring-1 ring-foreground/10`; we override the ring
// color to stay in the violet family. No `border-*` classes — avoids the
// double-outline (ring + border) that looked fuzzy/weird.
const DOC_SURFACE =
  "bg-violet-100 ring-violet-300/50 dark:bg-violet-950/95 dark:ring-violet-700/40";
const DOC_SURFACE_HOVER =
  "hover:bg-violet-200/70 dark:hover:bg-violet-900/90";

function cardClass(status: DocStatus): string {
  if (status === "failed") {
    return `cursor-pointer ring-destructive/40 ${DOC_SURFACE.replace(/ring-violet-[^\s]+/g, "")} bg-violet-100 dark:bg-violet-950/95 transition-colors hover:bg-destructive/10 dark:hover:bg-destructive/15`;
  }
  if (status === "cancelled") {
    return `cursor-pointer ${DOC_SURFACE} opacity-80 transition-opacity hover:opacity-100`;
  }
  if (ACTIVE_STATUSES.has(status)) {
    // Dashed ring-like outline via a faint inset; no border-width wrestling.
    return `cursor-pointer ${DOC_SURFACE} ${DOC_SURFACE_HOVER} transition-colors`;
  }
  return `cursor-pointer ${DOC_SURFACE} ${DOC_SURFACE_HOVER} transition-colors`;
}

function badgeVariant(status: DocStatus): "destructive" | "outline" {
  if (status === "failed") return "destructive";
  return "outline";
}

function statusDotClass(status: DocStatus): string {
  const base = "inline-block size-1.5 rounded-full";
  if (status === "ready") return `${base} bg-emerald-500`;
  if (status === "failed") return `${base} bg-destructive`;
  if (status === "cancelled") return `${base} bg-muted-foreground`;
  return `${base} bg-primary animate-pulse`;
}
