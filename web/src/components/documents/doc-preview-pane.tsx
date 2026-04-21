import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { MoreHorizontal, X } from "lucide-react";

import type { DocumentRow } from "@/lib/documents";
import { DocPreview } from "@/components/documents/doc-preview";
import { DocSummary } from "@/components/documents/doc-summary";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useDocBlob } from "@/hooks/use-doc-blob";
import { useDocPane, type DocPaneTab } from "@/hooks/use-doc-pane";
import { useDocument } from "@/hooks/use-document";

interface DocPreviewPaneProps {
  phone: string;
}

const DAY = 86_400_000;
const HOUR = 3_600_000;
const MIN = 60_000;

function formatRelativeTime(iso: string): string {
  const parsed = Date.parse(iso);
  if (Number.isNaN(parsed)) return "";
  const delta = Date.now() - parsed;
  if (delta < MIN) return "just now";
  if (delta < HOUR) {
    const m = Math.floor(delta / MIN);
    return `${m} min ago`;
  }
  if (delta < DAY) {
    const h = Math.floor(delta / HOUR);
    return `${h} hr ago`;
  }
  const days = Math.floor(delta / DAY);
  if (days === 1) return "yesterday";
  if (days < 30) return `${days} days ago`;
  return new Date(parsed).toLocaleDateString();
}

function PaneSkeleton() {
  return (
    <div className="flex h-full flex-col gap-3 p-4">
      <Skeleton className="h-4 w-2/3" />
      <Skeleton className="h-4 w-1/2" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

function PaneHeader({
  document,
  onClose,
  onDownload,
  onDeleteRequest,
}: {
  document: DocumentRow | undefined;
  onClose: () => void;
  onDownload: () => void;
  onDeleteRequest: () => void;
}) {
  const subtitle = document
    ? `${document.doc_type} · ${formatRelativeTime(document.uploaded_at)}`
    : null;

  return (
    <header className="flex h-14 items-center gap-2 border-b border-border px-4">
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={onClose}
        aria-label="Close"
      >
        <X className="size-4" />
      </Button>
      <div className="min-w-0 flex-1">
        <h3 className="truncate text-sm font-medium">
          {document?.original_filename ?? "Loading…"}
        </h3>
        {subtitle ? (
          <p className="truncate text-xs text-muted-foreground">{subtitle}</p>
        ) : (
          <Skeleton className="mt-1 h-3 w-24" />
        )}
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button variant="ghost" size="icon-sm" aria-label="Actions">
              <MoreHorizontal className="size-4" />
            </Button>
          }
        />
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            onClick={onDownload}
            disabled={!document}
          >
            Download
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={onDeleteRequest}
            variant="destructive"
            disabled={!document}
          >
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}

export function DocPreviewPane({ phone }: DocPreviewPaneProps) {
  const { open, doc, tab, setTab, close } = useDocPane();
  const { data: document, isLoading } = useDocument(doc, phone);
  const queryClient = useQueryClient();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Pre-fetch blob for the download action. Cheap — useDocBlob is cached.
  const { data: blobData } = useDocBlob(doc, phone);

  const handleDownload = useCallback(() => {
    if (!blobData || !document) return;
    const a = window.document.createElement("a");
    a.href = blobData.url;
    a.download = document.original_filename;
    a.rel = "noopener";
    window.document.body.appendChild(a);
    a.click();
    a.remove();
  }, [blobData, document]);

  const handleDelete = useCallback(async () => {
    if (!doc) return;
    setDeleting(true);
    try {
      const res = await fetch(`/api/v1/documents/${doc}`, {
        method: "DELETE",
        headers: { "X-Phone-Number": phone },
      });
      if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
      await queryClient.invalidateQueries({ queryKey: ["document", doc] });
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
      setConfirmOpen(false);
      close();
    } catch {
      // Leave the dialog open so the user can retry. Swallow error — the
      // pane isn't the right place for a toast system.
    } finally {
      setDeleting(false);
    }
  }, [doc, phone, queryClient, close]);

  if (!open || !doc) return null;

  const tabContent = document ? (
    <>
      <TabsContent value="preview" className="m-0 min-h-0 flex-1 p-0">
        <DocPreview document={document} phone={phone} />
      </TabsContent>
      <TabsContent
        value="summary"
        className="m-0 min-h-0 flex-1 overflow-hidden p-0"
      >
        <DocSummary document={document} />
      </TabsContent>
    </>
  ) : (
    <>
      <TabsContent value="preview" className="m-0 min-h-0 flex-1 p-0">
        <PaneSkeleton />
      </TabsContent>
      <TabsContent value="summary" className="m-0 min-h-0 flex-1 p-0">
        <PaneSkeleton />
      </TabsContent>
    </>
  );

  return (
    <aside role="complementary" className="flex h-full flex-col bg-card">
      <PaneHeader
        document={document}
        onClose={close}
        onDownload={handleDownload}
        onDeleteRequest={() => setConfirmOpen(true)}
      />

      <Tabs
        value={tab}
        onValueChange={(v) => setTab(v as DocPaneTab)}
        className="flex min-h-0 flex-1 flex-col"
      >
        <TabsList
          variant="line"
          className="h-10 rounded-none border-b border-border px-2"
        >
          <TabsTrigger value="preview">Preview</TabsTrigger>
          <TabsTrigger value="summary">Summary</TabsTrigger>
        </TabsList>

        {isLoading && !document ? <PaneSkeleton /> : tabContent}
      </Tabs>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this document?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently removes the document and its summary. This
              action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={handleDelete}
              disabled={deleting}
            >
              {deleting ? "Deleting…" : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </aside>
  );
}
