import type { DocumentRow } from "@/lib/documents";
import { DocPdfViewer } from "@/components/documents/doc-pdf-viewer";
import { DocImageViewer } from "@/components/documents/doc-image-viewer";

interface DocPreviewProps {
  document: DocumentRow;
  phone: string;
}

/**
 * Thin dispatcher that selects the right viewer based on the document's
 * mime type. Anything we can't render inline falls back to a short "not
 * supported" message — the pane header provides the Download action.
 */
export function DocPreview({ document, phone }: DocPreviewProps) {
  if (document.mime_type === "application/pdf") {
    return <DocPdfViewer documentId={document.document_id} phone={phone} />;
  }

  if (document.mime_type.startsWith("image/")) {
    return (
      <DocImageViewer
        documentId={document.document_id}
        phone={phone}
        mime={document.mime_type}
        filename={document.original_filename}
      />
    );
  }

  return (
    <div className="flex h-full items-center justify-center p-8 text-center">
      <p className="text-sm text-muted-foreground">
        Preview not supported for this file type. Use the menu to download.
      </p>
    </div>
  );
}
