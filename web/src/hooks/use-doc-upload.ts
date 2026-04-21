import { useCallback, useRef, useState } from "react";
import type { DocUploadResponse } from "@/lib/documents";

interface UseDocUploadResult {
  upload: (file: File, phone: string) => Promise<DocUploadResponse>;
  cancel: () => void;
  progress: number;
  error: string | null;
  isUploading: boolean;
}

/**
 * POST /api/v1/documents (multipart). Uses XMLHttpRequest because fetch lacks
 * upload-progress events. The hook exposes cancel() which aborts the most
 * recent in-flight request.
 */
export function useDocUpload(): UseDocUploadResult {
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const xhrRef = useRef<XMLHttpRequest | null>(null);

  const upload = useCallback((file: File, phone: string): Promise<DocUploadResponse> => {
    return new Promise<DocUploadResponse>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhrRef.current = xhr;

      const form = new FormData();
      form.append("file", file);
      form.append("source", "file_upload");

      xhr.open("POST", "/api/v1/documents");
      xhr.setRequestHeader("X-Phone-Number", phone);
      xhr.responseType = "text";

      setProgress(0);
      setError(null);
      setIsUploading(true);

      xhr.upload.onprogress = (e) => {
        if (!e.lengthComputable) return;
        setProgress(Math.round((e.loaded / e.total) * 100));
      };

      xhr.onload = () => {
        setIsUploading(false);
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const body: unknown = JSON.parse(xhr.responseText);
            if (
              body &&
              typeof body === "object" &&
              typeof (body as { document_id?: unknown }).document_id === "string" &&
              typeof (body as { status?: unknown }).status === "string"
            ) {
              resolve(body as DocUploadResponse);
              return;
            }
            const msg = "Upload response missing document_id/status";
            setError(msg);
            reject(new Error(msg));
          } catch {
            const msg = "Invalid JSON in upload response";
            setError(msg);
            reject(new Error(msg));
          }
        } else {
          const msg = xhr.responseText || `Upload failed (${xhr.status})`;
          setError(msg);
          reject(new Error(msg));
        }
      };

      xhr.onerror = () => {
        setIsUploading(false);
        const msg = "Network error during upload";
        setError(msg);
        reject(new Error(msg));
      };

      xhr.onabort = () => {
        setIsUploading(false);
        const msg = "Upload cancelled";
        setError(msg);
        reject(new Error(msg));
      };

      xhr.send(form);
    });
  }, []);

  const cancel = useCallback(() => {
    xhrRef.current?.abort();
  }, []);

  return { upload, cancel, progress, error, isUploading };
}
