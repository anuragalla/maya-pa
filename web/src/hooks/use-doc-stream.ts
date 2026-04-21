import { useEffect, useState } from "react";

import {
  parseDocStreamEvent,
  type DocStreamStage,
  type DocumentRow,
} from "@/lib/documents";
import { readSseFrames } from "@/lib/sse";

interface UseDocStreamResult {
  stage: DocStreamStage | null;
  label: string;
  payload: Partial<DocumentRow> | null;
  error: string | null;
}

const TERMINAL: ReadonlySet<DocStreamStage> = new Set(["ready", "failed", "cancelled"]);

export function useDocStream(
  documentId: string | null,
  phone: string,
): UseDocStreamResult {
  const [stage, setStage] = useState<DocStreamStage | null>(null);
  const [label, setLabel] = useState<string>("");
  const [payload, setPayload] = useState<Partial<DocumentRow> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!documentId || !phone) return;

    const controller = new AbortController();
    setStage(null);
    setLabel("");
    setPayload(null);
    setError(null);

    const run = async () => {
      try {
        const res = await fetch(`/api/v1/documents/${documentId}/events`, {
          headers: { "X-Phone-Number": phone, Accept: "text/event-stream" },
          signal: controller.signal,
        });
        if (!res.ok) {
          setError(`SSE ${res.status}`);
          return;
        }
        for await (const frame of readSseFrames(res, controller.signal)) {
          const ev = parseDocStreamEvent(frame.data);
          if (!ev) continue;
          setStage((prev) => (prev === ev.stage ? prev : ev.stage));
          if (ev.label) setLabel((prev) => (prev === ev.label ? prev : ev.label));
          if (ev.payload) setPayload(ev.payload);
          if (TERMINAL.has(ev.stage) || TERMINAL.has(frame.event as DocStreamStage)) {
            controller.abort();
            return;
          }
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "SSE stream error");
      }
    };

    void run();
    return () => controller.abort();
  }, [documentId, phone]);

  return { stage, label, payload, error };
}
