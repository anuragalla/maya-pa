import { useEffect, useState } from "react";
import { AlertCircle, FileImage } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocBlob } from "@/hooks/use-doc-blob";

interface DocImageViewerProps {
  documentId: string;
  phone: string;
  mime: string;
  filename: string;
}

/**
 * Triggers a download of the current blob via an off-DOM anchor.
 * Kept inline because both branches in this file want the same behaviour.
 */
function downloadBlob(url: string, filename: string): void {
  const a = window.document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  window.document.body.appendChild(a);
  a.click();
  a.remove();
}

export function DocImageViewer({
  documentId,
  phone,
  filename,
}: DocImageViewerProps) {
  const { data, isLoading, error } = useDocBlob(documentId, phone);
  const [imgError, setImgError] = useState(false);

  useEffect(() => {
    const url = data?.url;
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [data?.url]);

  useEffect(() => {
    setImgError(false);
  }, [documentId]);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center p-4">
        <Skeleton className="h-[70%] w-[70%] rounded-md" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
        <AlertCircle className="size-8 text-destructive" />
        <p className="text-sm text-muted-foreground">
          {error?.message ?? "Failed to load image."}
        </p>
      </div>
    );
  }

  if (imgError) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
        <FileImage className="size-10 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          Your browser can&apos;t preview this image format (likely HEIC on
          desktop). Download to view it.
        </p>
        <Button onClick={() => downloadBlob(data.url, filename)}>
          Download
        </Button>
      </div>
    );
  }

  return (
    <div className="flex h-full items-center justify-center bg-muted/20 p-4">
      <img
        src={data.url}
        alt={filename}
        onError={() => setImgError(true)}
        className="max-h-full max-w-full rounded-md object-contain"
      />
    </div>
  );
}
