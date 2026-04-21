import {
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";
import { useCallback } from "react";

import type { DocumentRow } from "@/lib/documents";

/**
 * GET /api/v1/documents/{id}.
 *
 * No refetchInterval — staleness is driven by SSE. The DocCard calls
 * `useInvalidateDocument()` when its SSE stream flips to `ready` / `failed`
 * so the query refetches and reveals the processed row.
 */
export function useDocument(
  documentId: string | null,
  phone: string,
): UseQueryResult<DocumentRow, Error> {
  return useQuery<DocumentRow, Error>({
    queryKey: ["document", documentId],
    queryFn: async () => {
      if (!documentId) throw new Error("no doc id");
      const res = await fetch(`/api/v1/documents/${documentId}`, {
        headers: { "X-Phone-Number": phone },
      });
      if (!res.ok) throw new Error(`Fetch failed: ${res.status}`);
      return (await res.json()) as DocumentRow;
    },
    enabled: !!documentId && !!phone,
    staleTime: 30 * 1000,
  });
}

/**
 * Returns a stable `invalidate(id)` that refetches the single-document query.
 * Used by DocCard's SSE listener on ready/failed transitions.
 */
export function useInvalidateDocument() {
  const qc = useQueryClient();
  return useCallback(
    (documentId: string) => {
      void qc.invalidateQueries({ queryKey: ["document", documentId] });
    },
    [qc],
  );
}
