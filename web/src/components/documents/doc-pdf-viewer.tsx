import { useEffect, useState } from "react";
import { Document as PdfDocument, Page, pdfjs } from "react-pdf";
import workerSrc from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import {
  ChevronLeft,
  ChevronRight,
  Minus,
  Plus,
  AlertCircle,
} from "lucide-react";

import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocBlob } from "@/hooks/use-doc-blob";

pdfjs.GlobalWorkerOptions.workerSrc = workerSrc;

interface DocPdfViewerProps {
  documentId: string;
  phone: string;
}

const MIN_SCALE = 0.5;
const MAX_SCALE = 2.5;
const SCALE_STEP = 0.1;

function PdfSkeleton() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8">
      <Skeleton className="h-[60%] w-[70%] max-w-md rounded-md" />
      <Skeleton className="h-3 w-24" />
    </div>
  );
}

function PdfError({ message }: { message: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
      <AlertCircle className="size-8 text-destructive" />
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

export function DocPdfViewer({ documentId, phone }: DocPdfViewerProps) {
  const { data, isLoading, error } = useDocBlob(documentId, phone);
  const [numPages, setNumPages] = useState(0);
  const [pageNumber, setPageNumber] = useState(1);
  const [scale, setScale] = useState(1);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Revoke the blob URL when this viewer unmounts or the URL changes.
  useEffect(() => {
    const url = data?.url;
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [data?.url]);

  // Reset page when the document changes.
  useEffect(() => {
    setPageNumber(1);
    setNumPages(0);
    setScale(1);
    setLoadError(null);
  }, [documentId]);

  if (isLoading) return <PdfSkeleton />;
  if (error || !data) {
    return <PdfError message={error?.message ?? "Failed to load PDF."} />;
  }
  if (loadError) return <PdfError message={loadError} />;

  const canPrev = pageNumber > 1;
  const canNext = numPages > 0 && pageNumber < numPages;

  return (
    <div className="relative flex h-full flex-col bg-muted/20">
      <ScrollArea className="flex-1">
        <div
          className="flex min-h-full justify-center p-4"
          onDoubleClick={() => setScale(1)}
        >
          <PdfDocument
            file={data.url}
            loading={<PdfSkeleton />}
            error={<PdfError message="Could not render PDF." />}
            onLoadSuccess={({ numPages: n }) => setNumPages(n)}
            onLoadError={(e: Error) => setLoadError(e.message)}
          >
            <Page
              pageNumber={pageNumber}
              scale={scale}
              renderTextLayer={false}
              renderAnnotationLayer={false}
              loading={<Skeleton className="h-[600px] w-[460px]" />}
            />
          </PdfDocument>
        </div>
      </ScrollArea>
      <div className="flex items-center justify-center gap-2 border-t border-border bg-card px-4 py-2">
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Previous page"
          onClick={() => setPageNumber((p) => Math.max(1, p - 1))}
          disabled={!canPrev}
        >
          <ChevronLeft className="size-4" />
        </Button>
        <span className="min-w-[64px] text-center text-xs tabular-nums text-muted-foreground">
          {pageNumber} / {numPages || "—"}
        </span>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Next page"
          onClick={() => setPageNumber((p) => Math.min(numPages || p, p + 1))}
          disabled={!canNext}
        >
          <ChevronRight className="size-4" />
        </Button>
        <Separator orientation="vertical" className="mx-2 h-5" />
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Zoom out"
          onClick={() => setScale((s) => Math.max(MIN_SCALE, s - SCALE_STEP))}
          disabled={scale <= MIN_SCALE + 0.001}
        >
          <Minus className="size-4" />
        </Button>
        <span className="w-10 text-center text-xs tabular-nums text-muted-foreground">
          {Math.round(scale * 100)}%
        </span>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Zoom in"
          onClick={() => setScale((s) => Math.min(MAX_SCALE, s + SCALE_STEP))}
          disabled={scale >= MAX_SCALE - 0.001}
        >
          <Plus className="size-4" />
        </Button>
      </div>
    </div>
  );
}
