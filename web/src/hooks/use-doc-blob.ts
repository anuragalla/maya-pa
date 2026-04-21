import { useQuery, type UseQueryResult } from "@tanstack/react-query";

export interface DocBlobResult {
  blob: Blob;
  url: string;
  mime: string;
}

/**
 * GET /api/v1/documents/{id}/content as a blob URL.
 *
 * IMPORTANT: blob URLs leak memory. TanStack Query cannot observe consumer
 * lifecycle, so the caller MUST `URL.revokeObjectURL(url)` on unmount —
 * typically inside a `useEffect` cleanup tied to `data?.url`.
 */
export function useDocBlob(
  documentId: string | null,
  phone: string,
): UseQueryResult<DocBlobResult, Error> {
  return useQuery<DocBlobResult, Error>({
    queryKey: ["doc-blob", documentId],
    queryFn: async () => {
      if (!documentId) throw new Error("no doc id");
      const res = await fetch(`/api/v1/documents/${documentId}/content`, {
        headers: { "X-Phone-Number": phone },
      });
      if (!res.ok) throw new Error(`Blob fetch failed: ${res.status}`);
      const blob = await res.blob();
      return { blob, url: URL.createObjectURL(blob), mime: blob.type };
    },
    enabled: !!documentId && !!phone,
    staleTime: 5 * 60 * 1000,
    gcTime: 5 * 60 * 1000,
  });
}
